"""
Alerts API Router.
Returns computed alerts for critical stock depletion, safety reserve breaches,
expiring batches, and consumption anomalies.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app import db
from app.domain.alerts import generate_inventory_alerts
from app.models.schemas import AlertResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get(
    "/",
    response_model=list[AlertResponse],
    summary="List active shortage and inventory alerts across facilities",
)
async def list_alerts(
    phc_id: Optional[str] = Query(None, description="Filter by facility ID"),
    district: Optional[str] = Query(None, description="Filter by district"),
    severity: Optional[str] = Query(None, description="Filter by severity (critical/warning/info)"),
    status: Optional[str] = Query("open", description="Alert status filter"),
):
    """
    Retrieve real-time inventory alerts calculated from live stock,
    active transfer reservations, reorder levels, and batch expiry dates.
    """
    # Normalize query defaults if called directly as a function
    phc_id = phc_id if isinstance(phc_id, str) else None
    district = district if isinstance(district, str) else None
    severity = severity if isinstance(severity, str) else None
    status = status if isinstance(status, str) else "open"

    # 1. Fetch facilities
    fac_query = "SELECT phc_id, facility_name, district FROM facilities WHERE 1=1"
    fac_params = []
    if phc_id:
        fac_query += " AND phc_id = %s"
        fac_params.append(phc_id)
    if district:
        fac_query += " AND district = %s"
        fac_params.append(district)

    try:
        facilities = db.fetch_all(fac_query, tuple(fac_params) if fac_params else None)
    except Exception as e:
        logger.error("Failed to query facilities for alerts: %s", e)
        raise HTTPException(status_code=500, detail="Database error retrieving facilities.")

    if not facilities:
        return []

    target_phc_ids = [f["phc_id"] for f in facilities]

    # 2. Fetch inventory items with medicine metadata
    placeholders = ",".join(["%s"] * len(target_phc_ids))
    inv_query = f"""
    SELECT i.phc_id, i.item_id, m.name AS item_name, m.unit, m.reorder_level,
           50 AS safety_reserve, i.batch_number, i.quantity, i.expiry_date
    FROM inventory i
    JOIN medicines m ON i.item_id = m.item_id
    WHERE i.phc_id IN ({placeholders})
    ORDER BY i.phc_id, i.item_id, i.expiry_date
    """
    try:
        inv_rows = db.fetch_all(inv_query, tuple(target_phc_ids))
    except Exception as e:
        logger.error("Failed to query inventory for alerts: %s", e)
        raise HTTPException(status_code=500, detail="Database error retrieving inventory.")

    # 3. Fetch active reservations
    res_query = f"""
    SELECT phc_id, item_id, COALESCE(SUM(reserved_quantity), 0) AS total_reserved
    FROM stock_reservations
    WHERE phc_id IN ({placeholders}) AND status = 'active'
    GROUP BY phc_id, item_id
    """
    try:
        res_rows = db.fetch_all(res_query, tuple(target_phc_ids))
    except Exception as e:
        logger.warning("Failed to fetch reservations (or table empty): %s", e)
        res_rows = []

    res_map = {(r["phc_id"], r["item_id"]): r["total_reserved"] for r in res_rows}

    # 4. Generate structured alerts
    all_alerts = generate_inventory_alerts(
        facilities=facilities,
        inventory_items=inv_rows,
        reservations_by_facility_item=res_map,
    )

    # 5. Filter by severity if requested
    if severity:
        sev_clean = severity.lower().strip()
        all_alerts = [a for a in all_alerts if a["severity"] == sev_clean]

    return [AlertResponse(**a) for a in all_alerts]


@router.get(
    "/{alert_id}",
    response_model=AlertResponse,
    summary="Get single alert detail by alert identifier",
)
async def get_alert(alert_id: str):
    """Retrieve detailed information for a specific alert."""
    parts = alert_id.split("-")
    if len(parts) >= 3 and parts[0] == "alert":
        phc_id = f"{parts[1]}-{parts[2]}" if len(parts) >= 4 and parts[1] == "PHC" else parts[1]
    else:
        phc_id = None

    alerts = await list_alerts(phc_id=phc_id, district=None, severity=None, status=None)
    for a in alerts:
        if a.alert_id == alert_id:
            return a

    raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")


@router.get(
    "/{alert_id}/donors",
    summary="Evaluate candidate donors for a specific shortage alert",
)
async def get_alert_donor_candidates(alert_id: str):
    """
    Evaluates peer facilities in the district to find safe donor candidates
    without compromising any donor's safety reserve or projected demand.
    """
    from app.domain.donor import evaluate_donor_candidates
    from app.domain.models import DonorFacilityContext, InventoryBatch

    # 1. Resolve alert
    alert = await get_alert(alert_id)
    recipient_phc_id = alert.phc_id
    item_id = alert.item_id
    deficit = max(0, alert.safety_reserve - alert.usable_stock) or 50

    # 2. Fetch recipient facility details
    recip = db.fetch_one(
        "SELECT phc_id, facility_name, district, latitude, longitude FROM facilities WHERE phc_id = %s",
        (recipient_phc_id,),
    )
    if not recip:
        raise HTTPException(status_code=404, detail=f"Recipient facility '{recipient_phc_id}' not found.")

    med = db.fetch_one("SELECT item_id, name, unit FROM medicines WHERE item_id = %s", (item_id,))
    if not med:
        raise HTTPException(status_code=404, detail=f"Medicine {item_id} not found.")

    # 3. Fetch potential donor facilities
    other_facs = db.fetch_all(
        """
        SELECT phc_id, facility_name, district, latitude, longitude
        FROM facilities
        WHERE phc_id != %s AND operational_status = 'active'
        """,
        (recipient_phc_id,),
    )

    # 4. Build contexts for each candidate facility
    contexts = []
    for f in other_facs:
        fac_id = f["phc_id"]
        batches_raw = db.fetch_all(
            "SELECT batch_number, quantity, expiry_date FROM inventory WHERE phc_id = %s AND item_id = %s",
            (fac_id, item_id),
        )
        batches = [
            InventoryBatch(
                batch_number=b["batch_number"],
                quantity=b["quantity"],
                expiry_date=b["expiry_date"],
            )
            for b in batches_raw
        ]

        active_res = db.fetch_one(
            "SELECT COALESCE(SUM(reserved_quantity), 0) as total FROM stock_reservations WHERE phc_id = %s AND item_id = %s AND status = 'active'",
            (fac_id, item_id),
        )
        res_count = active_res["total"] if active_res else 0

        contexts.append(
            DonorFacilityContext(
                facility_id=fac_id,
                facility_name=f["facility_name"],
                district=f["district"],
                latitude=float(f["latitude"]),
                longitude=float(f["longitude"]),
                batches=batches,
                active_reservations=res_count,
                safety_reserve=50,
                projected_demand_over_horizon=20,
            )
        )

    # 5. Evaluate using safe donor domain engine
    eval_result = evaluate_donor_candidates(
        recipient_facility_id=recipient_phc_id,
        recipient_facility_name=recip["facility_name"],
        recipient_district=recip["district"],
        recipient_lat=float(recip["latitude"]),
        recipient_lng=float(recip["longitude"]),
        item_id=item_id,
        item_name=med["name"],
        unit=med["unit"],
        recipient_deficit=deficit,
        candidate_contexts=contexts,
    )

    # 6. Format to match frontend contract exactly
    formatted = []
    for c in eval_result.candidates:
        ineligibility = c.rejection_reason or None
        best_batch = c.eligible_batches[0] if c.eligible_batches else None
        batch_num = "BATCH-STD"
        expiry_val = "2027-12-31"
        if isinstance(best_batch, dict):
            batch_num = best_batch.get("batch_number", "BATCH-STD")
            expiry_val = str(best_batch.get("expiry_date", "2027-12-31"))
        elif best_batch:
            batch_num = getattr(best_batch, "batch_number", "BATCH-STD")
            expiry_val = str(getattr(best_batch, "expiry_date", "2027-12-31"))

        dist = c.distance_km or 10.0
        donor_reserve_after = max(0, c.current_usable_stock - c.transferable_quantity)
        coverage_ratio = round(donor_reserve_after / max(1, c.protected_reserve), 2)

        formatted.append({
            "donor_phc_id": c.facility_id,
            "donor_phc_name": c.facility_name,
            "block": c.district,
            "distance_km": dist,
            "estimated_transit_minutes": max(15, int(dist * 2)),
            "transferable_quantity": c.transferable_quantity,
            "donor_reserve_after_transfer": donor_reserve_after,
            "reserve_coverage_ratio_after": coverage_ratio,
            "batch_number": batch_num,
            "expiry_date": expiry_val,
            "eligible": c.is_eligible,
            "ineligibility_reason": ineligibility,
        })

    return formatted

