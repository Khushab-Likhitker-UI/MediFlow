"""
Chronological policy replay and simulation engine.

Runs forward daily simulation across deterministic scenario fixtures:
- Strictly chronological train/test split.
- Usable inventory accounting (expiry date filtering).
- Scheduled delivery receipt.
- Forecast demand vs actual demand trajectory.
- Side-by-side evaluation against simple baseline.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from app.ml.baseline import TrailingMeanBaseline
from app.ml.evaluation.metrics import (
    calculate_mae,
    calculate_stockout_metrics,
    calculate_transfer_violations,
    calculate_wape,
)
from app.ml.evaluation.scenarios import ScenarioFixture
from app.ml.provider import SmartHealthForecastProvider


@dataclass(frozen=True)
class ReplayResult:
    """Evaluation result for a single scenario under policy replay."""
    scenario_id: str
    scenario_name: str
    data_provenance: str
    model_method: str
    model_version: str
    baseline_method: str
    horizon_days: int
    demand_mae: float
    demand_wape: float
    baseline_mae: float
    baseline_wape: float
    stockout_metrics: dict[str, Any]
    baseline_stockout_metrics: dict[str, Any]
    transfer_violations: list[str]
    offline_exact_once_deduped_count: int
    limitations: list[str]


class PolicyReplayEngine:
    """Simulates daily facility inventory operations under forecasting policies."""

    def __init__(self, provider: SmartHealthForecastProvider | None = None) -> None:
        self.provider = provider or SmartHealthForecastProvider()
        self.simple_baseline = TrailingMeanBaseline(window_days=7)

    def replay_scenario(
        self,
        scenario: ScenarioFixture,
        allow_synthetic: bool = False,
    ) -> ReplayResult:
        """Execute chronological simulation for a single scenario fixture."""
        horizon = scenario.horizon_days

        # 1. Prepare chronological training history (no shuffling)
        hist_df = pd.DataFrame(scenario.history_records)
        if not hist_df.empty and "date" in hist_df.columns:
            hist_df["ds"] = pd.to_datetime(hist_df["date"])
            hist_df["y"] = hist_df["quantity_consumed"].astype(float)
            hist_df = hist_df.sort_values(by="ds").reset_index(drop=True)

        # 2. Run Proposed Forecast Provider
        forecast_res = self.provider.forecast_item_demand(
            item_id=scenario.item_id,
            item_name=scenario.item_name,
            current_quantity=scenario.initial_stock,
            horizon_days=horizon,
            history_override=hist_df,
            allow_synthetic=allow_synthetic,
            data_source_label=scenario.data_provenance,
        )

        # 3. Run Defined Simple Baseline (Trailing Mean)
        baseline_pts = self.simple_baseline.fit_predict(
            df=hist_df,
            horizon_days=horizon,
            date_col="ds",
            val_col="y",
        )

        # 4. Extract actual and predicted demands
        actual_demands = [float(r["quantity_consumed"]) for r in scenario.test_actual_records[:horizon]]
        model_preds = [p.predicted_quantity for p in forecast_res.forecasted_demand[:horizon]]
        base_preds = [p["predicted_quantity"] for p in baseline_pts[:horizon]]

        # Pad if needed
        while len(model_preds) < len(actual_demands):
            model_preds.append(0.0)
        while len(base_preds) < len(actual_demands):
            base_preds.append(0.0)

        # Compute Demand Accuracy Metrics
        demand_mae = calculate_mae(actual_demands, model_preds)
        demand_wape = calculate_wape(actual_demands, model_preds)
        base_mae = calculate_mae(actual_demands, base_preds)
        base_wape = calculate_wape(actual_demands, base_preds)

        # 5. Simulate Inventory Balance Day by Day
        # Tracking usable batches, deliveries, and consumption
        actual_stock_trajectory: list[float] = []
        model_stock_trajectory: list[float] = []
        base_stock_trajectory: list[float] = []

        delivery_map = {d.day_offset: d.quantity for d in scenario.deliveries}

        # Initialize batches state
        batches_state = [
            {"batch_number": b.batch_number, "quantity": b.quantity, "expiry_date": b.expiry_date}
            for b in scenario.batches
        ]

        curr_actual_stock = float(scenario.initial_stock)
        curr_model_stock = float(scenario.initial_stock)
        curr_base_stock = float(scenario.initial_stock)

        sim_start_date = datetime.strptime(scenario.test_actual_records[0]["date"], "%Y-%m-%d")

        for day_idx in range(len(actual_demands)):
            day_num = day_idx + 1
            current_sim_date = (sim_start_date + timedelta(days=day_idx)).strftime("%Y-%m-%d")

            # Check for batch expiries on this day
            usable_physical_stock = 0.0
            for b in batches_state:
                if b["expiry_date"] > current_sim_date:
                    usable_physical_stock += b["quantity"]
            curr_actual_stock = min(curr_actual_stock, usable_physical_stock)

            # Receive deliveries on this day
            deliv_qty = float(delivery_map.get(day_num, 0))
            if deliv_qty > 0:
                batches_state.append({
                    "batch_number": f"DELIVERY-DAY-{day_num}",
                    "quantity": int(deliv_qty),
                    "expiry_date": (sim_start_date + timedelta(days=365)).strftime("%Y-%m-%d"),
                })
            curr_actual_stock += deliv_qty
            curr_model_stock += deliv_qty
            curr_base_stock += deliv_qty

            # Deduct consumption
            curr_actual_stock -= actual_demands[day_idx]
            curr_model_stock -= model_preds[day_idx]
            curr_base_stock -= base_preds[day_idx]

            actual_stock_trajectory.append(round(curr_actual_stock, 1))
            model_stock_trajectory.append(round(curr_model_stock, 1))
            base_stock_trajectory.append(round(curr_base_stock, 1))

        stockout_metrics = calculate_stockout_metrics(actual_stock_trajectory, model_stock_trajectory)
        base_stockout_metrics = calculate_stockout_metrics(actual_stock_trajectory, base_stock_trajectory)

        # 6. Evaluate Transfer Constraints if scenario has donor evaluation
        transfer_violations: list[str] = []
        if scenario.scenario_id == "donor_at_protected_reserve":
            donor = scenario.network_donors[0]
            # Transfer proposal of 30 units
            violations = calculate_transfer_violations(
                donor_facility=donor["facility_id"],
                donor_current_stock=donor["current_stock"],
                donor_protected_reserve=donor["protected_reserve"],
                transfer_quantity=30,
                batch_expiry_is_valid=True,
            )
            transfer_violations.extend(violations)
        elif scenario.scenario_id == "no_safe_donor":
            # Testing transfer proposal against all donors
            for donor in scenario.network_donors:
                violations = calculate_transfer_violations(
                    donor_facility=donor["facility_id"],
                    donor_current_stock=donor["current_stock"],
                    donor_protected_reserve=donor["protected_reserve"],
                    transfer_quantity=15,
                    batch_expiry_is_valid=True,
                )
                transfer_violations.extend(violations)

        # 7. Evaluate Offline Deduplication if scenario has offline retries
        dedup_count = 0
        if scenario.offline_duplicate_payloads:
            seen_ids = set()
            for payload in scenario.offline_duplicate_payloads:
                sync_id = payload.get("offline_sync_id")
                if sync_id in seen_ids:
                    dedup_count += 1
                else:
                    seen_ids.add(sync_id)

        return ReplayResult(
            scenario_id=scenario.scenario_id,
            scenario_name=scenario.name,
            data_provenance=scenario.data_provenance,
            model_method=forecast_res.method,
            model_version=forecast_res.model_version,
            baseline_method="trailing_mean_7d",
            horizon_days=horizon,
            demand_mae=demand_mae,
            demand_wape=demand_wape,
            baseline_mae=base_mae,
            baseline_wape=base_wape,
            stockout_metrics=stockout_metrics,
            baseline_stockout_metrics=base_stockout_metrics,
            transfer_violations=transfer_violations,
            offline_exact_once_deduped_count=dedup_count,
            limitations=forecast_res.limitations,
        )
