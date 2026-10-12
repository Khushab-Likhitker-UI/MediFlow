"""
Unit tests for the safe donor candidate evaluation engine.
Verifies donor reserve protection, transfer capping, batch shelf-life, and deterministic ranking.
"""

from datetime import date, timedelta
import pytest

from app.domain.donor import evaluate_donor_candidates
from app.domain.models import DonorFacilityContext, InventoryBatch


def test_donor_with_safe_surplus_eligible():
    """Donor facility with surplus above reserve and projected demand is eligible."""
    today = date(2026, 10, 15)
    donor_batches = [
        InventoryBatch(batch_number="B1", quantity=300, expiry_date=today + timedelta(days=180)),
    ]

    context = DonorFacilityContext(
        facility_id="PHC-002",
        facility_name="North PHC",
        district="Central",
        latitude=12.98,
        longitude=77.60,
        batches=donor_batches,
        active_reservations=0,
        safety_reserve=50,
        projected_demand_over_horizon=50,
    )

    # Donor usable: 300, reserve: 50, demand: 50 => safe surplus = 200
    res = evaluate_donor_candidates(
        recipient_facility_id="PHC-001",
        recipient_facility_name="Central PHC",
        recipient_district="Central",
        recipient_lat=12.97,
        recipient_lng=77.59,
        item_id=1,
        item_name="Paracetamol",
        unit="tablets",
        recipient_deficit=100,
        candidate_contexts=[context],
        as_of_date=today,
    )

    assert res.has_safe_donor is True
    assert res.recommended_candidate is not None
    assert res.recommended_candidate.facility_id == "PHC-002"
    assert res.recommended_candidate.is_eligible is True
    assert res.recommended_candidate.donor_safe_surplus == 200
    assert res.recommended_quantity == 100  # Capped by recipient deficit of 100


def test_donor_at_reserve_rejected():
    """Donor whose stock is at or below its own safety reserve must be rejected."""
    today = date(2026, 10, 15)
    donor_batches = [
        InventoryBatch(batch_number="B1", quantity=50, expiry_date=today + timedelta(days=180)),
    ]

    context = DonorFacilityContext(
        facility_id="PHC-002",
        facility_name="North PHC",
        district="Central",
        latitude=12.98,
        longitude=77.60,
        batches=donor_batches,
        active_reservations=0,
        safety_reserve=50,  # Exactly at reserve
        projected_demand_over_horizon=0,
    )

    res = evaluate_donor_candidates(
        recipient_facility_id="PHC-001",
        recipient_facility_name="Central PHC",
        recipient_district="Central",
        recipient_lat=12.97,
        recipient_lng=77.59,
        item_id=1,
        item_name="Paracetamol",
        unit="tablets",
        recipient_deficit=20,
        candidate_contexts=[context],
        as_of_date=today,
    )

    assert res.has_safe_donor is False
    assert res.recommended_candidate is None
    cand = res.candidates[0]
    assert cand.is_eligible is False
    assert "protected reserve" in cand.rejection_reason.lower()


def test_batches_expiring_soon_rejected():
    """Batches with less than 30 days shelf life cannot be donated."""
    today = date(2026, 10, 15)
    donor_batches = [
        InventoryBatch(batch_number="B-EXP", quantity=200, expiry_date=today + timedelta(days=15)),  # Only 15 days left
    ]

    context = DonorFacilityContext(
        facility_id="PHC-003",
        facility_name="East PHC",
        district="Central",
        latitude=12.98,
        longitude=77.60,
        batches=donor_batches,
        active_reservations=0,
        safety_reserve=20,
        projected_demand_over_horizon=10,
    )

    res = evaluate_donor_candidates(
        recipient_facility_id="PHC-001",
        recipient_facility_name="Central PHC",
        recipient_district="Central",
        recipient_lat=12.97,
        recipient_lng=77.59,
        item_id=1,
        item_name="Paracetamol",
        unit="tablets",
        recipient_deficit=50,
        candidate_contexts=[context],
        min_shelf_life_days=30,
        as_of_date=today,
    )

    assert res.has_safe_donor is False
    assert res.candidates[0].is_eligible is False
    assert "shelf-life" in res.candidates[0].rejection_reason.lower()


