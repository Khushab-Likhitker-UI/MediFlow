"""
Unit tests for ForecastProvider contract, provenance labeling, and anomaly review signals.

Verifies:
- Frozen dataclass structure and immutability (Phase 0 contract).
- Real history path vs fallback baseline vs synthetic demonstration path.
- Proper error handling when synthetic fallback is disabled.
- Human review signals in anomaly flags (no outbreak/misconduct labels).
- Footfall async methods and bounds.
"""

from datetime import date, timedelta

import pandas as pd
import pytest

from app.ml.provider import (
    AnomalyFlag,
    ForecastPoint,
    ForecastProvider,
    ForecastResult,
    HistoryQuality,
    SmartHealthForecastProvider,
    get_forecast_provider,
)


def test_forecast_point_dataclass_frozen():
    pt = ForecastPoint(date="2026-10-15", predicted_quantity=25.0, lower_bound=20.0, upper_bound=30.0)
    assert pt.date == "2026-10-15"
    assert pt.predicted_quantity == 25.0
    with pytest.raises(Exception):
        pt.predicted_quantity = 30.0  # dataclass is frozen


def test_forecast_result_dataclass_frozen():
    quality = HistoryQuality(total_rows=30, date_range_start="2026-09-01", date_range_end="2026-09-30", missing_days=0, sufficient=True)
    res = ForecastResult(
        item_id=1,
        item_name="Paracetamol",
        forecasted_demand=[ForecastPoint("2026-10-01", 10.0, 8.0, 12.0)],
        anomaly_flags=None,
        method="seasonal_naive",
        data_source="database",
        history_quality=quality,
        model_version="seasonal-naive-1.0",
        horizon_days=30,
        generated_at=pd.Timestamp.now().to_pydatetime(),
    )
    with pytest.raises(Exception):
        res.method = "prophet"  # frozen


def test_provider_real_sufficient_history():
    provider = SmartHealthForecastProvider(min_history_days=30)
    ref_date = date(2026, 10, 1)

    records = [
        {"ds": (ref_date - timedelta(days=40 - i)).strftime("%Y-%m-%d"), "y": 15.0}
        for i in range(40)
    ]
    df = pd.DataFrame(records)

    result = provider.forecast_item_demand(
        item_id=101,
        item_name="Amoxicillin",
        current_quantity=200,
        horizon_days=14,
        history_override=df,
        allow_synthetic=False,
        data_source_label="database",
    )

    assert isinstance(result, ForecastResult)
    assert result.item_id == 101
    assert result.data_source == "database"
    assert result.history_quality.sufficient is True
    assert result.history_quality.total_rows == 40
    assert len(result.forecasted_demand) == 14
    for pt in result.forecasted_demand:
        assert pt.predicted_quantity >= 0.0
        assert pt.lower_bound >= 0.0
        assert pt.upper_bound >= pt.lower_bound


def test_provider_sparse_history_no_synthetic_fallback():
    provider = SmartHealthForecastProvider(min_history_days=30)
    ref_date = date(2026, 10, 1)

    # Only 5 rows of history (< 30)
    records = [
        {"ds": (ref_date - timedelta(days=5 - i)).strftime("%Y-%m-%d"), "y": 10.0}
        for i in range(5)
    ]
    df = pd.DataFrame(records)

    # Strict: do NOT silently generate synthetic data
    result = provider.forecast_item_demand(
        item_id=102,
        item_name="ORS",
        current_quantity=50,
        horizon_days=7,
        history_override=df,
        allow_synthetic=False,
    )

    assert result.data_source == "custom_feed"
    assert result.method == "baseline_insufficient_history"
    assert result.history_quality.sufficient is False
    assert any("Insufficient history" in lim for lim in result.limitations)


def test_provider_sparse_history_with_synthetic_fallback():
    provider = SmartHealthForecastProvider(min_history_days=30)
    ref_date = date(2026, 10, 1)

    # Only 3 rows
    records = [
        {"ds": (ref_date - timedelta(days=3 - i)).strftime("%Y-%m-%d"), "y": 10.0}
        for i in range(3)
    ]
    df = pd.DataFrame(records)

    # Synthetic fallback allowed
    result = provider.forecast_item_demand(
        item_id=103,
        item_name="Ciprofloxacin",
        current_quantity=50,
        horizon_days=7,
        history_override=df,
        allow_synthetic=True,
    )

    assert result.data_source == "synthetic"
    assert "synthetic" in result.method
    assert any("using synthetic fallback" in lim for lim in result.limitations)


def test_provider_empty_history_disallowed_synthetic_raises():
    provider = SmartHealthForecastProvider(min_history_days=30)
    df = pd.DataFrame()

    with pytest.raises(ValueError, match="no consumption history and synthetic fallback is disabled"):
        provider.forecast_item_demand(
            item_id=999,
            item_name="NonExistentItem",
            current_quantity=0,
            horizon_days=7,
            history_override=df,
            allow_synthetic=False,
        )


def test_anomaly_flags_are_human_review_signals():
    provider = SmartHealthForecastProvider(min_history_days=10)
    ref_date = date(2026, 10, 1)

    # Create history with one massive spike
    records = []
    for i in range(25):
        dt = (ref_date - timedelta(days=25 - i)).strftime("%Y-%m-%d")
        qty = 500.0 if i == 15 else 10.0
        records.append({"ds": dt, "y": qty})
    df = pd.DataFrame(records)

    result = provider.forecast_item_demand(
        item_id=104,
        item_name="Salbutamol Inhaler",
        current_quantity=100,
        horizon_days=7,
        history_override=df,
        allow_synthetic=False,
    )

    if result.anomaly_flags:
        for flag in result.anomaly_flags:
            assert isinstance(flag, AnomalyFlag)
            assert flag.flag in ("unusual_spike", "unusual_drop")
            # Human review signal requirement: never label as outbreak or misconduct
            assert "outbreak" not in flag.flag.lower()
            assert "misconduct" not in flag.flag.lower()


@pytest.mark.asyncio
async def test_provider_footfall_methods():
    provider = get_forecast_provider()
    ref_date = date(2026, 10, 1)

    footfall_records = [
        {"date": (ref_date - timedelta(days=20 - i)).strftime("%Y-%m-%d"), "patient_count": 50 + (i % 5)}
        for i in range(20)
    ]

    # Test predict_footfall_with_bounds
    preds_with_bounds = await provider.predict_footfall_with_bounds(footfall_records)
    assert len(preds_with_bounds) == 7
    for pt in preds_with_bounds:
        assert "date" in pt
        assert "predicted_count" in pt
        assert "lower_bound" in pt
        assert "upper_bound" in pt

    # Test forecast_footfall
    footfall_count_records = [
        {"date": r["date"], "count": r["patient_count"]}
        for r in footfall_records
    ]
    footfall_res = await provider.forecast_footfall(footfall_count_records)
    assert "method" in footfall_res
    assert "horizon_days" in footfall_res
    assert footfall_res["horizon_days"] == 7
    assert len(footfall_res["predictions"]) == 7
