"""
Evaluation runner and reporter for Smart Health Sentinel.

Executes all 10 canonical deterministic scenarios safely in-memory:
- Evaluates forecasting models against simple trailing baselines.
- Calculates MAE, WAPE, stockout recall, precision, lead time, violations.
- Generates a machine-readable JSON report with a unique evaluation run ID.
- Prints human-readable summary table.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.ml.evaluation.replay import PolicyReplayEngine, ReplayResult
from app.ml.evaluation.scenarios import get_deterministic_scenarios
from app.ml.provider import SmartHealthForecastProvider

logger = logging.getLogger(__name__)


def run_evaluation_suite(
    output_path: str | Path | None = None,
    allow_synthetic_fallbacks: bool = True,
) -> dict[str, Any]:
    """Execute the full deterministic scenario evaluation suite.

    Safe: Operates completely on in-memory deterministic fixtures.
    Does NOT touch, modify, or reset any live database.
    """
    run_id = f"eval-run-{uuid.uuid4().hex[:12]}"
    run_timestamp = datetime.now(timezone.utc).isoformat()

    scenarios = get_deterministic_scenarios()
    provider = SmartHealthForecastProvider()
    engine = PolicyReplayEngine(provider=provider)

    scenario_results: list[dict[str, Any]] = []

    total_scenarios = len(scenarios)
    mae_sum = 0.0
    wape_sum = 0.0
    base_mae_sum = 0.0
    base_wape_sum = 0.0
    total_stockout_days = 0
    total_violations = 0
    total_deduped_offline_events = 0

    print("=" * 80)
    print(f"  Smart Health Sentinel — Deterministic Policy Evaluation Suite")
    print(f"  Run ID       : {run_id}")
    print(f"  Timestamp    : {run_timestamp}")
    print(f"  Scenarios    : {total_scenarios} deterministic fixtures")
    print(f"  Provenance   : synthetic_scenario (Clearly labeled; not real PHC impact)")
    print("=" * 80)
    print(f"{'Scenario ID':<35} | {'Model MAE':<10} | {'Base MAE':<10} | {'Stockout Alert':<14} | {'Violations'}")
    print("-" * 80)

    for scenario_id, fixture in scenarios.items():
        # Scenarios allow synthetic fallback except where testing strict insufficient history
        allow_synth = allow_synthetic_fallbacks and (scenario_id != "zero_sparse_history")

        res: ReplayResult = engine.replay_scenario(fixture, allow_synthetic=allow_synth)

        mae_sum += res.demand_mae
        wape_sum += res.demand_wape
        base_mae_sum += res.baseline_mae
        base_wape_sum += res.baseline_wape
        total_stockout_days += res.stockout_metrics["stockout_days"]
        total_violations += len(res.transfer_violations)
        total_deduped_offline_events += res.offline_exact_once_deduped_count

        alert_str = "BREACH" if res.stockout_metrics["stockout_occurred"] else "SAFE"
        if res.stockout_metrics["stockout_alerted"]:
            alert_str += f" (Lead:{res.stockout_metrics['warning_lead_time_days']}d)"

        print(
            f"{res.scenario_id:<35} | "
            f"{res.demand_mae:<10.2f} | "
            f"{res.baseline_mae:<10.2f} | "
            f"{alert_str:<14} | "
            f"{len(res.transfer_violations)}"
        )

        scenario_dict = {
            "scenario_id": res.scenario_id,
            "scenario_name": res.scenario_name,
            "data_provenance": res.data_provenance,
            "horizon_days": res.horizon_days,
            "model_method": res.model_method,
            "model_version": res.model_version,
            "baseline_method": res.baseline_method,
            "demand_mae": res.demand_mae,
            "demand_wape": res.demand_wape,
            "baseline_mae": res.baseline_mae,
            "baseline_wape": res.baseline_wape,
            "stockout_metrics": res.stockout_metrics,
            "baseline_stockout_metrics": res.baseline_stockout_metrics,
            "transfer_violations": res.transfer_violations,
            "offline_exact_once_deduped_count": res.offline_exact_once_deduped_count,
            "limitations": res.limitations,
        }
        scenario_results.append(scenario_dict)

    print("-" * 80)
    avg_mae = round(mae_sum / total_scenarios, 3)
    avg_base_mae = round(base_mae_sum / total_scenarios, 3)
    avg_wape = round(wape_sum / total_scenarios, 4)
    avg_base_wape = round(base_wape_sum / total_scenarios, 4)

    print(f"Overall Average Model MAE    : {avg_mae}")
    print(f"Overall Average Baseline MAE : {avg_base_mae}")
    print(f"Overall Average Model WAPE   : {avg_wape}")
    print(f"Overall Average Baseline WAPE: {avg_base_wape}")
    print(f"Total Cumulative Stockout Days: {total_stockout_days}")
    print(f"Total Transfer Violations Flagged: {total_violations}")
    print(f"Offline Exact-Once Tests Verified: {total_deduped_offline_events} (Marked owned by PWA test suite)")
    print("=" * 80)

    report: dict[str, Any] = {
        "evaluation_run_id": run_id,
        "scenario_set_version": "v1.0.0-phase1d",
        "generated_at": run_timestamp,
        "data_provenance": "synthetic_scenario",
        "disclaimer": (
            "Synthetic scenario evaluation validates algorithmic implementation "
            "under controlled boundary conditions; it does not prove real-world PHC impact."
        ),
        "offline_sync_test_lane_note": "Offline exact-once deduplication is owned by PWA test suite (phc-app).",
        "summary_metrics": {
            "total_scenarios_evaluated": total_scenarios,
            "average_demand_mae": avg_mae,
            "average_baseline_mae": avg_base_mae,
            "average_demand_wape": avg_wape,
            "average_baseline_wape": avg_base_wape,
            "total_stockout_days": total_stockout_days,
            "total_transfer_violations": total_violations,
            "offline_deduped_events": total_deduped_offline_events,
        },
        "scenarios": scenario_results,
    }

    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\n[OK] Machine-readable report saved to: {out_p.resolve()}")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Smart Health Sentinel deterministic evaluation suite.")
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="backend/evaluation_report.json",
        help="Path to save machine-readable evaluation report JSON.",
    )
    args = parser.parse_args()
    run_evaluation_suite(output_path=args.output)


if __name__ == "__main__":
    main()
