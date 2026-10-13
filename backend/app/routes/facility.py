"""
Facility management routes.

Provides endpoints for updating Primary Health Centre facility statuses
like beds availability and doctor attendance.

All operations verify that the referenced PHC exists before writing.
"""

import logging
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException

import time
from app.domain.auth import get_current_user, require_roles, verify_facility_access
from app.models.schemas import BedsUpdate, AttendanceUpdate, FacilityCreate
from app import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/facility", tags=["Facility"])


# ── Helpers ──────────────────────────────────────────────────────────────────

def _verify_phc_exists(phc_id: str) -> None:
    """Raise 400 if the given PHC ID does not exist in *facilities*."""
    try:
        check = db.fetch_one(
            "SELECT phc_id FROM facilities WHERE phc_id = %s", (phc_id,)
        )
    except Exception as e:
        logger.error("Failed to verify PHC %s: %s", phc_id, e)
        raise HTTPException(
            status_code=500, detail="Failed to verify facility"
        )
    if not check:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid PHC ID '{phc_id}'. Facility does not exist.",
        )


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get(
    "/",
    summary="List all facilities with stock, beds, and attendance",
    response_description="Array of facilities formatted for frontend dashboards",
)
async def list_facilities():
    """Return all facilities with their aggregated stock items, available beds, and doctor attendance.

    Formatted to seamlessly integrate with frontend dashboards.
    """
    try:
        facs = db.fetch_all("SELECT phc_id, facility_name, district, state, address, latitude, longitude, updated_at FROM facilities ORDER BY phc_id")
        meds = db.fetch_all("SELECT item_id, name, reorder_level, unit FROM medicines ORDER BY item_id")
        inv = db.fetch_all("SELECT phc_id, item_id, COALESCE(SUM(quantity), 0) AS quantity FROM inventory GROUP BY phc_id, item_id")
        beds = db.fetch_all("SELECT phc_id, available_beds FROM beds")
        # Get the latest attendance for each PHC (not just today)
        att = db.fetch_all("""
            SELECT pas.phc_id, pas.doctors_present
            FROM phc_attendance_summary pas
            JOIN (
                SELECT phc_id, MAX(attendance_date) AS max_date
                FROM phc_attendance_summary
                GROUP BY phc_id
            ) latest ON pas.phc_id = latest.phc_id AND pas.attendance_date = latest.max_date
        """)
        # Compute actual avg daily consumption from medicine_consumption table
        consumption = db.fetch_all("""
            SELECT phc_id, item_id,
                   COALESCE(AVG(quantity_consumed), 0) AS avg_daily
            FROM medicine_consumption
            WHERE consumption_date >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY phc_id, item_id
        """)

        inv_map = {(r["phc_id"], r["item_id"]): int(r["quantity"]) for r in inv}
        beds_map = {r["phc_id"]: int(r["available_beds"]) for r in beds}
        att_map = {r["phc_id"]: int(r["doctors_present"]) for r in att}
        cons_map = {(r["phc_id"], r["item_id"]): float(r["avg_daily"]) for r in consumption}

        result = []
        for f in facs:
            phc_id = f["phc_id"]
            stock_items = []
            for m in meds:
                qty = inv_map.get((phc_id, m["item_id"]), 0)
                # Use real consumption data, fall back to a small fraction of reorder level
                avg_cons = cons_map.get((phc_id, m["item_id"]), None)
                if avg_cons is None or avg_cons < 1:
                    avg_cons = max(1, int(m["reorder_level"] * 0.15))
                else:
                    avg_cons = int(avg_cons)
                stock_items.append({
                    "itemName": m["name"],
                    "currentUnits": qty,
                    "avgDailyConsumption": avg_cons,
                    "unit": m["unit"],
                    "reorderLevel": m["reorder_level"],
                })

            result.append({
                "id": phc_id,
                "name": f["facility_name"],
                "block": f["district"],
                "lat": float(f["latitude"]),
                "lng": float(f["longitude"]),
                "availableBeds": beds_map.get(phc_id, 0),
                "doctorsPresent": att_map.get(phc_id, 0),
                "stockItems": stock_items,
                "lastUpdated": str(f["updated_at"]),
            })
        return result
    except Exception as e:
        logger.error("Failed to list facilities: %s", e)
        raise HTTPException(status_code=500, detail="Failed to list facilities")


