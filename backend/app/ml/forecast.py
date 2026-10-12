"""
Patient footfall forecasting (shortage prediction).

Receives a list of daily patient-count dictionaries and returns a
7-day forecast using either Facebook Prophet (when ≥ 14 data points
are supplied) or a simple moving average fallback.

This module does **not** generate synthetic data — it processes the
history supplied by the API caller.
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from typing import Any

try:
    import pandas as pd  # type: ignore[import-untyped, import-not-found, unused-ignore]
except (ImportError, ModuleNotFoundError):
    pd = None  # type: ignore[assignment]

try:
    from prophet import Prophet  # type: ignore[import-untyped, import-not-found, unused-ignore]
except (ImportError, ModuleNotFoundError):
    Prophet = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

_FORECAST_HORIZON = 7  # days to predict
_SMA_WINDOW = 3        # window size for the fallback SMA
_MIN_RECORDS_FOR_PROPHET = 14  # Prophet needs at least ~2 weeks

# Dedicated thread pool for CPU-bound Prophet fitting.
_prophet_executor = ThreadPoolExecutor(
    max_workers=2, thread_name_prefix="prophet"
)


# ── Prophet forecast ─────────────────────────────────────────────────────────

def _prophet_forecast(
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Run Prophet synchronously (meant to be called via ``run_in_executor``).

    Returns the full response dict ``{method, horizon_days, input_points,
    predictions}`` expected by the ``/api/predict-shortage`` endpoint.
    """
    import logging as _logging
    for _name in ("prophet", "cmdstanpy"):
        _logging.getLogger(_name).setLevel(_logging.WARNING)

    df = pd.DataFrame(records).rename(columns={"date": "ds", "count": "y"})
    df["ds"] = pd.to_datetime(df["ds"])

    model = Prophet(
        yearly_seasonality=False,
        weekly_seasonality=True,
        daily_seasonality=False,
        changepoint_prior_scale=0.05,
    )
    model.fit(df)

    future = model.make_future_dataframe(periods=_FORECAST_HORIZON)
    forecast = model.predict(future)

    preds = forecast.tail(_FORECAST_HORIZON)
    predictions = [
        {
            "date": row["ds"].strftime("%Y-%m-%d"),
            "predicted_count": max(0, round(row["yhat"])),
        }
        for _, row in preds.iterrows()
    ]

    return {
        "method": "prophet",
        "horizon_days": _FORECAST_HORIZON,
        "input_points": len(records),
        "predictions": predictions,
    }


# ── SMA fallback ─────────────────────────────────────────────────────────────

def _sma_fallback(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Flat 7-day forecast using the last ``_SMA_WINDOW`` days' average.

    Used when fewer than ``_MIN_RECORDS_FOR_PROPHET`` records are
    supplied — too few for Prophet to fit meaningfully.
    """
    counts = [r["count"] for r in records]
    window = counts[-_SMA_WINDOW:]
    avg = sum(window) / len(window) if window else 0

    last_date_str = records[-1]["date"]
    if isinstance(last_date_str, date):
        last_date = last_date_str
    else:
        last_date = datetime.strptime(str(last_date_str), "%Y-%m-%d").date()

    predictions = []
    for i in range(1, _FORECAST_HORIZON + 1):
        predictions.append(
            {
                "date": (last_date + timedelta(days=i)).strftime("%Y-%m-%d"),
                "predicted_count": max(0, round(avg)),
            }
        )

    return {
        "method": "sma",
        "horizon_days": _FORECAST_HORIZON,
        "input_points": len(records),
        "predictions": predictions,
    }


# ── Public API ───────────────────────────────────────────────────────────────

async def forecast_footfall(
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Predict patient footfall for the next 7 days.

    Parameters
    ----------
    records:
        List of ``{"date": "YYYY-MM-DD", "count": int}`` dicts.

    Returns
    -------
    dict
        ``{method, horizon_days, input_points, predictions}``
    """
    if not records:
        raise ValueError("records must be a non-empty list")

    if len(records) < _MIN_RECORDS_FOR_PROPHET or Prophet is None or pd is None:
        if Prophet is None or pd is None:
            logger.warning("ML libraries (Prophet/Pandas) unavailable — using SMA fallback.")
        else:
            logger.info(
                "Only %d record(s) (< %d) — using SMA fallback.",
                len(records), _MIN_RECORDS_FOR_PROPHET,
            )
        return _sma_fallback(records)

    logger.info("Received %d records — fitting Prophet model.", len(records))
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_prophet_executor, _prophet_forecast, records)
