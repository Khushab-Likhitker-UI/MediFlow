"""
Anomaly detection for supply-chain consumption patterns.

Uses scikit-learn's Isolation Forest when available, with a deterministic
Median Absolute Deviation (MAD) robust Z-score fallback when scikit-learn is absent.

Human-review signal:
- Excludes stock receipts, inventory adjustments, and transfers from consumption anomalies.
- Flags are human-review signals only: "unusual_spike" or "unusual_drop".
- Does NOT label spikes as "outbreak", "epidemic", or "misconduct".
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

try:
    from sklearn.ensemble import IsolationForest  # type: ignore[import-untyped, import-not-found, unused-ignore]
except (ImportError, ModuleNotFoundError):
    IsolationForest = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Minimum data points needed for meaningful anomaly detection.
_MIN_HISTORY_DAYS = 30


# ── Real-data fetcher ────────────────────────────────────────────────────────

def _fetch_real_consumption_history(item_id: int) -> pd.DataFrame | None:
    """Read daily dispensing/consumption usage from PostgreSQL.

    Excludes stock receipts, transfers, and inventory adjustments.
    Queries ``medicine_consumption`` (or dispensed transactions).
    """
    try:
        from app import db  # late import to avoid circular deps

        query = """
        SELECT consumption_date AS date,
               SUM(quantity_consumed) AS usage
        FROM medicine_consumption
        WHERE item_id = %s
        GROUP BY consumption_date
        ORDER BY date
        """
        rows = db.fetch_all(query, (item_id,))

        if not rows or len(rows) < _MIN_HISTORY_DAYS:
            logger.info(
                "Item %d has %d consumption rows (< %d required for anomaly detection).",
                item_id, len(rows) if rows else 0, _MIN_HISTORY_DAYS,
            )
            return None

        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        df["usage"] = df["usage"].astype(float)
        return df

    except Exception as e:
        logger.warning(
            "Could not fetch real consumption for item %d (%s). Falling back.",
            item_id, e,
        )
        return None


# ── Synthetic-data fallback (explicit demo provenance) ──────────────────────

def _generate_synthetic_transactions(
    item_id: int,
    current_quantity: int,
    days: int = 90,
) -> pd.DataFrame:
    """Build synthetic daily usage data with injected demonstration spikes."""
    np.random.seed(item_id + 1000)
    base = max(current_quantity / 30, 5)

    dates = [datetime.now() - timedelta(days=days - i) for i in range(days)]
    usages = np.random.normal(base, base * 0.15, size=days)

    # Inject 2-3 demonstration anomalies
    anomaly_indices = np.random.choice(days, size=min(3, days), replace=False)
    for idx in anomaly_indices:
        usages[idx] *= np.random.choice([2.5, 0.1])

    usages = np.clip(usages, 0, None)
    return pd.DataFrame({"date": dates, "usage": usages})


# ── Statistical Fallback Anomaly Detector (MAD) ──────────────────────────────

def _detect_anomalies_mad(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Deterministic Median Absolute Deviation (MAD) anomaly detector.

    Used when scikit-learn is not available or for fast, transparent verification.
    """
    usages = df["usage"].to_numpy(dtype=float)
    median_val = float(np.median(usages))
    mad = float(np.median(np.abs(usages - median_val)))
    if mad < 1e-6:
        mad = float(np.std(usages)) or 1.0

    # Modified Z-score: 0.6745 * (x - median) / MAD
    modified_z = 0.6745 * (usages - median_val) / mad

    results: list[dict[str, Any]] = []
    mean_val = float(np.mean(usages))
    threshold = 3.0  # standard threshold for modified z-score anomaly

    for i, (_, row) in enumerate(df.iterrows()):
        z = modified_z[i]
        if abs(z) >= threshold:
            # Map modified z to negative score similar to Isolation Forest decision function
            score = -round(float(abs(z) / 10.0), 4)
            flag = "unusual_spike" if row["usage"] > mean_val else "unusual_drop"
            results.append({
                "date": row["date"].strftime("%Y-%m-%d") if isinstance(row["date"], (datetime, pd.Timestamp)) else str(row["date"]),
                "usage": round(float(row["usage"]), 1),
                "anomaly_score": score,
                "flag": flag,
                "is_anomaly": True,
            })
    return results


# ── Public API ───────────────────────────────────────────────────────────────

def detect_anomalies(
    item_id: int,
    item_name: str,
    current_quantity: int,
    df_override: pd.DataFrame | None = None,
    allow_synthetic: bool = True,
) -> list[dict[str, Any]]:
    """Return a list of flagged anomalous days.

    Each dict has: ``date``, ``usage``, ``anomaly_score``, ``flag``.
    Signals are for human-in-the-loop review.
    """
    if df_override is not None and not df_override.empty:
        df = df_override.copy()
        if "ds" in df.columns and "date" not in df.columns:
            df["date"] = df["ds"]
        if "y" in df.columns and "usage" not in df.columns:
            df["usage"] = df["y"]
    else:
        df = _fetch_real_consumption_history(item_id)
        if df is None:
            if not allow_synthetic:
                return []
            df = _generate_synthetic_transactions(item_id, current_quantity)

    if df is None or len(df) < 5:
        return []

    # Ensure columns and types
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["usage"] = pd.to_numeric(df["usage"], errors="coerce").fillna(0.0)

    # Use Isolation Forest if scikit-learn is available
    if IsolationForest is not None:
        try:
            features = df[["usage"]].values
            model = IsolationForest(contamination=0.05, random_state=42, n_estimators=100)
            df["anomaly_label"] = model.fit_predict(features)  # 1 = normal, -1 = anomaly
            df["anomaly_score"] = model.decision_function(features)

            mean_usage = float(df["usage"].mean())
            anomalies = df[df["anomaly_label"] == -1]
            return [
                {
                    "date": row["date"].strftime("%Y-%m-%d"),
                    "usage": round(float(row["usage"]), 1),
                    "anomaly_score": round(float(row["anomaly_score"]), 4),
                    "flag": "unusual_spike" if row["usage"] > mean_usage else "unusual_drop",
                    "is_anomaly": True,
                }
                for _, row in anomalies.iterrows()
            ]
        except Exception as exc:
            logger.warning("IsolationForest failed (%s); using MAD fallback.", exc)

    # Fallback to robust MAD detector
    return _detect_anomalies_mad(df)
