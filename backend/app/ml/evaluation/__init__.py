"""
Evaluation and scenario simulation package for Smart Health Sentinel.

Provides deterministic test fixtures, chronological evaluation routines,
policy replay simulation, and metric reporting.
"""

from app.ml.evaluation.metrics import (
    calculate_mae,
    calculate_wape,
    calculate_stockout_metrics,
    calculate_transfer_violations,
)
from app.ml.evaluation.scenarios import get_deterministic_scenarios, ScenarioFixture
from app.ml.evaluation.replay import PolicyReplayEngine, ReplayResult
from app.ml.evaluation.runner import run_evaluation_suite

__all__ = [
    "calculate_mae",
    "calculate_wape",
    "calculate_stockout_metrics",
    "calculate_transfer_violations",
    "get_deterministic_scenarios",
    "ScenarioFixture",
    "PolicyReplayEngine",
    "ReplayResult",
    "run_evaluation_suite",
]
