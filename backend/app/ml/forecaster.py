"""
Demand forecasting using Facebook Prophet and transparent statistical baselines.

Provides two public entry points for legacy backward compatibility:
1. ``forecast_demand``  – supply-item demand forecast.
2. ``predict_demand``   – patient-footfall forecast (async).

Integrates history quality assessment, transparent seasonal/trailing baselines,
and Prophet (when available and supported by history).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from app.ml.baseline import SeasonalNaiveBaseline, TrailingMeanBaseline
from app.ml.quality import HistoryQualityAssessor, QualityAssessmentResult

try:
    from prophet import Prophet  # type: ignore[import-untyped, import-not-found, unused-ignore]
except (ImportError, ModuleNotFoundError):
    Prophet = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Minimum rows of history required for a meaningful Prophet fit.
_MIN_HISTORY_DAYS = 30


# ── Real-data fetcher ────────────────────────────────────────────────────────

def _fetch_real_consumption(item_id: int) -> pd.DataFrame | None:
    """Read daily dispensing / consumption history from PostgreSQL.

    Excludes stock receipts, inventory adjustments, and transfers.
    Queries ``medicine_consumption``.
    """
    try:
        from app import db  # late import to avoid circular deps

        query = """
        SELECT consumption_date AS ds,
               SUM(quantity_consumed) AS y
        FROM medicine_consumption
        WHERE item_id = %s
        GROUP BY consumption_date
        ORDER BY consumption_date
        """
        rows = db.fetch_all(query, (item_id,))

        if not rows:
            logger.info("No consumption records found for item %d in database.", item_id)
            return None

        df = pd.DataFrame(rows)
        df["ds"] = pd.to_datetime(df["ds"])
        df["y"] = pd.to_numeric(df["y"], errors="coerce").fillna(0.0)
        return df

    except Exception as e:
        logger.warning(
            "Could not fetch real consumption for item %d (%s). Falling back.",
            item_id, e,
        )
        return None


# ── Synthetic-data fallback ──────────────────────────────────────────────────

def _generate_synthetic_history(
    item_id: int,
    current_quantity: int,
    days: int = 180,
) -> pd.DataFrame:
    """Build synthetic consumption history for demonstration/fallback purposes.

    Retained per project requirements (ADR-009) as a documented fallback.
    """
    np.random.seed(item_id)
    base_daily = max(current_quantity / 30, 5.0)

    dates = [datetime.now() - timedelta(days=days - i) for i in range(days)]
    values: list[float] = []
    for dt in dates:
        seasonal = 1.0 + 0.15 * np.sin(2 * np.pi * dt.weekday() / 7)
        noise = np.random.normal(0, base_daily * 0.1)
        values.append(max(0.0, base_daily * seasonal + noise))

    return pd.DataFrame({"ds": dates, "y": values})


# ── Public API: supply-item demand forecast ──────────────────────────────────

def forecast_demand(
    item_id: int,
    item_name: str,
    current_quantity: int,
    horizon_days: int = 30,
    history_df: pd.DataFrame | None = None,
    allow_synthetic: bool = True,
) -> list[dict[str, Any]]:
    """Return ``[{date, predicted_demand, lower_bound, upper_bound}, ...]``.

    Attempts real consumption data first; falls back to transparent baselines
    or synthetic demonstration data if history is inadequate.
    """
    assessor = HistoryQualityAssessor(min_history_days=_MIN_HISTORY_DAYS)

    # 1. Fetch data
    raw_df = history_df if history_df is not None else _fetch_real_consumption(item_id)
    quality = assessor.assess_and_clean(raw_df)

    # 2. Check if synthetic fallback is needed
    if not quality.sufficient:
        if allow_synthetic:
            logger.warning("Insufficient history for item %d; generating synthetic fallback.", item_id)
            synth_df = _generate_synthetic_history(item_id, current_quantity)
            quality = assessor.assess_and_clean(synth_df)
        else:
            logger.info("Insufficient history for item %d and synthetic fallback disabled; using baseline.", item_id)

    cleaned_df = quality.cleaned_df

    # 3. Fit Prophet if library is available and history is sufficient
    if Prophet is not None and quality.sufficient and len(cleaned_df) >= _MIN_HISTORY_DAYS:
        try:
            model = Prophet(
                yearly_seasonality=False,
                weekly_seasonality=True,
                daily_seasonality=False,
                changepoint_prior_scale=0.05,
            )
            model.fit(cleaned_df)
            future = model.make_future_dataframe(periods=horizon_days)
            forecast = model.predict(future)
            preds = forecast.tail(horizon_days)[["ds", "yhat", "yhat_lower", "yhat_upper"]]

            return [
                {
                    "date": row["ds"].strftime("%Y-%m-%d"),
                    "predicted_demand": max(0.0, round(float(row["yhat"]), 1)),
                    "lower_bound": max(0.0, round(float(row["yhat_lower"]), 1)),
                    "upper_bound": max(0.0, round(float(row["yhat_upper"]), 1)),
                }
                for _, row in preds.iterrows()
            ]
        except Exception as exc:
            logger.warning("Prophet fitting failed (%s); falling back to transparent baseline.", exc)

    # 4. Transparent baseline fallback (Seasonal Naive or Trailing Mean)
    baseline = SeasonalNaiveBaseline(cycle_length=7, weeks_window=4)
    baseline_pts = baseline.fit_predict(cleaned_df, horizon_days=horizon_days)

    return [
        {
            "date": p["date"],
            "predicted_demand": round(float(p["predicted_quantity"]), 1),
            "lower_bound": round(float(p["lower_bound"]), 1),
            "upper_bound": round(float(p["upper_bound"]), 1),
        }
        for p in baseline_pts
    ]


# ── Patient Footfall Prediction ─────────────────────────────────────────────

_FORECAST_HORIZON = 7
_MIN_RECORDS_FOR_PROPHET = 14


def _run_prophet(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Fit Prophet on df (columns ds, y) and return 7-day forecast."""
    model = Prophet(
        yearly_seasonality=False,
        weekly_seasonality=True,
        daily_seasonality=False,
        changepoint_prior_scale=0.05,
    )
    model.fit(df)
    future = model.make_future_dataframe(periods=_FORECAST_HORIZON)
    forecast = model.predict(future)

    rows = forecast.tail(_FORECAST_HORIZON)[["ds", "yhat", "yhat_lower", "yhat_upper"]]
    return [
        {
            "date": row["ds"].strftime("%Y-%m-%d"),
            "predicted_count": max(0, round(float(row["yhat"]), 1)),
            "lower_bound": max(0, round(float(row["yhat_lower"]), 1)),
            "upper_bound": max(0, round(float(row["yhat_upper"]), 1)),
        }
        for _, row in rows.iterrows()
    ]


