"""
Unit tests for deterministic stock projection engine.
Tests replenishment timing, safety reserve breach dates, and missing history labels.
"""

from datetime import date, timedelta
import pytest

from app.domain.models import AlertSeverity
from app.domain.projection import project_stock


def test_standard_depletion_and_stockout():
    """Verify daily depletion calculation and stockout date detection."""
    start = date(2026, 10, 1)
    current_stock = 100
    safety_reserve = 30
    daily_demands = [10.0] * 15  # 10 units/day for 15 days

    res = project_stock(
        facility_id="PHC-001",
        item_id=1,
        item_name="Paracetamol",
        unit="tablets",
        current_usable_stock=current_stock,
        daily_demands=daily_demands,
        safety_reserve=safety_reserve,
        start_date=start,
    )

    # Day 0: 100 - 10 = 90
    # Day 6: balance dips below safety reserve (30) -> Day 7 balance is 20 -> breach!
    assert res.projected_reserve_breach_date is not None
    assert res.projected_stockout_date is not None
    # Stockout happens when balance reaches 0 (Day 9 end or Day 10)
    assert res.projected_stockout_date == (start + timedelta(days=9)).isoformat()
    assert res.severity in (AlertSeverity.CRITICAL, AlertSeverity.WARNING)


def test_delivery_arriving_before_breach_prevents_breach():
    """Inbound replenishment before breach date maintains stock above reserve."""
    start = date(2026, 10, 1)
    current_stock = 50
    safety_reserve = 30
    daily_demands = [5.0] * 10  # 5 units/day

    # Delivery of 100 arrives on Day 2
    delivery_date = (start + timedelta(days=2)).isoformat()
    inbounds = {delivery_date: 100}

    res = project_stock(
        facility_id="PHC-001",
        item_id=1,
        item_name="Paracetamol",
        unit="tablets",
        current_usable_stock=current_stock,
        daily_demands=daily_demands,
        safety_reserve=safety_reserve,
        inbound_deliveries=inbounds,
        start_date=start,
    )

    assert res.projected_reserve_breach_date is None
    assert res.projected_stockout_date is None
    assert res.severity == AlertSeverity.INFO


def test_delivery_arriving_after_breach_records_breach_first():
    """Inbound replenishment arriving after breach date still flags the breach."""
    start = date(2026, 10, 1)
    current_stock = 40
    safety_reserve = 30
    daily_demands = [10.0] * 10  # 10 units/day. Day 1 -> 30, Day 2 -> 20 (Breach!)

    # Delivery arrives on Day 5 (after breach on Day 1/2)
    delivery_date = (start + timedelta(days=5)).isoformat()
    inbounds = {delivery_date: 200}

    res = project_stock(
        facility_id="PHC-001",
        item_id=1,
        item_name="Paracetamol",
        unit="tablets",
        current_usable_stock=current_stock,
        daily_demands=daily_demands,
        safety_reserve=safety_reserve,
        inbound_deliveries=inbounds,
        start_date=start,
    )

    assert res.projected_reserve_breach_date is not None
    breach_dt = date.fromisoformat(res.projected_reserve_breach_date)
    deliv_dt = date.fromisoformat(delivery_date)
    assert breach_dt < deliv_dt


def test_missing_or_zero_history_labeled_explicitly():
    """Missing or zero demand history must NOT claim infinite days of cover."""
    start = date(2026, 10, 1)
    current_stock = 200
    safety_reserve = 50
    daily_demands = [0.0] * 30  # No recorded demand

    res = project_stock(
        facility_id="PHC-001",
        item_id=1,
        item_name="Rare Medicine",
        unit="vials",
        current_usable_stock=current_stock,
        daily_demands=daily_demands,
        safety_reserve=safety_reserve,
        start_date=start,
        history_quality="zero_history",
        method="fallback_audit",
    )

    assert res.days_of_supply is None  # Cannot claim infinite days
    assert res.history_quality == "zero_history"
    assert "Insufficient consumption history" in res.reason


def test_zero_usable_stock_critical_severity():
    """When current usable stock is zero, severity must be CRITICAL immediately."""
    start = date(2026, 10, 1)
    res = project_stock(
        facility_id="PHC-001",
        item_id=1,
        item_name="Epinephrine",
        unit="vials",
        current_usable_stock=0,
        daily_demands=[2.0] * 10,
        safety_reserve=10,
        start_date=start,
    )

    assert res.severity == AlertSeverity.CRITICAL
    assert "depleted" in res.reason.lower()
