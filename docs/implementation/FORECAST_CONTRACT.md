# Smart Health Sentinel — Forecast Provider Contract

> **Baseline commit:** `cfe5968` (branch: `main`)
> **Date frozen:** 2026-10-13

This document defines the **ForecastProvider interface** that separates ownership:
- **Member A** (backend routes) calls the provider — never imports implementation details.
- **Member D** (ML module) implements the provider — owns `backend/app/ml/`.

---

## 1. Module Boundary

```
backend/app/ml/
├── __init__.py          ← Public re-exports (Member D maintains)
├── provider.py          ← ForecastProvider interface (frozen by this contract)
├── forecaster.py        ← Prophet implementation (Member D)
├── forecast.py          ← Footfall forecast (Member D)
└── anomaly_detector.py  ← Isolation Forest (Member D)
```

Member A imports ONLY from `backend/app/ml/provider` (or `backend/app/ml/__init__`).
Member A NEVER imports from `forecaster.py`, `forecast.py`, or `anomaly_detector.py` directly.

---

## 2. ForecastProvider Interface

```python
# backend/app/ml/provider.py  (to be created by Member D)

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


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
    anomaly_score: float         # Isolation Forest score (more negative = more anomalous)
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
    # Examples:
    #   "Insufficient history: using synthetic fallback"
    #   "Prophet yearly_seasonality disabled"
    #   "Anomaly detection skipped: <30 transaction rows"


class ForecastProvider(Protocol):
    """Interface that Member A calls. Member D implements."""

    def forecast_item_demand(
        self,
        item_id: int,
        item_name: str,
        current_quantity: int,
        horizon_days: int = 30,
    ) -> ForecastResult:
        """Forecast demand for a specific medicine/supply item.

        Parameters
        ----------
        item_id : int
            The `medicines.item_id` primary key.
        item_name : str
            Human-readable medicine name (for result labeling).
        current_quantity : int
            Current aggregated inventory quantity across all facilities.
        horizon_days : int
            Number of days to forecast (1-365).

        Returns
        -------
        ForecastResult
            Complete forecast with provenance metadata.

        Raises
        ------
        ValueError
            If item_id does not exist in consumption history
            AND synthetic fallback is disabled.
        """
        ...

    async def forecast_footfall(
        self,
        records: list[dict],
    ) -> dict:
        """Forecast patient footfall for the next 7 days.

        Parameters
        ----------
        records : list[dict]
            Dicts with keys ``date`` (YYYY-MM-DD) and ``count`` (int).

        Returns
        -------
        dict
            ``{method, horizon_days, input_points, predictions}``
        """
        ...

    async def predict_footfall_with_bounds(
        self,
        records: list[dict],
    ) -> list[dict]:
        """Forecast footfall with confidence bounds.

        Parameters
        ----------
        records : list[dict]
            Dicts with ``date`` and ``patient_count``.

        Returns
        -------
        list[dict]
            Seven dicts with ``date``, ``predicted_count``,
            ``lower_bound``, ``upper_bound``.
        """
        ...
```

---

## 3. How Member A Calls the Provider

```python
# In backend/app/routes/predictions.py (Member A's code)

from app.ml import get_forecast_provider

provider = get_forecast_provider()

# Supply-item demand forecast
result: ForecastResult = provider.forecast_item_demand(
    item_id=req.item_id,
    item_name=item_name,
    current_quantity=current_quantity,
    horizon_days=req.horizon_days,
)

# Member A maps ForecastResult → PredictionResponse for the API
return PredictionResponse(
    item_id=result.item_id,
    item_name=result.item_name,
    forecasted_demand=[
        {"date": p.date, "predicted_quantity": p.predicted_quantity}
        for p in result.forecasted_demand
    ],
    anomaly_flags=[
        {"date": a.date, "quantity": a.observed_quantity,
         "is_anomaly": a.is_anomaly, "score": a.anomaly_score}
        for a in (result.anomaly_flags or [])
    ] or None,
    method=result.method,
    data_source=result.data_source,
)
```

---

## 4. Current Implementation Mapping

The existing code does NOT yet implement the `ForecastProvider` protocol.
Here is the mapping for Member D to refactor:

| Provider method | Current function | File |
|---|---|---|
| `forecast_item_demand()` | `forecast_demand()` + `detect_anomalies()` | `forecaster.py` + `anomaly_detector.py` |
| `forecast_footfall()` | `forecast_footfall()` | `forecast.py` |
| `predict_footfall_with_bounds()` | `predict_demand()` | `forecaster.py` |

Member D wraps these into a class implementing `ForecastProvider` and re-exports via `__init__.py`.

---

## 5. Synthetic Data Labeling Requirements

When synthetic/fallback data is used, the `ForecastResult` MUST:

1. Set `data_source = "synthetic"`
2. Set `method` to include the suffix (e.g. `"synthetic_sma"`)
3. Add a limitation string: `"Insufficient history: using synthetic fallback"`
4. Log a warning via the Python `logging` module

This ensures the frontend can display a banner:  
> ⚠️ This forecast uses synthetic demonstration data, not real consumption history.
