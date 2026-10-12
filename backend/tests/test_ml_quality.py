"""
Unit tests for ML history quality assessment and data cleansing.

Tests:
- Empty history (None, empty list, empty DataFrame, bad columns)
- Sparse history (< 30 observations)
- Gaps in date continuity
- Negative and non-finite quantities
- Stale data detection
- All-zero demand and extreme spikes
"""

from datetime import date, datetime, timedelta

import pandas as pd
import pytest

from app.ml.quality import HistoryQualityAssessor, QualityAssessmentResult


def test_empty_history_none():
    assessor = HistoryQualityAssessor(min_history_days=30)
    res = assessor.assess_and_clean(None)
    assert isinstance(res, QualityAssessmentResult)
    assert res.total_rows == 0
    assert res.cleaned_rows == 0
    assert not res.sufficient
    assert res.cleaned_df.empty
    assert any("Empty history" in lim for lim in res.limitations)


def test_empty_history_empty_list():
    assessor = HistoryQualityAssessor(min_history_days=30)
    res = assessor.assess_and_clean([])
    assert res.total_rows == 0
    assert not res.sufficient
    assert any("Empty history" in lim for lim in res.limitations)


def test_empty_history_empty_dataframe():
    assessor = HistoryQualityAssessor(min_history_days=30)
    res = assessor.assess_and_clean(pd.DataFrame())
    assert res.total_rows == 0
    assert not res.sufficient


def test_sparse_history_under_threshold():
    ref_date = date(2026, 10, 1)
    assessor = HistoryQualityAssessor(min_history_days=30, reference_date=ref_date)
    records = [
        {"ds": (ref_date - timedelta(days=i)).strftime("%Y-%m-%d"), "y": 10.0}
        for i in range(1, 15)  # only 14 days < 30
    ]
    res = assessor.assess_and_clean(records)
    assert res.total_rows == 14
    assert res.cleaned_rows == 14
    assert not res.sufficient
    assert any("Insufficient observations" in lim for lim in res.limitations)


def test_gaps_in_history():
    ref_date = date(2026, 10, 1)
    assessor = HistoryQualityAssessor(min_history_days=30, reference_date=ref_date)
    # 40 rows over an 80-day span (40 missing days)
    records = [
        {"ds": (ref_date - timedelta(days=i * 2)).strftime("%Y-%m-%d"), "y": 12.0}
        for i in range(40)
    ]
    res = assessor.assess_and_clean(records)
    assert res.cleaned_rows == 40
    assert res.missing_days == 39  # span is 79 days, 40 points -> 39 gaps
    assert res.coverage_ratio < 0.6
    assert any("Gaps in history" in lim for lim in res.limitations)


def test_negative_quantities_clamped():
    ref_date = date(2026, 10, 1)
    assessor = HistoryQualityAssessor(min_history_days=10, reference_date=ref_date)
    records = [
        {"ds": (ref_date - timedelta(days=i)).strftime("%Y-%m-%d"), "y": -5.0 if i % 2 == 0 else 10.0}
        for i in range(1, 15)
    ]
    res = assessor.assess_and_clean(records)
    assert res.has_negative_values
    assert (res.cleaned_df["y"] >= 0.0).all()
    assert any("Negative consumption" in lim for lim in res.limitations)


def test_non_finite_and_nan_values_dropped():
    ref_date = date(2026, 10, 1)
    assessor = HistoryQualityAssessor(min_history_days=5, reference_date=ref_date)
    records = [
        {"ds": "2026-09-01", "y": "NaN"},
        {"ds": "2026-09-02", "y": None},
        {"ds": "2026-09-03", "y": "invalid_string"},
        {"ds": "2026-09-04", "y": 15.0},
        {"ds": "2026-09-05", "y": 20.0},
    ]
    res = assessor.assess_and_clean(records)
    assert res.has_non_finite_values
    assert res.cleaned_rows == 2
    assert res.cleaned_df["y"].tolist() == [15.0, 20.0]


def test_stale_data_detection():
    ref_date = date(2026, 10, 1)
    assessor = HistoryQualityAssessor(min_history_days=30, stale_days_threshold=60, reference_date=ref_date)
    # History ended 100 days ago (> 60 days stale)
    stale_start = ref_date - timedelta(days=100)
    records = [
        {"ds": (stale_start - timedelta(days=i)).strftime("%Y-%m-%d"), "y": 10.0}
        for i in range(35)
    ]
    res = assessor.assess_and_clean(records)
    assert res.cleaned_rows == 35
    assert res.stale
    assert not res.sufficient  # stale data cannot be considered sufficient
    assert any("Stale history" in lim for lim in res.limitations)


def test_all_zero_demand_handling():
    ref_date = date(2026, 10, 1)
    assessor = HistoryQualityAssessor(min_history_days=30, reference_date=ref_date)
    records = [
        {"ds": (ref_date - timedelta(days=i)).strftime("%Y-%m-%d"), "y": 0.0}
        for i in range(1, 35)
    ]
    res = assessor.assess_and_clean(records)
    assert res.cleaned_rows == 34
    assert res.sufficient
    assert (res.cleaned_df["y"] == 0.0).all()


def test_high_spike_demand_handling():
    ref_date = date(2026, 10, 1)
    assessor = HistoryQualityAssessor(min_history_days=30, reference_date=ref_date)
    records = [
        {"ds": (ref_date - timedelta(days=i)).strftime("%Y-%m-%d"), "y": 10000.0 if i == 5 else 10.0}
        for i in range(1, 35)
    ]
    res = assessor.assess_and_clean(records)
    assert res.cleaned_rows == 34
    assert res.sufficient
    assert 10000.0 in res.cleaned_df["y"].values
