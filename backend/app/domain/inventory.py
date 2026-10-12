"""
Domain logic for usable stock calculation and canonical unit/formulation validation.
Enforces single-source-of-truth inventory rules without HTTP or database coupling.
"""

from __future__ import annotations
from datetime import date, datetime, timezone
from typing import Optional

from app.domain.models import InventoryBatch, UsableStockResult

# Canonical allowable base units recognized across the platform
CANONICAL_UNITS = {
    "tablets",
    "capsules",
    "sachets",
    "vials",
    "bags",
    "units",
    "boxes",
    "rolls",
    "tubes",
}

CANONICAL_DOSAGE_FORMS = {
    "tablet",
    "capsule",
    "syrup",
    "injection",
    "ointment",
    "drops",
    "inhaler",
    "powder",
    "suspension",
    "cream",
    "gel",
    "solution",
    "other",
}


def normalize_unit(unit: str) -> str:
    """Normalize a unit string to lowercase stripped standard form."""
    if not unit:
        return "units"
    cleaned = unit.strip().lower()
    # Handle common singular/plural variations
    aliases = {
        "tablet": "tablets",
        "capsule": "capsules",
        "sachet": "sachets",
        "vial": "vials",
        "bag": "bags",
        "unit": "units",
        "box": "boxes",
        "roll": "rolls",
        "tube": "tubes",
    }
    return aliases.get(cleaned, cleaned)


def validate_canonical_unit(unit: str) -> bool:
    """Check if the provided unit is a valid canonical unit."""
    return normalize_unit(unit) in CANONICAL_UNITS


def are_units_compatible(unit_a: str, unit_b: str) -> bool:
    """Verify that two units are strictly compatible for inventory operations."""
    return normalize_unit(unit_a) == normalize_unit(unit_b)


def are_formulations_compatible(form_a: Optional[str], form_b: Optional[str]) -> bool:
    """
    Check if two dosage forms are compatible.
    If either is None/unspecified, compatibility is assumed if medicines match.
    If both specified, they must match exactly.
    """
    if not form_a or not form_b:
        return True
    return form_a.strip().lower() == form_b.strip().lower()


def calculate_usable_stock(
    facility_id: str,
    item_id: int,
    item_name: str,
    unit: str,
    batches: list[InventoryBatch],
    active_reservations: int = 0,
    as_of_date: Optional[date] = None,
) -> UsableStockResult:
    """
    Compute usable stock for a facility and medicine.

    Accounting Rules:
    1. Physical Total = sum(batch.quantity for all batches).
    2. Expired Quantity = sum(batch.quantity where batch.expiry_date <= as_of_date).
    3. Quarantined/Damaged = sum(batch.quantity where (quarantined or damaged)
       AND expiry_date > as_of_date) to prevent double subtraction.
    4. Unexpired Available = Physical Total - Expired - Quarantined.
    5. Reserved Quantity = active holds from approved transfers awaiting dispatch.
       Subtracted once from unexpired available stock.
    6. Usable Stock = max(0, Unexpired Available - Reserved Quantity).
    7. Active Batches = unexpired, undamaged, unquarantined batches with quantity > 0,
       ordered by earliest expiry date (FEFO - First Expired, First Out).
    """
    if as_of_date is None:
        as_of_date = datetime.now(timezone.utc).date()

    total_physical = 0
    expired_qty = 0
    quarantined_qty = 0
    eligible_batches: list[InventoryBatch] = []

    for b in batches:
        qty = max(0, b.quantity)
        total_physical += qty

        if b.expiry_date <= as_of_date:
            expired_qty += qty
        elif b.is_quarantined or b.is_damaged:
            quarantined_qty += qty
        else:
            if qty > 0:
                eligible_batches.append(b)

    # Sort eligible batches by expiry date (FEFO)
    eligible_batches.sort(key=lambda b: b.expiry_date)

    unexpired_clean = total_physical - expired_qty - quarantined_qty
    reservations_applied = max(0, active_reservations)
    usable_qty = max(0, unexpired_clean - reservations_applied)

    return UsableStockResult(
        facility_id=facility_id,
        item_id=item_id,
        item_name=item_name,
        unit=normalize_unit(unit),
        total_physical_quantity=total_physical,
        expired_quantity=expired_qty,
        reserved_quantity=reservations_applied,
        quarantined_quantity=quarantined_qty,
        usable_quantity=usable_qty,
        active_batches=eligible_batches,
    )