@router.post(
    "/",
    status_code=201,
    summary="Register a new PHC facility in Supabase",
    response_description="Created facility summary",
)
async def create_facility(
    facility_in: FacilityCreate,
    current_user: dict = Depends(require_roles(["admin"])),
):
    """Create a new Primary Health Centre in Supabase with initial beds & inventory."""
    phc_id = f"PHC-{int(time.time() * 1000) % 1000000:06d}"
    try:
        # Insert Facility
        db.execute_query(
            """
            INSERT INTO facilities (phc_id, facility_name, facility_type, district, state, address, latitude, longitude)
            VALUES (%s, %s, 'PHC', %s, 'State', %s, 12.9716, 77.5946)
            """,
            (phc_id, facility_in.name.strip(), facility_in.block.strip(), f"{facility_in.name.strip()}, {facility_in.block.strip()}")
        )
        # Insert initial beds
        db.execute_query(
            "INSERT INTO beds (phc_id, available_beds) VALUES (%s, 10)",
            (phc_id,)
        )
        # Insert initial attendance
        db.execute_query(
            """
            INSERT INTO phc_attendance_summary (phc_id, attendance_date, doctors_present, timestamp)
            VALUES (%s, CURRENT_DATE, 2, NOW())
            """,
            (phc_id,)
        )
        # Insert stock items
        default_expiry = (date.today() + timedelta(days=365)).isoformat()
        for item in facility_in.stockItems:
            m = db.fetch_one("SELECT item_id FROM medicines WHERE LOWER(name) = LOWER(%s)", (item.itemName.strip(),))
            if not m:
                m = db.fetch_one(
                    "INSERT INTO medicines (name, category, unit, reorder_level) VALUES (%s, 'Essential', 'units', 50) RETURNING item_id",
                    (item.itemName.strip(),)
                )
            if m and "item_id" in m:
                item_id = m["item_id"]
                db.execute_query(
                    """
                    INSERT INTO inventory (phc_id, item_id, batch_number, quantity, expiry_date)
                    VALUES (%s, %s, 'INITIAL-BATCH', %s, %s)
                    """,
                    (phc_id, item_id, item.currentUnits, default_expiry)
                )
                if item.avgDailyConsumption > 0:
                    db.execute_query(
                        """
                        INSERT INTO medicine_consumption (phc_id, item_id, consumption_date, quantity_consumed)
                        VALUES (%s, %s, CURRENT_DATE, %s)
                        """,
                        (phc_id, item_id, item.avgDailyConsumption)
                    )
        return {"status": "success", "id": phc_id, "name": facility_in.name, "block": facility_in.block}
    except Exception as e:
        logger.error("Failed to create facility: %s", e)
        raise HTTPException(status_code=500, detail="Database error creating facility")


@router.post(
    "/beds",
    summary="Log a beds availability update for a PHC",
    response_description="Acknowledgement that the update was received",
)
async def update_beds(
    update: BedsUpdate,
    current_user: dict = Depends(get_current_user),
):
    """UPSERT available beds count for a PHC.

    Returns 400 if the PHC ID does not exist in the facilities table.
    """
    verify_facility_access(current_user, update.phc_id)
    _verify_phc_exists(update.phc_id)

    query = """
    INSERT INTO beds (phc_id, available_beds, timestamp, updated_at)
    VALUES (%s, %s, %s, NOW())
    ON CONFLICT (phc_id) 
    DO UPDATE SET available_beds = EXCLUDED.available_beds,
                  timestamp     = EXCLUDED.timestamp,
                  updated_at    = NOW()
    """
    try:
        db.execute_query(
            query, (update.phc_id, update.available_beds, update.timestamp)
        )
    except Exception as e:
        error_msg = str(e).lower()
        if "foreign key constraint" in error_msg:
            raise HTTPException(status_code=400, detail="Invalid PHC ID")
        logger.error("Failed to update beds for %s: %s", update.phc_id, e)
        raise HTTPException(
            status_code=500, detail="Failed to log beds update"
        )

    return {"status": "success", "message": "Beds update logged"}


