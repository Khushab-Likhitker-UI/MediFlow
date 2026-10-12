"""
Prediction / forecasting routes.

Exposes the ML pipeline (Prophet demand forecasting + scikit-learn anomaly
detection) through REST endpoints.

All item lookups are performed against PostgreSQL.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    FootfallPredictionRequest,
    FootfallRequest,
    PredictionRequest,
    PredictionResponse,
)
from app.ml.forecaster import forecast_demand, predict_demand as predict_footfall_demand
from app.ml.forecast import forecast_footfall
from app.ml.anomaly_detector import detect_anomalies
from app import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/predictions", tags=["Predictions"])


@router.post(
    "/demand",
    response_model=PredictionResponse,
    summary="Forecast demand for a supply item",
)
async def predict_demand(req: PredictionRequest):
    """Forecast demand for a supply item using Prophet.

    Fetches the item's name and current aggregated quantity from
    PostgreSQL, then delegates to the ML pipeline.
    """
    try:
        query = """
        SELECT m.name, COALESCE(SUM(i.quantity), 0) as quantity
        FROM medicines m
        LEFT JOIN inventory i ON i.item_id = m.item_id
        WHERE m.item_id = %s
        GROUP BY m.item_id
        """
        record = db.fetch_one(query, (req.item_id,))
    except Exception as e:
        logger.error("Failed to fetch item %d for prediction: %s", req.item_id, e)
        raise HTTPException(status_code=500, detail="Failed to fetch item data")

    if not record:
        raise HTTPException(status_code=404, detail="Inventory item not found")

    item_name = record["name"]
    current_quantity = int(record["quantity"])

    try:
        forecast = forecast_demand(
            item_id=req.item_id,
            item_name=item_name,
            current_quantity=current_quantity,
            horizon_days=req.horizon_days,
        )
    except Exception as e:
        logger.error("Forecast failed for item %d: %s", req.item_id, e)
        raise HTTPException(status_code=500, detail="Forecast model failed")

    try:
        anomalies = detect_anomalies(
            item_id=req.item_id,
            item_name=item_name,
            current_quantity=current_quantity,
        )
    except Exception as e:
        # Non-fatal: return forecast without anomalies if detection fails
        logger.warning("Anomaly detection failed for item %d: %s", req.item_id, e)
        anomalies = None

    return PredictionResponse(
        item_id=req.item_id,
        item_name=item_name,
        forecasted_demand=forecast,
        anomaly_flags=anomalies,
    )


@router.get("/health", summary="ML pipeline health check")
async def ml_health():
    return {
        "status": "ok",
        "models": {
            "forecaster": "prophet",
            "anomaly_detector": "isolation_forest",
        },
    }


# ── Shortage / Footfall prediction (standalone prefix) ──────────────────────
# Mounted separately at /api in main.py → final URL: /api/predict-shortage

shortage_router = APIRouter(tags=["Shortage Prediction"])


@shortage_router.post(
    "/predict-shortage",
    summary="Predict patient footfall shortage for the next 7 days",
    response_description="7-day footfall forecast with method metadata",
)
async def predict_shortage(body: FootfallRequest):
    """
    Accepts historical daily patient footfall and returns a 7-day forecast.

    - **≥ 14 data points** → Facebook Prophet time-series model
    - **< 14 data points** → 3-day simple moving average fallback
    """
    try:
        history_dicts = [entry.model_dump() for entry in body.history]
        result = await forecast_footfall(history_dicts)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@shortage_router.post(
    "/predict",
    summary="Predict patient footfall for the next 7 days",
    response_description="7-day footfall forecast with predicted counts and confidence bounds",
)
async def predict_footfall(body: FootfallPredictionRequest):
    """
    Accepts a list of **DailyFootfall** records and returns a 7-day forecast.

    - **≥ 14 records** → Facebook Prophet time-series model
    - **< 14 records** → Simple Moving Average fallback (±20 % bounds)

    Each returned item contains ``date``, ``predicted_count``,
    ``lower_bound``, and ``upper_bound``.
    """
    try:
        # Convert Pydantic models → plain dicts expected by predict_demand
        records = [
            {
                "date": entry.date.isoformat(),
                "patient_count": entry.patient_count,
            }
            for entry in body.footfall_data
        ]

        predictions = await predict_footfall_demand(records)

        return {"predictions": predictions}

    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("Footfall prediction failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed: {exc}",
        )
