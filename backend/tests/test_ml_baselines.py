"""
Unit tests for simple transparent baselines and uncertainty bounds.

Tests:
- TrailingMeanBaseline
- SeasonalNaiveBaseline
- Nominal uncertainty bounds (clamped >= 0)
- All-zero series
- High spike series
- Baseline comparison metrics
"""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.ml.baseline import SeasonalNaiveBaseline, TrailingMeanBaseline
from app.ml.evaluation.metrics import calculate_mae, calculate_wape


def test_trailing_mean_baseline_constant_series():
    ref_date = date(2026, 10, 1)
    df = pd.DataFrame({
        "ds": [ref_date - timedelta(days=30 - i) for i in range(30)],
        "y": [20.0] * 30,
    })
    baseline = TrailingMeanBaseline(window_days=14)
    forecast = baseline.fit_predict(df, horizon_days=7)

    assert len(forecast) == 7
    for pt in forecast:
        assert pt["predicted_quantity"] == 20.0
        assert pt["lower_bound"] <= 20.0
        assert pt["upper_bound"] >= 20.0
        assert pt["lower_bound"] >= 0.0


def test_trailing_mean_baseline_empty_series():
    df = pd.DataFrame({"ds": pd.Series(dtype="datetime64[ns]"), "y": pd.Series(dtype="float64")})
    baseline = TrailingMeanBaseline(window_days=14)
    forecast = baseline.fit_predict(df, horizon_days=5)

    assert len(forecast) == 5
    for pt in forecast:
        assert pt["predicted_quantity"] == 0.0
        assert pt["lower_bound"] == 0.0
        assert pt["upper_bound"] == 0.0


def test_trailing_mean_bounds_clamped_at_zero():
    ref_date = date(2026, 10, 1)
    # High variance around a low mean
    df = pd.DataFrame({
        "ds": [ref_date - timedelta(days=10 - i) for i in range(10)],
        "y": [1.0, 15.0, 0.0, 20.0, 1.0, 18.0, 0.0, 12.0, 1.0, 10.0],
    })
    baseline = TrailingMeanBaseline(window_days=7, z_score=2.0)
    forecast = baseline.fit_predict(df, horizon_days=5)

    for pt in forecast:
        assert pt["lower_bound"] >= 0.0, "Uncertainty lower bound must never be negative for consumption"
        assert pt["lower_bound"] <= pt["predicted_quantity"]
        assert pt["upper_bound"] >= pt["predicted_quantity"]


def test_seasonal_naive_baseline_weekly_pattern():
    ref_date = date(2026, 10, 1)
    # Mon=10, Tue=20, Wed=30, Thu=40, Fri=50, Sat=5, Sun=0 pattern repeating for 4 weeks (28 days)
    weekday_pattern = [10.0, 20.0, 30.0, 40.0, 50.0, 5.0, 0.0]
    dates = [ref_date - timedelta(days=28 - i) for i in range(28)]
    values = [weekday_pattern[dt.weekday()] for dt in dates]
    df = pd.DataFrame({"ds": dates, "y": values})

    seasonal = SeasonalNaiveBaseline(cycle_length=7, weeks_window=4)
    forecast = seasonal.fit_predict(df, horizon_days=7)

    assert len(forecast) == 7
    for pt in forecast:
        fc_date = date.fromisoformat(pt["date"])
        expected_val = weekday_pattern[fc_date.weekday()]
        assert pt["predicted_quantity"] == expected_val


def test_seasonal_naive_short_history_fallback():
    ref_date = date(2026, 10, 1)
    # Only 4 days of history (< 7 days)
    df = pd.DataFrame({
        "ds": [ref_date - timedelta(days=4 - i) for i in range(4)],
        "y": [10.0, 12.0, 14.0, 16.0],
    })
    seasonal = SeasonalNaiveBaseline(cycle_length=7)
    forecast = seasonal.fit_predict(df, horizon_days=5)

    assert len(forecast) == 5
    # Should cleanly fall back to trailing mean
    for pt in forecast:
        assert pt["predicted_quantity"] > 0.0


def test_metric_calculations_mae_and_wape():
    actual = [10.0, 20.0, 30.0, 40.0]
    predicted = [12.0, 18.0, 33.0, 37.0]

    # errors: 2, 2, 3, 3 -> sum = 10 -> MAE = 2.5
    mae = calculate_mae(actual, predicted)
    assert mae == 2.5

    # actual sum = 100 -> WAPE = 10 / 100 = 0.10
    wape = calculate_wape(actual, predicted)
    assert wape == 0.10


def test_metric_calculations_zero_actual():
    actual = [0.0, 0.0, 0.0]
    predicted = [0.0, 0.0, 0.0]
    assert calculate_mae(actual, predicted) == 0.0
    assert calculate_wape(actual, predicted) == 0.0
