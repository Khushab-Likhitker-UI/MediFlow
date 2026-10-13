# Smart Health Sentinel — Scientific Evaluation & Forecasting Methodology

> **Evaluation Run ID:** `eval-run-2da1ccfd9dc5`  
> **Evaluator Source:** [`backend/run_evaluation.py`](file:///c:/Users/likhi/Desktop/Medicine_Helper/MediFlow/backend/run_evaluation.py) / [`backend/app/ml/evaluation/evaluator.py`](file:///c:/Users/likhi/Desktop/Medicine_Helper/MediFlow/backend/app/ml/evaluation/evaluator.py)  
> **Report Artifact:** [`backend/evaluation_report.json`](file:///c:/Users/likhi/Desktop/Medicine_Helper/MediFlow/backend/evaluation_report.json)  
> **Data Provenance:** Deterministic Synthetic Test Fixtures (Strictly labeled; not real-world field data)

---

## 1. Evaluation Philosophy & Scientific Rigor

1. **Chronological Holdout Splitting:**
   Time-series consumption data must never be evaluated using randomized k-fold cross-validation, which leaks future information into past predictions. All forecast evaluations use strictly forward-looking chronological holdout splits.
2. **Honest Baseline Benchmarking:**
   A machine-learning model (such as Prophet) cannot be assumed superior to simpler statistical baselines. Both the model and a 7-day Simple Moving Average (SMA) baseline are evaluated on identical test windows.
3. **Transparent Metric Reporting:**
   If a simple baseline achieves a lower error rate than a complex ML model on the evaluated scenario set, that finding is reported directly without manipulation.

---

## 2. Metric Formulations

### Mean Absolute Error (MAE)
$$\text{MAE} = \frac{1}{N} \sum_{t=1}^N |y_t - \hat{y}_t|$$
*Units:* Base units (e.g., tablets, vials) per day.

### Weighted Absolute Percentage Error (WAPE)
$$\text{WAPE} = \frac{\sum_{t=1}^N |y_t - \hat{y}_t|}{\sum_{t=1}^N y_t}$$
*Characteristics:* Robust against zero denominators common in low-volume rural PHC dispensaries.

### Warning Lead Time
The number of days between the initial reserve-breach alert generation and the date physical stock is depleted below the critical safety reserve.

### Transfer Safety Constraint Adherence
$$\text{Safety Compliance Rate} = 1.0 - \frac{\text{Unsafe Transfers Approved}}{\text{Total Proposals Evaluated}}$$
*Acceptance Standard:* Must be strictly 100% (zero approved transfers that breach donor safety reserve or exceed usable batch stock).

---

## 3. The 10 Deterministic Evaluation Scenarios

The test suite exercises 10 corner-case scenario fixtures designed to validate inventory policies and transfer decisions:

| Scenario ID | Test Condition | Expected Alert Behavior | Expected Donor Action |
|---|---|---|---|
| `normal_consumption` | Steady consumption, ample usable stock. | No alert raised (SAFE). | No redistribution required. |
| `demand_surge` | Sudden 5x spike in dispensing rate. | Immediate critical breach alert. | Recommends feasible transfer from peer facility. |
| `critically_low_stock_before_delivery` | Stock low, replenishment delivery 5 days away. | Critical shortage alert with lead time. | Proposes bridge transfer from surplus donor. |
| `delivery_arrives_before_breach` | Usable stock low, but verified shipment arrives tomorrow. | Warning alert with inbound delivery accounted for. | Transfer suppressed due to confirmed shipment. |
| `no_safe_donor` | Shortage facility surrounded by peer facilities with zero surplus. | Critical alert generated. | Explicit `no-safe-donor` result; 2 unsafe candidates rejected. |
| `donor_at_protected_reserve` | Candidate donor has stock, but donating would breach its own reserve. | Critical alert generated. | Candidate correctly rejected (0 units transferred). |
| `expired_batch` | Large physical stock, but 80% of units expired yesterday. | Immediate shortage alert on usable stock. | Expired stock excluded from transferable calculation. |
| `competing_recipients` | Two facilities simultaneously requesting stock from single donor. | Alerts generated for both. | Greedy allocation prevents double-allocation. |
| `zero_sparse_history` | Brand new PHC with fewer than 7 days of consumption history. | Fallback alert using reorder level. | Insufficient-history fallback mode active. |
| `offline_duplicate_retry` | Network timeout causes duplicate sync packet replay. | Alert generated normally. | Operation deduped; stock modified exactly once. |

---

## 4. Actual Evaluation Results & Analysis

```
================================================================================
  Smart Health Sentinel — Deterministic Policy Evaluation Suite
  Run ID       : eval-run-2da1ccfd9dc5
  Timestamp    : 2026-10-13T03:29:33.838364+00:00
  Scenarios    : 10 deterministic fixtures
================================================================================
Overall Average Model MAE    : 5.255
Overall Average Baseline MAE : 4.492
Overall Average Model WAPE   : 0.1832 (18.32%)
Overall Average Baseline WAPE: 0.1146 (11.46%)
Total Cumulative Stockout Days: 64
Total Transfer Violations Flagged: 3
Unsafe Transfers Approved    : 0 (100% Safety Enforcement)
================================================================================
```

### Key Analytical Takeaways
1. **Why the Baseline Outperformed Prophet in this Benchmark:**
   The 7-day Simple Moving Average achieved lower error (MAE 4.492 vs 5.255) because several test scenarios feature short, stationary time horizons where Prophet's trend and seasonality parameters introduce unnecessary variance. In production, MediFlow uses an adaptive model selector: Prophet is deployed on facilities with > 60 days of historical data and strong day-of-week seasonality, while the SMA baseline is used for sparse or stationary records.
2. **Deconstruction of the "3 Transfer Violations Flagged":**
   The 3 violations recorded in the report represent **detected and successfully prevented unsafe proposals** (2 in `no_safe_donor` and 1 in `donor_at_protected_reserve`). Exactly **0 unsafe transfers were approved**.

---

## 5. Scope Boundary: Synthetic vs Real-World Evidence

> [!IMPORTANT]
> All evaluation metrics documented herein are derived from reproducible synthetic scenario fixtures executed locally. They demonstrate software correctness, algorithm stability, and boundary enforcement. MediFlow makes **no claims of real-world patient impact, percentage reductions in mortality, or live clinical deployment** until formal field pilot authorization is conducted.
