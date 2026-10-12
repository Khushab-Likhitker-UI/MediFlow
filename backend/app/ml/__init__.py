"""
ML forecasting and anomaly detection module.

Public interface defined by docs/implementation/FORECAST_CONTRACT.md:
- Member A imports from ``app.ml`` or ``app.ml.provider``
- Member D owns and maintains ``backend/app/ml/``
"""

from app.ml.provider import (
    AnomalyFlag,
    ForecastPoint,
    ForecastProvider,
    ForecastResult,
    HistoryQuality,
    SmartHealthForecastProvider,
    get_forecast_provider,
)
from app.ml.forecaster import forecast_demand, predict_demand
from app.ml.forecast import forecast_footfall
from app.ml.anomaly_detector import detect_anomalies

__all__ = [
    "ForecastPoint",
    "AnomalyFlag",
    "HistoryQuality",
    "ForecastResult",
    "ForecastProvider",
    "SmartHealthForecastProvider",
    "get_forecast_provider",
    # Legacy backward compatibility exports
    "forecast_demand",
    "predict_demand",
    "forecast_footfall",
    "detect_anomalies",
]
