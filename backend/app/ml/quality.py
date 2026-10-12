"""
History quality assessment for demand forecasting.

Provides configurable data quality validation and cleansing for daily
dispensing and consumption time series:
- Minimum observations check
- Gap and coverage detection
- Negative / invalid quantity detection
- Stale data detection
- Non-finite (NaN / Inf) filtering

Thresholds are configurable and documented.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# Default quality thresholds
DEFAULT_MIN_HISTORY_DAYS = 30
DEFAULT_MAX_GAP_DAYS = 7
DEFAULT_STALE_DAYS_THRESHOLD = 60


@dataclass(frozen=True)
class QualityAssessmentResult:
    """Detailed diagnostic results from history quality assessment."""
    total_rows: int
    cleaned_rows: int
    date_range_start: str
    date_range_end: str
    missing_days: int
    coverage_ratio: float
    sufficient: bool
    stale: bool
    has_negative_values: bool
    has_non_finite_values: bool
    cleaned_df: pd.DataFrame
    limitations: list[str]


class HistoryQualityAssessor:
    """Configurable assessor for consumption/dispensing time-series history."""

    def __init__(
        self,
        min_history_days: int = DEFAULT_MIN_HISTORY_DAYS,
        max_gap_days: int = DEFAULT_MAX_GAP_DAYS,
        stale_days_threshold: int = DEFAULT_STALE_DAYS_THRESHOLD,
        reference_date: date | datetime | None = None,
    ) -> None:
        self.min_history_days = min_history_days
        self.max_gap_days = max_gap_days
        self.stale_days_threshold = stale_days_threshold
        self.reference_date = (
            reference_date.date()
            if isinstance(reference_date, datetime)
            else (reference_date or date.today())
        )

    def assess_and_clean(
        self,
        raw_data: pd.DataFrame | list[dict[str, Any]] | None,
        date_col: str = "ds",
        val_col: str = "y",
    ) -> QualityAssessmentResult:
        """Validate, clean, and score consumption history quality.

        Parameters
        ----------
        raw_data : pd.DataFrame | list[dict] | None
            Raw consumption records with date and quantity columns.
        date_col : str
            Name of the date column (default 'ds').
        val_col : str
            Name of the quantity column (default 'y').

        Returns
        -------
        QualityAssessmentResult
            Assessment diagnostics and cleaned (ds, y) DataFrame.
        """
        limitations: list[str] = []

        # Handle None or empty data
        if raw_data is None:
            return QualityAssessmentResult(
                total_rows=0,
                cleaned_rows=0,
                date_range_start="",
                date_range_end="",
                missing_days=0,
                coverage_ratio=0.0,
                sufficient=False,
                stale=False,
                has_negative_values=False,
                has_non_finite_values=False,
                cleaned_df=pd.DataFrame({"ds": pd.Series(dtype="datetime64[ns]"), "y": pd.Series(dtype="float64")}),
                limitations=["Empty history: no records supplied"],
            )

        if isinstance(raw_data, list):
            if not raw_data:
                return QualityAssessmentResult(
                    total_rows=0,
                    cleaned_rows=0,
                    date_range_start="",
                    date_range_end="",
                    missing_days=0,
                    coverage_ratio=0.0,
                    sufficient=False,
                    stale=False,
                    has_negative_values=False,
                    has_non_finite_values=False,
                    cleaned_df=pd.DataFrame({"ds": pd.Series(dtype="datetime64[ns]"), "y": pd.Series(dtype="float64")}),
                    limitations=["Empty history: record list is empty"],
                )
            df = pd.DataFrame(raw_data)
        else:
            df = raw_data.copy()

        if df.empty:
            return QualityAssessmentResult(
                total_rows=0,
                cleaned_rows=0,
                date_range_start="",
                date_range_end="",
                missing_days=0,
                coverage_ratio=0.0,
                sufficient=False,
                stale=False,
                has_negative_values=False,
                has_non_finite_values=False,
                cleaned_df=pd.DataFrame({"ds": pd.Series(dtype="datetime64[ns]"), "y": pd.Series(dtype="float64")}),
                limitations=["Empty history: DataFrame has 0 rows"],
            )

        # Map alternate column names if necessary
        col_rename = {}
        if date_col not in df.columns:
            for alt in ("date", "consumption_date", "transaction_date"):
                if alt in df.columns:
                    col_rename[alt] = date_col
                    break
        if val_col not in df.columns:
            for alt in ("quantity", "quantity_consumed", "usage", "count", "patient_count"):
                if alt in df.columns:
                    col_rename[alt] = val_col
                    break
        if col_rename:
            df = df.rename(columns=col_rename)

        if date_col not in df.columns or val_col not in df.columns:
            limitations.append(f"Missing required columns ({date_col}, {val_col})")
            return QualityAssessmentResult(
                total_rows=len(df),
                cleaned_rows=0,
                date_range_start="",
                date_range_end="",
                missing_days=0,
                coverage_ratio=0.0,
                sufficient=False,
                stale=False,
                has_negative_values=False,
                has_non_finite_values=False,
                cleaned_df=pd.DataFrame({"ds": pd.Series(dtype="datetime64[ns]"), "y": pd.Series(dtype="float64")}),
                limitations=limitations,
            )

        total_rows = len(df)

        # 1. Check for non-finite values
        has_non_finite = bool(df[val_col].isna().any() or pd.to_numeric(df[val_col], errors="coerce").isna().any())
        if has_non_finite:
            limitations.append("Non-finite or unparseable quantities detected and dropped")

        # 2. Convert quantities to float
        df[val_col] = pd.to_numeric(df[val_col], errors="coerce")
        df = df.dropna(subset=[val_col])

        # 3. Check for negative values
        has_negative = bool((df[val_col] < 0).any())
        if has_negative:
            limitations.append("Negative consumption quantities detected; clamped to 0")
            df[val_col] = df[val_col].clip(lower=0.0)

        # 4. Parse dates
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=[date_col])

        if df.empty:
            limitations.append("All rows dropped during sanitization (invalid dates or non-finite values)")
            return QualityAssessmentResult(
                total_rows=total_rows,
                cleaned_rows=0,
                date_range_start="",
                date_range_end="",
                missing_days=0,
                coverage_ratio=0.0,
                sufficient=False,
                stale=False,
                has_negative_values=has_negative,
                has_non_finite_values=has_non_finite,
                cleaned_df=pd.DataFrame({"ds": pd.Series(dtype="datetime64[ns]"), "y": pd.Series(dtype="float64")}),
                limitations=limitations,
            )

        # Deduplicate and aggregate multiple observations on the same date
        df["date_only"] = df[date_col].dt.date
        df = df.groupby("date_only", as_index=False)[val_col].sum()
        df = df.rename(columns={"date_only": date_col})
        df[date_col] = pd.to_datetime(df[date_col])
        df = df.sort_values(by=date_col).reset_index(drop=True)

        cleaned_rows = len(df)
        min_date = df[date_col].min().date()
        max_date = df[date_col].max().date()
        date_span_days = (max_date - min_date).days + 1
        missing_days = max(0, date_span_days - cleaned_rows)
        coverage_ratio = round(cleaned_rows / max(1, date_span_days), 4)

        # 5. Check staleness
        days_since_latest = (self.reference_date - max_date).days
        is_stale = days_since_latest > self.stale_days_threshold
        if is_stale:
            limitations.append(
                f"Stale history: latest data point ({max_date}) is {days_since_latest} days older than reference date"
            )

        # 6. Check observation sufficiency
        sufficient = (cleaned_rows >= self.min_history_days) and not is_stale
        if cleaned_rows < self.min_history_days:
            limitations.append(
                f"Insufficient observations: {cleaned_rows} unique days found (minimum required: {self.min_history_days})"
            )

        if missing_days > 0:
            limitations.append(f"Gaps in history: {missing_days} calendar days missing in range {min_date} to {max_date}")

        cleaned_df = df[[date_col, val_col]].copy()
        cleaned_df[val_col] = cleaned_df[val_col].astype(float)

        return QualityAssessmentResult(
            total_rows=total_rows,
            cleaned_rows=cleaned_rows,
            date_range_start=min_date.strftime("%Y-%m-%d"),
            date_range_end=max_date.strftime("%Y-%m-%d"),
            missing_days=missing_days,
            coverage_ratio=coverage_ratio,
            sufficient=sufficient,
            stale=is_stale,
            has_negative_values=has_negative,
            has_non_finite_values=has_non_finite,
            cleaned_df=cleaned_df,
            limitations=limitations,
        )
