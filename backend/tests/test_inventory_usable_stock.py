"""
Unit tests for usable stock calculation and canonical unit rules.
Verifies batch-level accounting, expiry cutoffs, and reservation hold subtraction.
"""

from datetime import date, timedelta
import pytest

from app.domain.inventory import (
    calculate_usable_stock,
    validate_canonical_unit,
    are_units_compatible,
    are_formulations_compatible,
    normalize_unit,
)
from app.domain.models import InventoryBatch


def test_clean_eligible_stock():
    """Verify normal usable stock calculation with healthy batches."""
    today = date(2026, 10, 15)
    batches = [
        InventoryBatch(batch_number="B1", quantity=100, expiry_date=today + timedelta(days=60)),
        InventoryBatch(batch_number="B2", quantity=200, expiry_date=today + timedelta(days=90)),
    ]

    res = calculate_usable_stock(
        facility_id="PHC-001",
        item_id=1,
        item_name="Paracetamol 500mg",
        unit="tablets",
        batches=batches,
        active_reservations=0,
        as_of_date=today,
    )

    assert res.total_physical_quantity == 300
    assert res.expired_quantity == 0
    assert res.reserved_quantity == 0
    assert res.quarantined_quantity == 0
    assert res.usable_quantity == 300
    assert len(res.active_batches) == 2


def test_expired_batches_excluded():
    """Batches where expiry_date <= as_of_date must be excluded from usable stock."""
    today = date(2026, 10, 15)
    batches = [
        InventoryBatch(batch_number="B-EXP1", quantity=50, expiry_date=today - timedelta(days=1)),
        InventoryBatch(batch_number="B-EXP2", quantity=30, expiry_date=today),  # Expiring today
        InventoryBatch(batch_number="B-GOOD", quantity=120, expiry_date=today + timedelta(days=45)),
    ]

    res = calculate_usable_stock(
        facility_id="PHC-001",
        item_id=1,
        item_name="Paracetamol",
        unit="tablets",
        batches=batches,
        as_of_date=today,
    )

    assert res.total_physical_quantity == 200
    assert res.expired_quantity == 80
    assert res.usable_quantity == 120
    assert len(res.active_batches) == 1
    assert res.active_batches[0].batch_number == "B-GOOD"


def test_quarantined_and_damaged_batches_excluded():
    """Quarantined or damaged stock must not be counted as usable."""
    today = date(2026, 10, 15)
    batches = [
        InventoryBatch(batch_number="B-Q", quantity=40, expiry_date=today + timedelta(days=60), is_quarantined=True),
        InventoryBatch(batch_number="B-D", quantity=20, expiry_date=today + timedelta(days=60), is_damaged=True),
        InventoryBatch(batch_number="B-OK", quantity=100, expiry_date=today + timedelta(days=60)),
    ]

    res = calculate_usable_stock(
        facility_id="PHC-001",
        item_id=2,
        item_name="Amoxicillin",
        unit="capsules",
        batches=batches,
        as_of_date=today,
    )

    assert res.total_physical_quantity == 160
    assert res.quarantined_quantity == 60
    assert res.usable_quantity == 100
    assert len(res.active_batches) == 1
    assert res.active_batches[0].batch_number == "B-OK"


def test_active_reservations_subtracted_without_double_count():
    """Active transfer reservations must be subtracted once from usable stock."""
    today = date(2026, 10, 15)
    batches = [
        InventoryBatch(batch_number="B1", quantity=100, expiry_date=today + timedelta(days=60)),
        InventoryBatch(batch_number="B2", quantity=100, expiry_date=today - timedelta(days=10)),  # Expired
    ]

    # Active hold for 30 units
    res = calculate_usable_stock(
        facility_id="PHC-002",
        item_id=1,
        item_name="Paracetamol",
        unit="tablets",
        batches=batches,
        active_reservations=30,
        as_of_date=today,
    )

    assert res.total_physical_quantity == 200
    assert res.expired_quantity == 100
    assert res.reserved_quantity == 30
    # Usable = 200 - 100 (expired) - 30 (reserved) = 70
    assert res.usable_quantity == 70


def test_double_subtraction_prevention_on_quarantined_expired_batch():
    """A batch that is both expired AND quarantined must not be deducted twice."""
    today = date(2026, 10, 15)
    batches = [
        InventoryBatch(
            batch_number="B-EXP-AND-Q",
            quantity=50,
            expiry_date=today - timedelta(days=5),
            is_quarantined=True,
        ),
        InventoryBatch(batch_number="B-CLEAN", quantity=100, expiry_date=today + timedelta(days=30)),
    ]

    res = calculate_usable_stock(
        facility_id="PHC-001",
        item_id=1,
        item_name="Paracetamol",
        unit="tablets",
        batches=batches,
        as_of_date=today,
    )

    assert res.total_physical_quantity == 150
    assert res.expired_quantity == 50
    assert res.quarantined_quantity == 0  # Not double-counted in quarantined
    assert res.usable_quantity == 100


def test_fefo_batch_ordering():
    """Active batches must be ordered strictly by earliest expiry date (FEFO)."""
    today = date(2026, 10, 15)
    batches = [
        InventoryBatch(batch_number="B-LATE", quantity=50, expiry_date=today + timedelta(days=180)),
        InventoryBatch(batch_number="B-EARLY", quantity=40, expiry_date=today + timedelta(days=20)),
        InventoryBatch(batch_number="B-MID", quantity=60, expiry_date=today + timedelta(days=60)),
    ]

    res = calculate_usable_stock(
        facility_id="PHC-001",
        item_id=1,
        item_name="Paracetamol",
        unit="tablets",
        batches=batches,
        as_of_date=today,
    )

    batch_order = [b.batch_number for b in res.active_batches]
    assert batch_order == ["B-EARLY", "B-MID", "B-LATE"]


def test_canonical_unit_validation_and_compatibility():
    """Ensure canonical units are validated and incompatible units are rejected."""
    assert validate_canonical_unit("tablets") is True
    assert validate_canonical_unit("capsules") is True
    assert validate_canonical_unit("sachets") is True
    assert validate_canonical_unit("vials") is True
    assert validate_canonical_unit("invalid_custom_unit") is False

    assert are_units_compatible("tablets", "tablet") is True
    assert are_units_compatible("tablets", "capsules") is False
    assert are_units_compatible("vials", "tablets") is False


def test_dosage_form_compatibility():
    """Dosage forms must match when both are specified."""
    assert are_formulations_compatible("tablet", "tablet") is True
    assert are_formulations_compatible("syrup", "tablet") is False
    assert are_formulations_compatible(None, "tablet") is True
    assert are_formulations_compatible("tablet", None) is True
