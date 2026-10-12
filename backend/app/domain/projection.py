"""
Stock projection engine across planning horizon.
Calculates daily depletion curves, reserve breach dates, and stockout events
using forecast demand and dependable inbound replenishment.
"""

from __future__ import annotations
from datetime import date, timedelta
from typing import Optional

from app.domain.models import (
    AlertSeverity,
    ProjectionDailyPoint,
    StockProjectionResult,
)


def project_stock(
    facility_id: str,
    item_id: int,
    item_name: str,
    unit: str,
    current_usable_stock: int,
    daily_demands: list[float],
    safety_reserve: int,
    inbound_deliveries: Optional[dict[str, int]] = None,
    start_date: Optional[date] = None,
    history_quality: str = "sufficient",
    data_source: str = "database",
    method: str = "deterministic_forecast",
) -> StockProjectionResult:
    """
    Project inventory balance day-by-day over the planning horizon.

    Rules:
    - Never silently treats missing history as 0 or infinite cover.
    - Tracks reserve breach (balance < safety_reserve) and stockout (balance <= 0).
    - Inbound deliveries on a given date arrive and add to balance.
    """
    if start_date is None:
        start_date = date.today()

    if inbound_deliveries is None:
        inbound_deliveries = {}

    horizon_days = len(daily_demands)
    if horizon_days == 0:
        # Default 30 days if no demand points given
        horizon_days = 30
        daily_demands = [0.0] * 30

    daily_points: list[ProjectionDailyPoint] = []
    current_balance = float(max(0, current_usable_stock))

    reserve_breach_date: Optional[str] = None
    stockout_date: Optional[str] = None

    total_demand = sum(daily_demands)
    avg_demand = total_demand / horizon_days if horizon_days > 0 else 0.0

    # Calculate days of supply
    if history_quality in ("insufficient_history", "zero_history") and avg_demand <= 0.0:
        days_of_supply = None
    elif avg_demand > 0.0:
        days_of_supply = round(current_usable_stock / avg_demand, 1)
    else:
        days_of_supply = None

    for day_idx in range(horizon_days):
        current_day = start_date + timedelta(days=day_idx)
        date_str = current_day.isoformat()

        demand_today = max(0.0, daily_demands[day_idx])
        replenishment_today = max(0, inbound_deliveries.get(date_str, 0))

        # Balance at end of day
        ending_balance = current_balance - demand_today + replenishment_today

        is_breached = ending_balance < float(safety_reserve)
        is_stockout = ending_balance <= 0.0

        if is_breached and reserve_breach_date is None:
            reserve_breach_date = date_str

        if is_stockout and stockout_date is None:
            stockout_date = date_str

        daily_points.append(
            ProjectionDailyPoint(
                date=date_str,
                projected_demand=round(demand_today, 2),
                inbound_replenishment=replenishment_today,
                ending_stock=round(max(0.0, ending_balance), 2),
                is_breached=is_breached,
                is_stockout=is_stockout,
            )
        )

        # Roll over balance (physical inventory cannot go below zero)
        current_balance = max(0.0, ending_balance)

    # Determine severity and plain-language reason
    if current_usable_stock == 0:
        severity = AlertSeverity.CRITICAL
        reason = "Stock is currently completely depleted (0 units on hand)."
    elif stockout_date is not None:
        days_to_stockout = (
            date.fromisoformat(stockout_date) - start_date
        ).days
        if days_to_stockout <= 7:
            severity = AlertSeverity.CRITICAL
            reason = f"Imminent stockout projected on {stockout_date} ({days_to_stockout} days remaining)."
        else:
            severity = AlertSeverity.WARNING
            reason = f"Stockout projected on {stockout_date} ({days_to_stockout} days remaining)."
    elif reserve_breach_date is not None:
        days_to_breach = (
            date.fromisoformat(reserve_breach_date) - start_date
        ).days
        if days_to_breach <= 3:
            severity = AlertSeverity.CRITICAL
            reason = f"Safety reserve breach imminent on {reserve_breach_date} ({days_to_breach} days remaining)."
        else:
            severity = AlertSeverity.WARNING
            reason = f"Safety reserve breach projected on {reserve_breach_date}."
    elif history_quality in ("insufficient_history", "zero_history"):
        severity = AlertSeverity.WARNING
        reason = (
            "Insufficient consumption history available to reliably forecast runout. "
            "Manual facility audit recommended."
        )
    else:
        severity = AlertSeverity.INFO
        reason = (
            f"Stock adequate for the {horizon_days}-day planning horizon. "
            f"Estimated {days_of_supply} days of cover."
        )

    return StockProjectionResult(
        facility_id=facility_id,
        item_id=item_id,
        item_name=item_name,
        unit=unit,
        current_usable_stock=current_usable_stock,
        safety_reserve=safety_reserve,
        planning_horizon_days=horizon_days,
        days_of_supply=days_of_supply,
        projected_reserve_breach_date=reserve_breach_date,
        projected_stockout_date=stockout_date,
        severity=severity,
        reason=reason,
        history_quality=history_quality,
        data_source=data_source,
        method=method,
        daily_curve=daily_points,
    )