@router.post(
    "/attendance",
    summary="Log a doctor attendance update for a PHC",
    response_description="Acknowledgement that the update was received",
)
async def update_attendance(
    update: AttendanceUpdate,
    current_user: dict = Depends(get_current_user),
):
    """UPSERT daily doctor attendance summary for a PHC.

    Returns 400 if the PHC ID does not exist in the facilities table.
    """
    verify_facility_access(current_user, update.phc_id)
    _verify_phc_exists(update.phc_id)

    attendance_date = update.timestamp.date()
    query = """
    INSERT INTO phc_attendance_summary
        (phc_id, attendance_date, doctors_present, timestamp, updated_at)
    VALUES (%s, %s, %s, %s, NOW())
    ON CONFLICT (phc_id, attendance_date)
    DO UPDATE SET doctors_present = EXCLUDED.doctors_present,
                  timestamp       = EXCLUDED.timestamp,
                  updated_at      = NOW()
    """
    try:
        db.execute_query(
            query,
            (update.phc_id, attendance_date, update.doctors_present, update.timestamp),
        )
    except Exception as e:
        error_msg = str(e).lower()
        if "foreign key constraint" in error_msg:
            raise HTTPException(status_code=400, detail="Invalid PHC ID")
        logger.error(
            "Failed to update attendance for %s: %s", update.phc_id, e
        )
        raise HTTPException(
            status_code=500, detail="Failed to log attendance update"
        )

    return {"status": "success", "message": "Attendance update logged"}


@router.get(
    "/{phc_id}/inventory",
    summary="Get batch-level inventory and usable stock for a facility",
)
async def get_facility_inventory(phc_id: str):
    """
    Return detailed batch-level inventory for a specific facility,
    including total physical quantity, active reservations, expired stock,
    and net usable stock.
    """
    _verify_phc_exists(phc_id)

    # 1. Fetch batches for this facility
    batches_query = """
    SELECT i.item_id, m.name AS item_name, m.unit, m.reorder_level,
           i.batch_number, i.quantity, i.expiry_date
    FROM inventory i
    JOIN medicines m ON i.item_id = m.item_id
    WHERE i.phc_id = %s
    ORDER BY i.item_id, i.expiry_date ASC;
    """
    batches = db.fetch_all(batches_query, (phc_id,))

    # 2. Fetch active reservations for this facility
    res_query = """
    SELECT item_id, COALESCE(SUM(reserved_quantity), 0) AS reserved_quantity
    FROM stock_reservations
    WHERE phc_id = %s AND status = 'active'
    GROUP BY item_id;
    """
    reservations = db.fetch_all(res_query, (phc_id,))
    res_map = {r["item_id"]: r["reserved_quantity"] for r in reservations}

    # 3. Group by medicine and calculate usable stock
    from datetime import date
    today = date.today()

    items_map = {}
    for b in batches:
        iid = b["item_id"]
        if iid not in items_map:
            items_map[iid] = {
                "item_id": iid,
                "item_name": b["item_name"],
                "unit": b["unit"],
                "reorder_level": b["reorder_level"],
                "total_physical_quantity": 0,
                "expired_quantity": 0,
                "reserved_quantity": res_map.get(iid, 0),
                "usable_quantity": 0,
                "batches": [],
            }

        qty = max(0, b["quantity"])
        is_exp = b["expiry_date"] <= today if b["expiry_date"] else False

        items_map[iid]["total_physical_quantity"] += qty
        if is_exp:
            items_map[iid]["expired_quantity"] += qty

        items_map[iid]["batches"].append({
            "batch_number": b["batch_number"],
            "quantity": qty,
            "expiry_date": b["expiry_date"].isoformat() if b["expiry_date"] else None,
            "is_expired": is_exp,
        })

    for item in items_map.values():
        unexpired = max(0, item["total_physical_quantity"] - item["expired_quantity"])
        item["usable_quantity"] = max(0, unexpired - item["reserved_quantity"])

    return {
        "phc_id": phc_id,
        "items": list(items_map.values()),
    }
