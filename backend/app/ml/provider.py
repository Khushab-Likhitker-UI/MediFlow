"""
ForecastProvider implementation and frozen interface types.

Frozen by docs/implementation/FORECAST_CONTRACT.md (Phase 0).
Implemented by Phase 1D (Forecasting and Evaluation Engineer).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

import pandas as pd

from app.ml.anomaly_detector import detect_anomalies
from app.ml.baseline import SeasonalNaiveBaseline, TrailingMeanBaseline
from app.ml.forecast import forecast_footfall as _forecast_footfall_fn
from app.ml.forecaster import (
    _MIN_HISTORY_DAYS,
    _fetch_real_consumption,
    _generate_synthetic_history,
    predict_demand as _predict_demand_fn,
)
from app.ml.quality import HistoryQualityAssessor, QualityAssessmentResult

try:
    from prophet import Prophet
except (ImportError, ModuleNotFoundError):
    Prophet = None

try:
    from sklearn.ensemble import IsolationForest
except (ImportError, ModuleNotFoundError):
    IsolationForest = None

logger = logging.getLogger(__name__)


# ── Frozen Phase 0 Dataclasses ────────────────────────────────────────────────

@dataclass(frozen=True)
class ForecastPoint:
    """A single forecasted data point."""
    date: str                    # YYYY-MM-DD
    predicted_quantity: float    # Central forecast value (units of medicine.unit)
    lower_bound: float           # 80% confidence interval lower
    upper_bound: float           # 80% confidence interval upper


@dataclass(frozen=True)
class AnomalyFlag:
    """A single anomaly detection result."""
    date: str                    # YYYY-MM-DD
    observed_quantity: float     # Actual observed value
    anomaly_score: float         # Score (more negative = more anomalous)
    flag: str                    # "unusual_spike" | "unusual_drop"
    is_anomaly: bool             # True if flagged


@dataclass(frozen=True)
class HistoryQuality:
    """Metadata about the input data used for forecasting."""
    total_rows: int              # Number of data points available
    date_range_start: str        # YYYY-MM-DD of earliest data point
    date_range_end: str          # YYYY-MM-DD of latest data point
    missing_days: int            # Number of gaps in the date range
    sufficient: bool             # True if >= MIN_HISTORY_DAYS


@dataclass(frozen=True)
class ForecastResult:
    """Complete result from the forecast provider."""

    # ── Core forecast output ─────────────────────────────
    item_id: int
    item_name: str
    forecasted_demand: list[ForecastPoint]
    anomaly_flags: list[AnomalyFlag] | None

    # ── Provenance metadata ──────────────────────────────
    method: str                  # "prophet" | "sma" | "synthetic_sma"
    data_source: str             # "database" | "synthetic"
    history_quality: HistoryQuality
    model_version: str           # e.g. "prophet-1.1.5+iforest-sklearn-1.5"
    horizon_days: int            # Number of days forecasted
    generated_at: datetime       # UTC timestamp of generation

    # ── Limitations ──────────────────────────────────────
    limitations: list[str] = field(default_factory=list)


class ForecastProvider(Protocol):
    """Interface that Member A calls. Member D implements."""

    def forecast_item_demand(
        self,
        item_id: int,
        item_name: str,
        current_quantity: int,
        horizon_days: int = 30,
        history_override: pd.DataFrame | list[dict[str, Any]] | None = None,
        allow_synthetic: bool = True,
        data_source_label: str | None = None,
    ) -> ForecastResult:
        """Forecast demand for a specific medicine/supply item."""
        ...

    async def forecast_footfall(
        self,
        records: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Forecast patient footfall for the next 7 days."""
        ...

    async def predict_footfall_with_bounds(
        self,
        records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Forecast footfall with confidence bounds."""
        ...


# ── Concrete Forecast Provider Implementation ────────────────────────────────

class SmartHealthForecastProvider:
    """Production ForecastProvider conforming to Phase 0 specification."""

    def __init__(self, min_history_days: int = _MIN_HISTORY_DAYS) -> None:
        self.min_history_days = min_history_days
        self.quality_assessor = HistoryQualityAssessor(min_history_days=min_history_days)

    def forecast_item_demand(
        self,
        item_id: int,
        item_name: str,
        current_quantity: int,
        horizon_days: int = 30,
        history_override: pd.DataFrame | list[dict[str, Any]] | None = None,
        allow_synthetic: bool = True,
        data_source_label: str | None = None,
    ) -> ForecastResult:
        """Forecast demand for a specific medicine/supply item.

        Parameters
        ----------
        item_id : int
            The medicines.item_id primary key.
        item_name : str
            Human-readable medicine name.
        current_quantity : int
            Current inventory quantity across facilities.
        horizon_days : int
            Forecast horizon in days (1-365).
        history_override : DataFrame | list[dict] | None
            Optional explicit history data for testing/replay.
        allow_synthetic : bool
            Whether synthetic fallback generation is permitted if history is inadequate.
        data_source_label : str | None
            Explicit label for data provenance.

        Returns
        -------
        ForecastResult
            Typed forecast result conforming to FORECAST_CONTRACT.md.

        Raises
        ------
        ValueError
            If item has no history and allow_synthetic is False.
        """
        generated_at = datetime.now(timezone.utc)
        limitations: list[str] = [
            "Nominal 80% uncertainty bounds; not automatically calibrated to real PHC variance."
        ]

        # 1. Acquire raw consumption history
        is_synthetic = False
        default_source = "database" if history_override is None else "custom_feed"

        if history_override is not None:
            raw_history = history_override
        else:
            raw_history = _fetch_real_consumption(item_id)

        assessment = self.quality_assessor.assess_and_clean(raw_history)
        limitations.extend(assessment.limitations)

        # 2. Check if history is sufficient or if fallback is required
        if not assessment.sufficient:
            if not allow_synthetic:
                if assessment.cleaned_rows == 0:
                    raise ValueError(
                        f"Item {item_id} ({item_name}) has no consumption history and synthetic fallback is disabled."
                    )
                # Keep real data, use transparent baseline
                data_source = data_source_label or default_source
                method = "baseline_insufficient_history"
                model_version = "baseline-sma-1.0"
                limitations.append("Insufficient history: using transparent baseline fallback without synthetic generation")
            else:
                logger.warning("Item %d (%s) has insufficient history; using synthetic fallback.", item_id, item_name)
                is_synthetic = True
                data_source = "synthetic"
                method = "synthetic_sma"
                model_version = "synthetic-generator-1.0+sma-1.0"
                limitations.append("Insufficient history: using synthetic fallback")
                synth_df = _generate_synthetic_history(item_id, current_quantity)
                assessment = self.quality_assessor.assess_and_clean(synth_df)
        else:
            data_source = data_source_label or default_source
            method = "seasonal_naive"
            model_version = "seasonal-naive-1.0"

        cleaned_df = assessment.cleaned_df

        # 3. Model execution: Prophet vs Transparent Baseline
        forecast_points: list[ForecastPoint] = []
        prophet_success = False

        if Prophet is not None and assessment.sufficient and not is_synthetic:
            try:
                m = Prophet(
                    yearly_seasonality=False,
                    weekly_seasonality=True,
                    daily_seasonality=False,
                    changepoint_prior_scale=0.05,
                )
                m.fit(cleaned_df)
                future = m.make_future_dataframe(periods=horizon_days)
                forecast = m.predict(future)
                preds = forecast.tail(horizon_days)

                for _, row in preds.iterrows():
                    pred_qty = max(0.0, round(float(row["yhat"]), 2))
                    lb = max(0.0, round(float(row["yhat_lower"]), 2))
                    ub = max(lb, round(float(row["yhat_upper"]), 2))
                    forecast_points.append(
                        ForecastPoint(
                            date=row["ds"].strftime("%Y-%m-%d"),
                            predicted_quantity=pred_qty,
                            lower_bound=lb,
                            upper_bound=ub,
                        )
                    )
                method = "prophet"
                model_version = "prophet-1.1.5"
                prophet_success = True
            except Exception as exc:
                logger.warning("Prophet fitting failed (%s); reverting to baseline.", exc)
                limitations.append(f"Prophet fitting encountered exception: {exc}")

        if not prophet_success:
            if Prophet is None and not is_synthetic:
                limitations.append("Prophet package unavailable in runtime environment; using transparent baseline.")

            # Run Seasonal Naive or Trailing Mean baseline
            if len(cleaned_df) >= 7:
                baseline = SeasonalNaiveBaseline(cycle_length=7, weeks_window=4)
                if not is_synthetic and method != "baseline_insufficient_history":
                    method = "seasonal_naive"
                    model_version = "seasonal-naive-1.0"
            else:
                baseline = TrailingMeanBaseline(window_days=7)
                if not is_synthetic and method != "baseline_insufficient_history":
                    method = "trailing_mean"
                    model_version = "trailing-mean-1.0"

            raw_pts = baseline.fit_predict(cleaned_df, horizon_days=horizon_days)
            for p in raw_pts:
                forecast_points.append(
                    ForecastPoint(
                        date=p["date"],
                        predicted_quantity=float(p["predicted_quantity"]),
                        lower_bound=float(p["lower_bound"]),
                        upper_bound=float(p["upper_bound"]),
                    )
                )

        # 4. Anomaly detection (human review signals on consumption data)
        anomaly_flags: list[AnomalyFlag] = []
        try:
            raw_anomalies = detect_anomalies(
                item_id=item_id,
                item_name=item_name,
                current_quantity=current_quantity,
                df_override=cleaned_df,
                allow_synthetic=is_synthetic,
            )
            for a in (raw_anomalies or []):
                anomaly_flags.append(
                    AnomalyFlag(
                        date=a["date"],
                        observed_quantity=float(a["usage"]),
                        anomaly_score=float(a["anomaly_score"]),
                        flag=str(a["flag"]),
                        is_anomaly=bool(a["is_anomaly"]),
                    )
                )
        except Exception as exc:
            logger.warning("Anomaly detection failed for item %d: %s", item_id, exc)
            limitations.append(f"Anomaly detection skipped: {exc}")

        if IsolationForest is None:
            model_version += "+iforest-fallback-mad"
        else:
            model_version += "+iforest-sklearn"

        history_quality = HistoryQuality(
            total_rows=assessment.total_rows,
            date_range_start=assessment.date_range_start,
            date_range_end=assessment.date_range_end,
            missing_days=assessment.missing_days,
            sufficient=assessment.sufficient,
        )

        return ForecastResult(
            item_id=item_id,
            item_name=item_name,
            forecasted_demand=forecast_points,
            anomaly_flags=anomaly_flags or None,
            method=method,
            data_source=data_source,
            history_quality=history_quality,
            model_version=model_version,
            horizon_days=horizon_days,
            generated_at=generated_at,
            limitations=limitations,
        )

    async def forecast_footfall(
        self,
        records: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Forecast patient footfall for the next 7 days."""
        return await _forecast_footfall_fn(records)

    async def predict_footfall_with_bounds(
        self,
        records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Forecast footfall with confidence bounds."""
        return await _predict_demand_fn(records)


# ── Global Provider Singleton / Factory ──────────────────────────────────────

_GLOBAL_PROVIDER: ForecastProvider | None = None


def get_forecast_provider() -> ForecastProvider:
    """Return the global ForecastProvider instance for Member A."""
    global _GLOBAL_PROVIDER
    if _GLOBAL_PROVIDER is None:
        _GLOBAL_PROVIDER = SmartHealthForecastProvider()
    return _GLOBAL_PROVIDER
