"""
Alert evaluation and aggregation service.
Generates structured alerts for low stock, critical depletion, expiring batches,
and consumption anomalies with provenance, data freshness, and donor counts.
"""

from __future__ import annotations
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from app.domain.models import AlertSeverity, AlertType


def generate_inventory_alerts(
    facilities: list[dict],
    inventory_items: list[dict],
    reservations_by_facility_item: dict[tuple[str, int], int],
    as_of_date: Optional[date] = None,
) -> list[dict]:
    """
    Evaluate alerts for facilities and inventory.

    Alert Types:
    - critical_stock: usable stock <= 0 (Severity: CRITICAL)
    - low_stock: usable stock < reorder_level (Severity: WARNING or CRITICAL if <= reserve)
    - expiring_soon: batches expiring within 30 days (Severity: WARNING)
    """
    if as_of_date is None:
        as_of_date = datetime.now(timezone.utc).date()

    now_iso = datetime.now(timezone.utc).isoformat()
    alerts: list[dict] = []
    expiry_horizon = as_of_date + timedelta(days=30)

    # Index facilities by ID for quick lookup
    facility_map = {f["phc_id"]: f for f in facilities}

    for item in inventory_items:
        phc_id = item["phc_id"]
        item_id = item["item_id"]
        item_name = item.get("item_name") or item.get("name", "Unknown Item")
        unit = item.get("unit", "units")
        reorder_level = item.get("reorder_level", 50)
        safety_reserve = item.get("safety_reserve", 30)

        fac = facility_map.get(phc_id, {})
        facility_name = fac.get("facility_name") or fac.get("name", phc_id)
        district = fac.get("district", "Unknown District")

        total_qty = item.get("quantity", 0)
        expiry_date = item.get("expiry_date")
        if isinstance(expiry_date, str):
            expiry_date = date.fromisoformat(expiry_date)

        # Check reservations
        reserved = reservations_by_facility_item.get((phc_id, item_id), 0)

        # Calculate usable
        is_expired = expiry_date is not None and expiry_date <= as_of_date
        usable_qty = max(0, (0 if is_expired else total_qty) - reserved)

        # 1. Critical Stock Alert
        if usable_qty <= 0:
            alerts.append(
                {
                    "alert_id": f"alert-{phc_id}-{item_id}-critical",
                    "phc_id": phc_id,
                    "facility_name": facility_name,
                    "district": district,
                    "item_id": item_id,
                    "item_name": item_name,
                    "unit": unit,
                    "type": AlertType.CRITICAL_STOCK.value,
                    "severity": AlertSeverity.CRITICAL.value,
                    "current_stock": total_qty,
                    "usable_stock": usable_qty,
                    "reserved_stock": reserved,
                    "reorder_level": reorder_level,
                    "safety_reserve": safety_reserve,
                    "message": f"Critical stockout: 0 usable {unit} remaining (physical: {total_qty}, reserved: {reserved}).",
                    "generated_at": now_iso,
                    "data_source": "database",
                    "status": "open",
                }
            )
        # 2. Low Stock / Reserve Breach Alert
        elif usable_qty <= safety_reserve:
            alerts.append(
                {
                    "alert_id": f"alert-{phc_id}-{item_id}-breach",
                    "phc_id": phc_id,
                    "facility_name": facility_name,
                    "district": district,
                    "item_id": item_id,
                    "item_name": item_name,
                    "unit": unit,
                    "type": AlertType.LOW_STOCK.value,
                    "severity": AlertSeverity.CRITICAL.value,
                    "current_stock": total_qty,
                    "usable_stock": usable_qty,
                    "reserved_stock": reserved,
                    "reorder_level": reorder_level,
                    "safety_reserve": safety_reserve,
                    "message": (
                        f"Safety reserve breached: {usable_qty} {unit} on hand is below "
                        f"protected reserve of {safety_reserve} {unit}."
                    ),
                    "generated_at": now_iso,
                    "data_source": "database",
                    "status": "open",
                }
            )
        elif usable_qty <= reorder_level:
            alerts.append(
                {
                    "alert_id": f"alert-{phc_id}-{item_id}-low",
                    "phc_id": phc_id,
                    "facility_name": facility_name,
                    "district": district,
                    "item_id": item_id,
                    "item_name": item_name,
                    "unit": unit,
                    "type": AlertType.LOW_STOCK.value,
                    "severity": AlertSeverity.WARNING.value,
                    "current_stock": total_qty,
                    "usable_stock": usable_qty,
                    "reserved_stock": reserved,
                    "reorder_level": reorder_level,
                    "safety_reserve": safety_reserve,
                    "message": (
                        f"Low stock: {usable_qty} {unit} on hand is below "
                        f"reorder level of {reorder_level} {unit}."
                    ),
                    "generated_at": now_iso,
                    "data_source": "database",
                    "status": "open",
                }
            )

        # 3. Expiring Soon Alert
        if expiry_date and as_of_date < expiry_date <= expiry_horizon and total_qty > 0:
            days_left = (expiry_date - as_of_date).days
            alerts.append(
                {
                    "alert_id": f"alert-{phc_id}-{item_id}-expiring",
                    "phc_id": phc_id,
                    "facility_name": facility_name,
                    "district": district,
                    "item_id": item_id,
                    "item_name": item_name,
                    "unit": unit,
                    "type": AlertType.EXPIRING_SOON.value,
                    "severity": AlertSeverity.WARNING.value,
                    "current_stock": total_qty,
                    "usable_stock": usable_qty,
                    "reserved_stock": reserved,
                    "reorder_level": reorder_level,
                    "safety_reserve": safety_reserve,
                    "message": f"Batch expiring in {days_left} days ({expiry_date.isoformat()}). Quantity: {total_qty} {unit}.",
                    "generated_at": now_iso,
                    "data_source": "database",
                    "status": "open",
                }
            )

    return alerts