def _sma_fallback(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flat 7-day forecast from simple moving average (with nominal bounds)."""
    counts = [float(r["patient_count"]) for r in records if "patient_count" in r]
    sma = float(sum(counts) / len(counts)) if counts else 0.0
    margin = round(sma * 0.2, 1)

    last_date_val = max(r["date"] for r in records)
    if isinstance(last_date_val, (date, datetime)):
        last_date = last_date_val if isinstance(last_date_val, date) else last_date_val.date()
    else:
        last_date = datetime.strptime(str(last_date_val)[:10], "%Y-%m-%d").date()

    result: list[dict[str, Any]] = []
    for day_offset in range(1, _FORECAST_HORIZON + 1):
        forecast_date = last_date + timedelta(days=day_offset)
        result.append({
            "date": forecast_date.strftime("%Y-%m-%d"),
            "predicted_count": max(0, round(sma, 1)),
            "lower_bound": max(0, round(sma - margin, 1)),
            "upper_bound": round(sma + margin, 1),
        })
    return result


async def predict_demand(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Predict patient footfall for the next 7 days with uncertainty bounds."""
    if not records:
        raise ValueError("records must be a non-empty list")

    if len(records) < _MIN_RECORDS_FOR_PROPHET or Prophet is None:
        return _sma_fallback(records)

    df = pd.DataFrame({
        "ds": pd.to_datetime([r["date"] for r in records]),
        "y": [float(r["patient_count"]) for r in records],
    })

    return await asyncio.to_thread(_run_prophet, df)
