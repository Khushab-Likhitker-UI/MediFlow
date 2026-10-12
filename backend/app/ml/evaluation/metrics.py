"""
Evaluation metrics for demand forecasting and inventory stockout simulation.

Computes:
- MAE (Mean Absolute Error)
- WAPE (Weighted Absolute Percentage Error)
- Stockout-event Recall and False-Alert / Precision rates
- Warning Lead Time (days in advance stockout is predicted)
- Stockout-days in policy replay
- Transfer constraint violations
"""

from __future__ import annotations

from typing import Any


def calculate_mae(actual: list[float], predicted: list[float]) -> float:
    """Compute Mean Absolute Error between actual and predicted sequences."""
    if not actual or not predicted or len(actual) != len(predicted):
        return 0.0
    errors = [abs(a - p) for a, p in zip(actual, predicted)]
    return round(float(sum(errors) / len(errors)), 3)


def calculate_wape(actual: list[float], predicted: list[float]) -> float:
    """Compute Weighted Absolute Percentage Error (WAPE).

    Formula: sum(|actual - predicted|) / sum(actual)
    Safe handling for zero total demand.
    """
    if not actual or not predicted or len(actual) != len(predicted):
        return 0.0
    abs_err_sum = sum(abs(a - p) for a, p in zip(actual, predicted))
    actual_sum = sum(actual)
    if actual_sum == 0:
        return 0.0 if abs_err_sum == 0 else 1.0
    return round(float(abs_err_sum / actual_sum), 4)


def calculate_stockout_metrics(
    actual_stock_trajectory: list[float],
    predicted_stock_trajectory: list[float],
) -> dict[str, Any]:
    """Compute stockout event recall, precision, warning lead time, and stockout days.

    Parameters
    ----------
    actual_stock_trajectory : list[float]
        Simulated physical inventory levels over time.
    predicted_stock_trajectory : list[float]
        Forecast-driven expected inventory levels over time.

    Returns
    -------
    dict
        ``{
            "stockout_occurred": bool,
            "stockout_alerted": bool,
            "true_positive": bool,
            "false_positive": bool,
            "false_negative": bool,
            "recall": float,
            "precision": float,
            "false_alert_rate": float,
            "warning_lead_time_days": int,
            "stockout_days": int,
        }``
    """
    n = min(len(actual_stock_trajectory), len(predicted_stock_trajectory))
    if n == 0:
        return {
            "stockout_occurred": False,
            "stockout_alerted": False,
            "true_positive": False,
            "false_positive": False,
            "false_negative": False,
            "recall": 1.0,
            "precision": 1.0,
            "false_alert_rate": 0.0,
            "warning_lead_time_days": 0,
            "stockout_days": 0,
        }

    # Find first actual breach day (stock <= 0)
    actual_stockout_day: int | None = None
    stockout_days_count = 0
    for day_idx in range(n):
        if actual_stock_trajectory[day_idx] <= 0:
            if actual_stockout_day is None:
                actual_stockout_day = day_idx + 1  # 1-indexed day
            stockout_days_count += 1

    # Find first predicted breach day (predicted <= 0)
    predicted_stockout_day: int | None = None
    for day_idx in range(n):
        if predicted_stock_trajectory[day_idx] <= 0:
            if predicted_stockout_day is None:
                predicted_stockout_day = day_idx + 1
            break

    stockout_occurred = actual_stockout_day is not None
    stockout_alerted = predicted_stockout_day is not None

    if stockout_occurred and stockout_alerted:
        tp = True
        fp = False
        fn = False
        lead_time = max(0, actual_stockout_day - predicted_stockout_day)
    elif stockout_occurred and not stockout_alerted:
        tp = False
        fp = False
        fn = True
        lead_time = 0
    elif not stockout_occurred and stockout_alerted:
        tp = False
        fp = True
        fn = False
        lead_time = 0
    else:
        tp = False
        fp = False
        fn = False
        lead_time = 0

    if stockout_occurred:
        recall = 1.0 if tp else 0.0
    else:
        recall = 1.0

    if stockout_alerted:
        precision = 1.0 if tp else 0.0
        false_alert_rate = 1.0 if fp else 0.0
    else:
        precision = 1.0 if not stockout_occurred else 0.0
        false_alert_rate = 0.0

    return {
        "stockout_occurred": stockout_occurred,
        "stockout_alerted": stockout_alerted,
        "actual_first_stockout_day": actual_stockout_day,
        "predicted_first_stockout_day": predicted_stockout_day,
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "recall": recall,
        "precision": precision,
        "false_alert_rate": false_alert_rate,
        "warning_lead_time_days": lead_time,
        "stockout_days": stockout_days_count,
    }


def calculate_transfer_violations(
    donor_facility: str,
    donor_current_stock: int,
    donor_protected_reserve: int,
    transfer_quantity: int,
    batch_expiry_is_valid: bool = True,
) -> list[str]:
    """Check transfer business constraints and return any violations.

    Constraints:
    1. Transfer quantity must be > 0.
    2. Donor cannot transfer expired stock.
    3. Transfer cannot breach donor's protected reserve:
       (donor_current_stock - transfer_quantity) >= donor_protected_reserve.
    """
    violations: list[str] = []

    if transfer_quantity <= 0:
        violations.append(f"Invalid transfer quantity ({transfer_quantity}): must be greater than 0.")

    if not batch_expiry_is_valid:
        violations.append(f"Safety violation: donor {donor_facility} attempted to transfer an expired batch.")

    remaining_donor_stock = donor_current_stock - transfer_quantity
    if remaining_donor_stock < donor_protected_reserve:
        deficit = donor_protected_reserve - remaining_donor_stock
        violations.append(
            f"Protected reserve breach: transfer of {transfer_quantity} leaves donor {donor_facility} "
            f"with {remaining_donor_stock} units (below protected reserve of {donor_protected_reserve} by {deficit})."
        )

    return violations
