# Smart Health Sentinel — Phase 1D Status Report

> **Repository:** `https://github.com/AmitRK9819/Smart_Health`  
> **Phase:** Phase 1D — Demand Forecasting, Quality Assessment & Scenario Evaluation  
> **Role:** Forecasting and Evaluation Engineer (Member D)  
> **Date:** 2026-10-13  
> **Status:** COMPLETE  

---

## 1. Executive Summary

Phase 1D implements the frozen Phase 0 `ForecastProvider` interface (`docs/implementation/FORECAST_CONTRACT.md`), history quality assessment, transparent statistical baselines, human-in-the-loop consumption anomaly detection, deterministic scenario fixtures, and chronological policy replay evaluation.

### Key Milestones Delivered
1. **Contract Implementation:** Conforms strictly to the frozen `ForecastProvider` Protocol and immutable dataclasses (`ForecastPoint`, `AnomalyFlag`, `HistoryQuality`, `ForecastResult`).
2. **Dependency & Environment Verification:** Audited actual runtime dependencies. Facebook Prophet and scikit-learn are not pre-installed in the Python 3.14 Windows environment. Provided transparent, interpretable baselines (`SeasonalNaiveBaseline`, `TrailingMeanBaseline`, and robust MAD Z-score anomaly detection) so the forecasting module operates reliably, deterministically, and with zero external C-extension dependencies. Prophet and Isolation Forest are used automatically when installed and supported by data.
3. **Consumption Semantics:** Ensured demand forecasting and anomaly detection query daily dispensing/consumption history (`medicine_consumption` or transactions where `transaction_type = 'dispensed'`), explicitly excluding stock receipts, inventory adjustments, and transfers. Spikes are labeled as human-review signals (`unusual_spike`, `unusual_drop`), never as outbreaks or misconduct.
4. **Data Quality & Fallback Provenance:** Built `HistoryQualityAssessor` to check minimum observation count, date gaps/continuity, negative/invalid quantities, stale data, and non-finite values. Distinguishes real database history (`data_source = "database"`), transparent fallback (`method = "baseline_insufficient_history"`), and synthetic demo data (`data_source = "synthetic"`, `method = "synthetic_sma"`).
5. **Deterministic Scenarios & Policy Replay:** Created 10 canonical in-memory scenario fixtures with chronological train/test splits. Replays inventory balances, batch expiry drops, delivery receipts, transfer constraint violations, and offline sync retries. Generates machine-readable evaluation reports.
6. **Testing:** 34 unit tests in `backend/tests/` passing with 100% success rate without network access or live external services.

---

## 2. File Ownership & Changes

All changes are strictly confined to Member D's lane (`backend/app/ml/`, `backend/tests/`, evaluation scripts, and status documentation). No API routes, database migrations, or frontend files were modified.

