# Smart Health Sentinel — Phase 1A Status Report

> **Role:** Member A — Backend Domain Services, Database Integrity, and API  
> **Branch:** `feat/sentinel-backend`  
> **Date:** 2026-10-13  
> **Status:** COMPLETE  

---

## 1. Executive Summary

Member A has implemented the backend-authoritative operational workflow for projected medicine shortages, safe inter-facility redistributions, and cryptographic role-based authorization according to Prompt 1A and the frozen Phase 0 specifications.

All domain rules are decoupled from HTTP controllers into pure, deterministic service modules, and 46 automated tests pass with 100% success rate.

---

## 2. Completed Milestones

| Milestone | Deliverables | Status |
| :--- | :--- | :--- |
| **Milestone 1: Baseline & Design** | Mapped existing schema and routes; created additive reversible migrations `database/migrations/001_sentinel_phase1a.sql` and rollback script. | ✅ COMPLETE |
| **Milestone 2: Inventory & Projection** | Built batch-aware usable stock engine with FEFO sorting, expiry exclusion, reservation subtraction, and canonical unit validation (`app/domain/inventory.py`); built deterministic stock projection engine (`app/domain/projection.py`). | ✅ COMPLETE |
| **Milestone 3: Safe Donor & Proposal Engine** | Built multi-facility candidate evaluator protecting donor reserve, donor projected demand, and batch shelf-life; implemented deterministic ranking and no-safe-donor escalation (`app/domain/donor.py`). | ✅ COMPLETE |
| **Milestone 4: Transfer State Machine & Ledger** | Implemented state machine (`PROPOSED -> APPROVED -> DISPATCHED -> RECEIVED -> RECONCILED`), atomic reservation locking, and idempotency tracking (`app/domain/transfer.py`, `app/routes/transfers.py`). | ✅ COMPLETE |
| **Milestone 5: API, Auth & Authorization** | Implemented JWT token issuance/verification (`PyJWT`), role enforcement (`admin`, `manager`, `viewer`), district-level authority checks, locked-down CORS origins, registered endpoints in `main.py`. | ✅ COMPLETE |
| **Milestone 6: Tests & Verification** | Created 46 automated unit and integration tests across 5 test modules in `backend/tests/`; 100% pass rate. | ✅ COMPLETE |

---

## 3. Endpoints Implemented & Exposed

| Method | Path | Summary & Permissions |
| :--- | :--- | :--- |
| `POST` | `/api/v1/users/login` | Issues real cryptographic signed JWT access token (`HS256`). |
| `GET` | `/api/v1/users/me` | Returns profile and claims of authenticated user. |
| `POST` | `/api/v1/transfers/propose` | Propose inter-facility stock transfer (Idempotent via `client_operation_id`). |
| `POST` | `/api/v1/transfers/{id}/approve` | Revalidates stock, places active reservation hold, transitions to `approved` (Admin/Manager). |
| `POST` | `/api/v1/transfers/{id}/reject` | Rejects proposal with mandatory justification (Admin/Manager). |
| `POST` | `/api/v1/transfers/{id}/dispatch` | Deducts donor physical stock, fulfills hold, logs `transferred_out` (Admin/Manager). |
| `POST` | `/api/v1/transfers/{id}/receive` | Adds to destination stock, logs `transferred_in`, handles partial receipts (Authenticated). |
| `GET` | `/api/v1/transfers/` | Lists transfers with status, facility, and item filters. |
| `GET` | `/api/v1/transfers/{id}` | Fetches single transfer with facility and medicine metadata. |
| `GET` | `/api/v1/transfers/candidates/evaluate`| Evaluates and ranks candidate donor facilities for a given deficit. |
| `GET` | `/api/v1/alerts/` | Scans facilities for critical shortages, reserve breaches, and expiring batches. |
| `GET` | `/api/v1/alerts/{alert_id}` | Detailed alert inspection. |
| `POST` | `/api/v1/stock-movements` | Ingests offline PWA stock events with exact-once idempotency (`client_operation_id`). |
| `GET` | `/api/v1/facility/{phc_id}/inventory`| Returns batch-level inventory, expiry dates, reservations, and usable stock. |

---

## 4. Database Migrations

- **Migration File:** `database/migrations/001_sentinel_phase1a.sql`
  - Creates `processed_operations` (idempotency ledger).
  - Creates `transfers` (state machine with `client_operation_id` unique index).
  - Creates `stock_reservations` (atomic stock reservation holds).
  - Creates `audit_events` (immutable operational audit trail).
  - Adds triggers for auto-updating `updated_at`.
- **Rollback File:** `database/migrations/001_sentinel_phase1a_rollback.sql`
  - Reversible drop of all added triggers, functions, and tables.

---

## 5. Verification Commands and Test Results

```powershell
python -m pytest backend/tests -v
```

**Results:**
- `backend/tests/test_inventory_usable_stock.py`: 8 passed
- `backend/tests/test_stock_projection.py`: 5 passed
- `backend/tests/test_safe_donor_engine.py`: 7 passed
- `backend/tests/test_transfer_state_machine.py`: 7 passed
- `backend/tests/test_auth_and_permissions.py`: 5 passed
- `backend/tests/test_api_endpoints.py`: 14 passed
- **Total:** **46 passed, 0 failed in 0.86s**

---

## 6. Environment & Configuration Changes

The following environment variables have been introduced in `backend/app/core/config.py`:
- `JWT_SECRET_KEY`: Secret string for signing JWT tokens (default development key provided).
- `JWT_ALGORITHM`: Token algorithm (default: `HS256`).
- `JWT_EXPIRE_MINUTES`: Expiration window (default: `1440` minutes / 24 hours).
- `PLANNING_HORIZON_DAYS`: Stockout projection horizon (default: `30` days).
- `SAFETY_RESERVE_DAYS`: Safety stock buffer (default: `7` days).

---

## 7. Known Gaps & Handoff Notes

- **Forecast Provider Boundary:** Member A created `app/domain/forecast_client.py` adhering to `docs/implementation/FORECAST_CONTRACT.md`. When Member D publishes `app/ml/provider.py`, the backend will dynamically call Member D's Prophet engine; until then, it seamlessly falls back to the transparent deterministic baseline with explicit provenance labels.
- **Frontend / PWA Handoff:**
  - Member B (Web Dashboard) can consume `GET /api/v1/alerts/`, `GET /api/v1/transfers/candidates/evaluate`, and `POST /api/v1/transfers/{id}/approve` directly.
  - Member C (PHC PWA) can consume `POST /api/v1/stock-movements` sending its persistent `client_operation_id`. Duplicate retransmissions will be recognized and acknowledged without double-counting stock.
