"""
Unit tests for evaluation tooling, chronological splitting, and deterministic scenario fixtures.

Tests:
- Chronological time-series splitting (strictly ordered, no random shuffling).
- All 10 canonical deterministic scenarios present and valid.
- Reproducible deterministic execution.
- Policy replay with batch expiry filtering and delivery receipt.
- Transfer constraint violation detection.
- Offline duplicate detection.
- Machine-readable evaluation report generation.
"""

import json
from datetime import date, datetime
from pathlib import Path

import pytest

from app.ml.evaluation.metrics import (
    calculate_mae,
    calculate_stockout_metrics,
    calculate_transfer_violations,
    calculate_wape,
)
from app.ml.evaluation.replay import PolicyReplayEngine
from app.ml.evaluation.runner import run_evaluation_suite
from app.ml.evaluation.scenarios import ScenarioFixture, get_deterministic_scenarios


def test_chronological_ordering_never_shuffled():
    scenarios = get_deterministic_scenarios()
    for scenario_id, fixture in scenarios.items():
        if fixture.history_records:
            history_dates = [datetime.strptime(r["date"], "%Y-%m-%d") for r in fixture.history_records]
            # Ensure history is strictly chronological (monotonically increasing)
            for i in range(len(history_dates) - 1):
                assert history_dates[i] <= history_dates[i + 1], (
                    f"Scenario {scenario_id} history is not chronologically ordered at index {i}"
                )

        if fixture.test_actual_records:
            test_dates = [datetime.strptime(r["date"], "%Y-%m-%d") for r in fixture.test_actual_records]
            for i in range(len(test_dates) - 1):
                assert test_dates[i] < test_dates[i + 1], (
                    f"Scenario {scenario_id} test records are not chronologically ordered at index {i}"
                )

            # Ensure chronological split boundary: max(history_date) < min(test_date)
            if fixture.history_records:
                assert history_dates[-1] < test_dates[0], (
                    f"Scenario {scenario_id} has future leak: history latest ({history_dates[-1]}) "
                    f"is not strictly before test earliest ({test_dates[0]})"
                )


def test_all_10_deterministic_scenarios_exist():
    expected_ids = {
        "normal_consumption",
        "demand_surge",
        "critically_low_stock_before_delivery",
        "delivery_arrives_before_breach",
        "no_safe_donor",
        "donor_at_protected_reserve",
        "expired_batch",
        "competing_recipients",
        "zero_sparse_history",
        "offline_duplicate_retry",
    }
    scenarios = get_deterministic_scenarios()
    assert set(scenarios.keys()) == expected_ids
    for s_id, s in scenarios.items():
        assert isinstance(s, ScenarioFixture)
        assert s.data_provenance == "synthetic_scenario"
        assert s.horizon_days > 0


def test_reproducible_evaluation_runs():
    engine = PolicyReplayEngine()
    scenarios = get_deterministic_scenarios()

    fixture = scenarios["normal_consumption"]
    res1 = engine.replay_scenario(fixture, allow_synthetic=False)
    res2 = engine.replay_scenario(fixture, allow_synthetic=False)

    assert res1.demand_mae == res2.demand_mae
    assert res1.demand_wape == res2.demand_wape
    assert res1.stockout_metrics == res2.stockout_metrics


def test_delivery_arrives_before_breach_scenario():
    engine = PolicyReplayEngine()
    scenarios = get_deterministic_scenarios()

    # Scenario 4: delivery of 100 units arrives on day 3, averting stockout
    fixture = scenarios["delivery_arrives_before_breach"]
    res = engine.replay_scenario(fixture, allow_synthetic=False)

    assert res.stockout_metrics["stockout_occurred"] is False
    assert res.stockout_metrics["stockout_days"] == 0


def test_critically_low_stock_before_delayed_delivery_scenario():
    engine = PolicyReplayEngine()
    scenarios = get_deterministic_scenarios()

    # Scenario 3: initial stock 24, usage 12/day, delivery arrives day 5 -> breaches on day 3
    fixture = scenarios["critically_low_stock_before_delivery"]
    res = engine.replay_scenario(fixture, allow_synthetic=False)

    assert res.stockout_metrics["stockout_occurred"] is True
    assert res.stockout_metrics["stockout_days"] > 0


def test_expired_batch_inventory_drop():
    engine = PolicyReplayEngine()
    scenarios = get_deterministic_scenarios()

    # Scenario 7: 90 units expire on day 2
    fixture = scenarios["expired_batch"]
    res = engine.replay_scenario(fixture, allow_synthetic=False)

    assert res.stockout_metrics["stockout_occurred"] is True


def test_donor_protected_reserve_violation():
    engine = PolicyReplayEngine()
    scenarios = get_deterministic_scenarios()

    # Scenario 6: transferring 30 units breaches protected reserve floor (55 - 30 = 25 < 50)
    fixture = scenarios["donor_at_protected_reserve"]
    res = engine.replay_scenario(fixture, allow_synthetic=False)

    assert len(res.transfer_violations) > 0
    assert any("Protected reserve breach" in v for v in res.transfer_violations)


def test_offline_duplicate_retry_deduplication():
    engine = PolicyReplayEngine()
    scenarios = get_deterministic_scenarios()

    # Scenario 10: 2 submissions with the same offline_sync_id
    fixture = scenarios["offline_duplicate_retry"]
    res = engine.replay_scenario(fixture, allow_synthetic=False)

    assert res.offline_exact_once_deduped_count == 1


def test_evaluation_suite_report_generation(tmp_path: Path):
    report_file = tmp_path / "eval_report_test.json"
    report = run_evaluation_suite(output_path=report_file)

    assert report_file.exists()
    with open(report_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "evaluation_run_id" in data
    assert data["scenario_set_version"] == "v1.0.0-phase1d"
    assert data["data_provenance"] == "synthetic_scenario"
    assert "summary_metrics" in data
    assert data["summary_metrics"]["total_scenarios_evaluated"] == 10
    assert "average_demand_mae" in data["summary_metrics"]
    assert "average_baseline_mae" in data["summary_metrics"]
    assert len(data["scenarios"]) == 10