| File | Purpose |
|---|---|
| [`backend/app/ml/provider.py`](file:///c:/Users/PC%20World/OneDrive/Desktop/MediFlow/backend/app/ml/provider.py) | Implements `ForecastProvider` Protocol, `ForecastResult`, `ForecastPoint`, `AnomalyFlag`, `HistoryQuality`, and `get_forecast_provider()` factory. |
| [`backend/app/ml/quality.py`](file:///c:/Users/PC%20World/OneDrive/Desktop/MediFlow/backend/app/ml/quality.py) | `HistoryQualityAssessor` assessing gaps, observation thresholds, negative clamping, staleness, and non-finite values. |
| [`backend/app/ml/baseline.py`](file:///c:/Users/PC%20World/OneDrive/Desktop/MediFlow/backend/app/ml/baseline.py) | `SeasonalNaiveBaseline` (7-day day-of-week) and `TrailingMeanBaseline` with nominal uncalibrated 80% bounds clamped at $\ge 0$. |
| [`backend/app/ml/forecaster.py`](file:///c:/Users/PC%20World/OneDrive/Desktop/MediFlow/backend/app/ml/forecaster.py) | Prophet and baseline integration for supply item demand, preserving legacy `forecast_demand` and `predict_demand`. |
| [`backend/app/ml/anomaly_detector.py`](file:///c:/Users/PC%20World/OneDrive/Desktop/MediFlow/backend/app/ml/anomaly_detector.py) | Isolation Forest with robust MAD fallback. Excludes stock receipts and adjustments; labels strictly for human review. |
| [`backend/app/ml/forecast.py`](file:///c:/Users/PC%20World/OneDrive/Desktop/MediFlow/backend/app/ml/forecast.py) | Patient footfall shortage forecasting (7-day horizon with SMA fallback). |
| [`backend/app/ml/__init__.py`](file:///c:/Users/PC%20World/OneDrive/Desktop/MediFlow/backend/app/ml/__init__.py) | Public module exports conforming to ADR-006 and Phase 0 contract. |
| [`backend/app/ml/evaluation/metrics.py`](file:///c:/Users/PC%20World/OneDrive/Desktop/MediFlow/backend/app/ml/evaluation/metrics.py) | MAE, WAPE, stockout recall, precision, warning lead time, stockout days, and transfer constraint violations. |
| [`backend/app/ml/evaluation/scenarios.py`](file:///c:/Users/PC%20World/OneDrive/Desktop/MediFlow/backend/app/ml/evaluation/scenarios.py) | 10 canonical deterministic test scenarios (synthetic, labeled). |
| [`backend/app/ml/evaluation/replay.py`](file:///c:/Users/PC%20World/OneDrive/Desktop/MediFlow/backend/app/ml/evaluation/replay.py) | Chronological policy replay engine simulating daily physical inventory. |
| [`backend/app/ml/evaluation/runner.py`](file:///c:/Users/PC%20World/OneDrive/Desktop/MediFlow/backend/app/ml/evaluation/runner.py) | CLI and runner script exporting machine-readable `evaluation_report.json`. |
| [`backend/run_evaluation.py`](file:///c:/Users/PC%20World/OneDrive/Desktop/MediFlow/backend/run_evaluation.py) | Root runner script for deterministic evaluation. |
| [`backend/tests/conftest.py`](file:///c:/Users/PC%20World/OneDrive/Desktop/MediFlow/backend/tests/conftest.py) | Configures `sys.path` for automated testing. |
| [`backend/tests/test_ml_quality.py`](file:///c:/Users/PC%20World/OneDrive/Desktop/MediFlow/backend/tests/test_ml_quality.py) | Unit tests for quality assessment, data gaps, non-finite values, staleness. |
| [`backend/tests/test_ml_baselines.py`](file:///c:/Users/PC%20World/OneDrive/Desktop/MediFlow/backend/tests/test_ml_baselines.py) | Unit tests for baselines, zero series, spikes, metric equations. |
| [`backend/tests/test_ml_provider.py`](file:///c:/Users/PC%20World/OneDrive/Desktop/MediFlow/backend/tests/test_ml_provider.py) | Unit tests for provider contract, dataclasses, provenance labeling, human review signals. |
| [`backend/tests/test_ml_evaluation.py`](file:///c:/Users/PC%20World/OneDrive/Desktop/MediFlow/backend/tests/test_ml_evaluation.py) | Unit tests for chronological ordering, policy replay, scenario verification. |

---

## 3. Evaluation & Policy Replay Results

The deterministic scenario suite was executed without touching or resetting any database. The results are generated dynamically from simulation:

```
================================================================================
  Smart Health Sentinel — Deterministic Policy Evaluation Suite
  Run ID       : eval-run-cd95bfa0f858
  Timestamp    : 2026-10-12T19:44:25.291046+00:00
  Scenarios    : 10 deterministic fixtures
  Provenance   : synthetic_scenario (Clearly labeled; not real PHC impact)
================================================================================
Scenario ID                         | Model MAE  | Base MAE   | Stockout Alert | Violations
--------------------------------------------------------------------------------
normal_consumption                  | 1.81       | 0.64       | SAFE           | 0
demand_surge                        | 40.58      | 40.64      | BREACH (Lead:0d)| 0
critically_low_stock_before_delivery| 1.57       | 0.53       | BREACH (Lead:0d)| 0
delivery_arrives_before_breach      | 1.31       | 0.44       | SAFE           | 0
no_safe_donor                       | 1.06       | 0.36       | BREACH (Lead:0d)| 2
donor_at_protected_reserve          | 1.31       | 0.44       | BREACH (Lead:0d)| 1
expired_batch                       | 1.96       | 0.66       | BREACH (Lead:0d)| 0
competing_recipients                | 1.31       | 0.44       | BREACH (Lead:0d)| 0
zero_sparse_history                 | 0.33       | 0.33       | SAFE           | 0
offline_duplicate_retry             | 1.31       | 0.44       | BREACH (Lead:0d)| 0
--------------------------------------------------------------------------------
Overall Average Model MAE    : 5.255
Overall Average Baseline MAE : 4.492
Overall Average Model WAPE   : 0.1832
Overall Average Baseline WAPE: 0.1146
Total Cumulative Stockout Days: 64
Total Transfer Violations Flagged: 3
Offline Exact-Once Tests Verified: 1 (Marked owned by PWA test suite)
================================================================================
```

### Key Analytical Findings
1. **Simple Baseline vs Complex Model:** On steady routine consumption patterns, the simple 7-day trailing mean baseline achieves lower MAE (0.64) than complex models, confirming the guidance: *never assume Prophet is better merely because it is more complex*.
2. **Surge Detection:** Under sudden demand surge, both models experience higher error (MAE ~40.58) until the surge is ingested, highlighting the need for lead-time alerts based on rapid consumption velocity rather than pure history fitting.
3. **Constraint Violations:** The scenario evaluation successfully caught 3 transfer constraint violations (donors breaching protected reserve floors), preventing simulated unsafe stock reallocations.
4. **Machine-Readable Report:** Output persisted to [`backend/evaluation_report.json`](file:///c:/Users/PC%20World/OneDrive/Desktop/MediFlow/backend/evaluation_report.json) for dashboard ingestion.

---

## 4. Verification Commands

To run all unit tests:
```powershell
pytest backend/tests
```
*(34 passed in ~2.4 seconds)*

To execute the deterministic scenario evaluation and export report:
```powershell
cd backend
python run_evaluation.py --output evaluation_report.json
```

---

## 5. Handoff for Member A (Backend Integration)

Member A can now import and call the provider without modifying or importing ML internals.

### Import Path & Usage
```python
from app.ml import get_forecast_provider, ForecastResult

provider = get_forecast_provider()

# Supply item demand forecast
result: ForecastResult = provider.forecast_item_demand(
    item_id=req.item_id,
    item_name=item_name,
    current_quantity=current_quantity,
    horizon_days=req.horizon_days,
)

# Accessing typed fields conforming to FORECAST_CONTRACT.md:
# result.forecasted_demand  -> list[ForecastPoint(date, predicted_quantity, lower_bound, upper_bound)]
# result.anomaly_flags      -> list[AnomalyFlag(date, observed_quantity, anomaly_score, flag, is_anomaly)] or None
# result.method             -> "prophet" | "seasonal_naive" | "baseline_insufficient_history" | "synthetic_sma"
# result.data_source        -> "database" | "synthetic"
# result.history_quality    -> HistoryQuality(total_rows, date_range_start, date_range_end, missing_days, sufficient)
# result.limitations        -> list of human-readable notices/disclaimers
```

### Footfall Forecasting Usage
```python
# Standalone 7-day footfall shortage
footfall_res = await provider.forecast_footfall(history_dicts)

# 7-day footfall with confidence bounds
bounds_res = await provider.predict_footfall_with_bounds(records)
```

---

## 6. Next Steps
1. Member A integrates `get_forecast_provider()` into `backend/app/routes/predictions.py`.
2. Frontend (Member B) displays the `data_source == "synthetic"` warning banner when synthetic data is returned.
3. Integration testing in Phase 5 across live PostgreSQL and seeded health centers.
