"""
Client adapter for the ForecastProvider interface.
Complies with docs/implementation/FORECAST_CONTRACT.md.
Calls Member D's ML provider when available, otherwise uses a deterministic fallback.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Optional


@dataclass(frozen=True)
class ForecastPoint:
    date: str  # YYYY-MM-DD
    predicted_quantity: float
    lower_bound: float
    upper_bound: float


@dataclass(frozen=True)
class AnomalyFlag:
    date: str  # YYYY-MM-DD
    observed_quantity: float
    anomaly_score: float
    flag: str
    is_anomaly: bool


@dataclass(frozen=True)
class HistoryQuality:
    total_rows: int
    date_range_start: str
    date_range_end: str
    missing_days: int
    sufficient: bool


@dataclass(frozen=True)
class ForecastResult:
    item_id: int
    item_name: str
    forecasted_demand: list[ForecastPoint]
    anomaly_flags: Optional[list[AnomalyFlag]]
    method: str
    data_source: str
    history_quality: HistoryQuality
    model_version: str
    horizon_days: int
    generated_at: datetime
    limitations: list[str] = field(default_factory=list)


class BaselineForecastProvider:
    """
    Transparent, deterministic demand forecast fallback complying with FORECAST_CONTRACT.md.
    Used when Member D's ML module is either not yet merged or undergoing independent testing.
    """

    def forecast_item_demand(
        self,
        item_id: int,
        item_name: str,
        current_quantity: int,
        horizon_days: int = 30,
        consumption_history: Optional[list[dict]] = None,
    ) -> ForecastResult:
        now = datetime.now(timezone.utc)
        today = now.date()

        if consumption_history and len(consumption_history) >= 7:
            # Calculate simple trailing average from actual history
            quantities = [float(row.get("quantity_consumed", 0)) for row in consumption_history]
            avg_daily = sum(quantities) / len(quantities) if quantities else 10.0
            data_source = "database"
            method = "sma"
            sufficient = len(consumption_history) >= 30
            limitations = []
            if not sufficient:
                limitations.append(f"Sparse history: only {len(consumption_history)} days available.")
            dates = [row.get("consumption_date", str(today)) for row in consumption_history]
            history_quality = HistoryQuality(
                total_rows=len(consumption_history),
                date_range_start=min(dates),
                date_range_end=max(dates),
                missing_days=0,
                sufficient=sufficient,
            )
        else:
            # Transparent baseline when history is insufficient
            avg_daily = max(5.0, round(current_quantity / 45.0, 1))
            data_source = "synthetic"
            method = "synthetic_baseline"
            limitations = ["Insufficient historical consumption data; using deterministic baseline."]
            history_quality = HistoryQuality(
                total_rows=len(consumption_history or []),
                date_range_start=str(today - timedelta(days=7)),
                date_range_end=str(today),
                missing_days=7,
                sufficient=False,
            )

        points = []
        for i in range(horizon_days):
            d = (today + timedelta(days=i)).isoformat()
            pred = max(0.0, avg_daily)
            points.append(
                ForecastPoint(
                    date=d,
                    predicted_quantity=round(pred, 2),
                    lower_bound=round(max(0.0, pred * 0.8), 2),
                    upper_bound=round(pred * 1.2, 2),
                )
            )

        return ForecastResult(
            item_id=item_id,
            item_name=item_name,
            forecasted_demand=points,
            anomaly_flags=None,
            method=method,
            data_source=data_source,
            history_quality=history_quality,
            model_version="sentinel-baseline-v1.0",
            horizon_days=horizon_days,
            generated_at=now,
            limitations=limitations,
        )


def get_forecast_provider():
    """
    Factory returning Member D's provider if available, otherwise the baseline provider.
    """
    try:
        from app.ml.provider import get_forecast_provider as get_ml_provider
        return get_ml_provider()
    except (ImportError, AttributeError):
        pass

    try:
        from app.ml.provider import SmartHealthForecastProvider
        return SmartHealthForecastProvider()
    except (ImportError, AttributeError, TypeError):
        pass

    return BaselineForecastProvider()