def test_transfer_quantity_capped_by_donor_surplus():
    """Transfer quantity cannot exceed donor safe surplus even if recipient needs more."""
    today = date(2026, 10, 15)
    donor_batches = [
        InventoryBatch(batch_number="B1", quantity=100, expiry_date=today + timedelta(days=120)),
    ]

    context = DonorFacilityContext(
        facility_id="PHC-002",
        facility_name="North PHC",
        district="Central",
        latitude=12.98,
        longitude=77.60,
        batches=donor_batches,
        active_reservations=0,
        safety_reserve=40,
        projected_demand_over_horizon=20,
    )

    # Usable = 100, Reserve = 40, Demand = 20 => Surplus = 40
    res = evaluate_donor_candidates(
        recipient_facility_id="PHC-001",
        recipient_facility_name="Central PHC",
        recipient_district="Central",
        recipient_lat=12.97,
        recipient_lng=77.59,
        item_id=1,
        item_name="Paracetamol",
        unit="tablets",
        recipient_deficit=200,  # Recipient needs 200
        candidate_contexts=[context],
        as_of_date=today,
    )

    assert res.has_safe_donor is True
    assert res.recommended_quantity == 40  # Capped at donor safe surplus of 40


def test_deterministic_ranking_prioritizes_same_district_and_surplus():
    """Candidates in the same district with larger surpluses are ranked higher."""
    today = date(2026, 10, 15)
    # Candidate A: Other district, surplus 200
    cand_a = DonorFacilityContext(
        facility_id="PHC-OTHER",
        facility_name="Other District PHC",
        district="North District",
        latitude=13.50,
        longitude=78.00,
        batches=[InventoryBatch("B1", 300, today + timedelta(days=90))],
        safety_reserve=50,
        projected_demand_over_horizon=50,
    )

    # Candidate B: Same district, surplus 100
    cand_b = DonorFacilityContext(
        facility_id="PHC-SAME",
        facility_name="Same District PHC",
        district="Central District",
        latitude=12.99,
        longitude=77.61,
        batches=[InventoryBatch("B2", 200, today + timedelta(days=90))],
        safety_reserve=50,
        projected_demand_over_horizon=50,
    )

    res = evaluate_donor_candidates(
        recipient_facility_id="PHC-001",
        recipient_facility_name="Central PHC",
        recipient_district="Central District",
        recipient_lat=12.97,
        recipient_lng=77.59,
        item_id=1,
        item_name="Paracetamol",
        unit="tablets",
        recipient_deficit=50,
        candidate_contexts=[cand_a, cand_b],
        as_of_date=today,
    )

    assert res.recommended_candidate.facility_id == "PHC-SAME"
    assert res.recommended_candidate.rank == 1


def test_no_safe_donor_returns_escalation_action():
    """When no safe donor is found, escalation instructions are returned."""
    today = date(2026, 10, 15)
    res = evaluate_donor_candidates(
        recipient_facility_id="PHC-001",
        recipient_facility_name="Central PHC",
        recipient_district="Central District",
        recipient_lat=12.97,
        recipient_lng=77.59,
        item_id=1,
        item_name="Paracetamol",
        unit="tablets",
        recipient_deficit=50,
        candidate_contexts=[],  # No candidate facilities
        as_of_date=today,
    )

    assert res.has_safe_donor is False
    assert res.recommended_candidate is None
    assert "emergency central purchase" in res.escalation_action.lower()


def test_competing_recipients_cannot_double_allocate_surplus():
    """
    When Recipient 1 receives a transfer reservation from a donor,
    the donor's active_reservations increases, preventing Recipient 2 from taking the same units.
    """
    today = date(2026, 10, 15)
    donor_batches = [InventoryBatch("B1", 100, today + timedelta(days=90))]

    # Initial state: Donor has 100 total, 20 reserve, 10 demand => 70 safe surplus
    donor_ctx = DonorFacilityContext(
        facility_id="PHC-DONOR",
        facility_name="Donor PHC",
        district="Central",
        latitude=12.98,
        longitude=77.60,
        batches=donor_batches,
        active_reservations=0,
        safety_reserve=20,
        projected_demand_over_horizon=10,
    )

    # Recipient 1 needs 50 units
    res1 = evaluate_donor_candidates(
        recipient_facility_id="PHC-REC1",
        recipient_facility_name="Recipient 1",
        recipient_district="Central",
        recipient_lat=12.97,
        recipient_lng=77.59,
        item_id=1,
        item_name="Paracetamol",
        unit="tablets",
        recipient_deficit=50,
        candidate_contexts=[donor_ctx],
        as_of_date=today,
    )
    assert res1.recommended_quantity == 50

    # Simulate reservation created for Recipient 1 (active_reservations now 50)
    donor_ctx.active_reservations = 50

    # Recipient 2 now requests 40 units from the same donor
    res2 = evaluate_donor_candidates(
        recipient_facility_id="PHC-REC2",
        recipient_facility_name="Recipient 2",
        recipient_district="Central",
        recipient_lat=12.97,
        recipient_lng=77.59,
        item_id=1,
        item_name="Paracetamol",
        unit="tablets",
        recipient_deficit=40,
        candidate_contexts=[donor_ctx],
        as_of_date=today,
    )

    # Remaining safe surplus is now 70 - 50 = 20 units!
    # Recipient 2 receives 20, NOT 40
    assert res2.recommended_quantity == 20
