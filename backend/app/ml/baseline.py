"""
Simple transparent forecasting baselines for demand time series.

Provides:
1. TrailingMeanBaseline (Moving average with empirical variance bounds)
2. SeasonalNaiveBaseline (Day-of-week 7-day cyclical baseline)

These transparent baselines ensure the system always produces trustworthy,
interpretable demand forecasts without hidden complexity or uncalibrated assumptions.
Uncertainty ranges are nominal and clamped at >= 0 to match demand semantics.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd


class TrailingMeanBaseline:
    """Trailing mean / Simple Moving Average (SMA) baseline.

    Parameters
    ----------
    window_days : int
        Number of most recent observations to compute mean and empirical variance.
    z_score : float
        Normal multiplier for confidence bounds (1.28 ~ 80% interval).
    """

    def __init__(self, window_days: int = 14, z_score: float = 1.28) -> None:
        self.window_days = window_days
        self.z_score = z_score

    def fit_predict(
        self,
        df: pd.DataFrame,
        horizon_days: int = 30,
        start_date: date | datetime | None = None,
        date_col: str = "ds",
        val_col: str = "y",
    ) -> list[dict[str, Any]]:
        """Compute flat trailing-mean forecast with nominal uncertainty bounds.

        Returns a list of dicts:
        ``[{"date": YYYY-MM-DD, "predicted_quantity": float, "lower_bound": float, "upper_bound": float}, ...]``
        """
        if df.empty or val_col not in df.columns:
            mean_val = 0.0
            std_val = 0.0
            latest_date = start_date or date.today()
            if isinstance(latest_date, datetime):
                latest_date = latest_date.date()
        else:
            sorted_df = df.sort_values(by=date_col)
            recent_vals = sorted_df[val_col].tail(self.window_days).to_numpy(dtype=float)
            if len(recent_vals) == 0:
                mean_val = 0.0
                std_val = 0.0
            else:
                mean_val = float(np.mean(recent_vals))
                std_val = float(np.std(recent_vals, ddof=1)) if len(recent_vals) > 1 else (0.15 * mean_val)

            if start_date is not None:
                latest_date = start_date.date() if isinstance(start_date, datetime) else start_date
            else:
                last_ts = sorted_df[date_col].iloc[-1]
                latest_date = last_ts.date() if isinstance(last_ts, (datetime, pd.Timestamp)) else last_ts

        # Fallback margin if std is zero or missing
        margin = max(self.z_score * std_val, 0.15 * mean_val, 0.5 if mean_val > 0 else 0.0)

        results = []
        for i in range(1, horizon_days + 1):
            forecast_date = latest_date + timedelta(days=i)
            pred = max(0.0, round(mean_val, 2))
            lower = max(0.0, round(mean_val - margin, 2))
            upper = max(lower, round(mean_val + margin, 2))
            results.append({
                "date": forecast_date.strftime("%Y-%m-%d"),
                "predicted_quantity": pred,
                "lower_bound": lower,
                "upper_bound": upper,
            })
        return results


class SeasonalNaiveBaseline:
    """7-day seasonal-naive baseline (matching day-of-week).

    For public health centers and pharmacies, dispensing patterns often follow
    pronounced day-of-week cycles (e.g. peak on Mondays, dip on weekends).
    This baseline forecasts day t using the historical distribution of that same weekday.

    Parameters
    ----------
    cycle_length : int
        Seasonality cycle in days (default 7).
    weeks_window : int
        How many past cycles/weeks to consider (default 4).
    z_score : float
        Normal multiplier for confidence interval (1.28 ~ 80% interval).
    """

    def __init__(self, cycle_length: int = 7, weeks_window: int = 4, z_score: float = 1.28) -> None:
        self.cycle_length = cycle_length
        self.weeks_window = weeks_window
        self.z_score = z_score

    def fit_predict(
        self,
        df: pd.DataFrame,
        horizon_days: int = 30,
        start_date: date | datetime | None = None,
        date_col: str = "ds",
        val_col: str = "y",
    ) -> list[dict[str, Any]]:
        """Forecast future horizon using day-of-week historical distribution."""
        if df.empty or len(df) < self.cycle_length:
            # Fall back to TrailingMeanBaseline if history is shorter than 1 cycle
            trailing = TrailingMeanBaseline(window_days=self.cycle_length, z_score=self.z_score)
            return trailing.fit_predict(df, horizon_days=horizon_days, start_date=start_date, date_col=date_col, val_col=val_col)

        sorted_df = df.copy()
        sorted_df[date_col] = pd.to_datetime(sorted_df[date_col])
        sorted_df = sorted_df.sort_values(by=date_col)
        sorted_df["weekday"] = sorted_df[date_col].dt.weekday

        # Restrict to recent weeks window
        cutoff_days = self.cycle_length * self.weeks_window
        recent_df = sorted_df.tail(cutoff_days)

        weekday_stats: dict[int, tuple[float, float]] = {}
        global_mean = float(recent_df[val_col].mean())
        global_std = float(recent_df[val_col].std(ddof=1)) if len(recent_df) > 1 else 0.15 * global_mean

        for w in range(7):
            w_vals = recent_df[recent_df["weekday"] == w][val_col].to_numpy(dtype=float)
            if len(w_vals) > 0:
                w_mean = float(np.mean(w_vals))
                w_std = float(np.std(w_vals, ddof=1)) if len(w_vals) > 1 else global_std
            else:
                w_mean = global_mean
                w_std = global_std
            weekday_stats[w] = (w_mean, w_std)

        if start_date is not None:
            latest_date = start_date.date() if isinstance(start_date, datetime) else start_date
        else:
            last_ts = sorted_df[date_col].iloc[-1]
            latest_date = last_ts.date() if isinstance(last_ts, (datetime, pd.Timestamp)) else last_ts

        results = []
        for i in range(1, horizon_days + 1):
            forecast_date = latest_date + timedelta(days=i)
            w = forecast_date.weekday()
            w_mean, w_std = weekday_stats.get(w, (global_mean, global_std))
            margin = max(self.z_score * w_std, 0.15 * w_mean, 0.5 if w_mean > 0 else 0.0)

            pred = max(0.0, round(w_mean, 2))
            lower = max(0.0, round(w_mean - margin, 2))
            upper = max(lower, round(w_mean + margin, 2))

            results.append({
                "date": forecast_date.strftime("%Y-%m-%d"),
                "predicted_quantity": pred,
                "lower_bound": lower,
                "upper_bound": upper,
            })
        return results
