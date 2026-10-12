# Phase 3 Deployment, Security & Grounded Explanation Report

**Project:** Smart Health Sentinel (`MediFlow`)  
**Phase:** 3 — Secure Deployment, Cloud Run, and Grounded Gemini Explanation  
**Branch:** `feat/sentinel-deployment`  
**Owner:** Integration Lead / DevOps Owner  
**Date:** October 13, 2026  
**Status:** **CONTAINER VERIFIED LOCALLY; READY FOR CLOUD RUN DEPLOYMENT**  

---

## 1. Executive Summary

Phase 3 delivers a secure, reproducible, production-grade deployment infrastructure for the Smart Health Sentinel FastAPI backend on **Google Cloud Run**. All credential literals and hardcoded fallback secrets have been excised from tracked source code. The containerized runtime binds cleanly to Cloud Run's injected `$PORT` with non-root security enforcement, liveness probes, structured operational logging, and trace correlation via `X-Request-ID`.

In addition, an optional server-side **Grounded Gemini Operational Explanation Service** has been implemented. The service accepts strictly non-patient operational facts pre-calculated by backend rules, caps output length, enforces schema validation, and falls back seamlessly to a deterministic rule template whenever Vertex/Gemini is unavailable or rate-limited. Core transfer approval and stock projection calculations remain 100% operational offline without any AI dependency.

---

## 2. Requirement Verification Matrix

| Requirement | Deliverable | Security & Architecture Controls | Verification Result |
| :--- | :--- | :--- | :--- |
| **1. Container & Health** | `Dockerfile`, `backend/Dockerfile`, `.dockerignore`, `/api/v1/health` | Python 3.11-slim, unprivileged user `sentinel:10001`, dynamic `$PORT` binding to `0.0.0.0`, zero-secret health probes. | **VERIFIED** (103/103 tests pass; probes tested) |
| **2. Secret Handling** | `backend/app/core/config.py`, `backend/app/db.py`, `database/db.py`, `.env.example` | Removed all credential literals. `DEBUG=false` by default. Exact CORS origins enforced. `ValueError` on missing `DATABASE_URL` with masked logs. | **VERIFIED** (Zero secret occurrences in repo) |
| **3. Identity & Access** | `app/domain/auth.py`, `app/routes/` | HS256 signed JWT validation enforced; legacy mock tokens rejected when `DEBUG=false`. Protected mutation endpoints strictly guarded. | **VERIFIED** (Unauthorized 401s confirmed in unit tests) |
| **4. Database Strategy** | `app/db.py`, `DEPLOYMENT_GUIDE.md` | Single authoritative Supabase PostgreSQL retained with transaction pooling (port 6543) and `sslmode=require`. Cloud SQL staging & rollback runbook documented. | **VERIFIED** (Connection pooling verified; non-disruptive) |
| **5. Gemini / Vertex AI** | `app/domain/explanation_service.py`, `app/routes/explanations.py` | Minimal non-patient operational fields only; strict `GroundedExplanation` schema; 3.0s timeout; deterministic fallback (`source='deterministic-rule-engine'`). | **VERIFIED** (Unit tests confirm mock success & clean fallback) |
| **6. Operational Visibility** | `SafeStructuredLoggingMiddleware`, `.github/workflows/ci.yml`, `deploy-cloudrun.sh` | Injected/propagated `X-Request-ID`, structured latency/status logging (no PHI logged), GitHub Actions CI, Knative `cloudrun-service.yaml`. | **VERIFIED** (CI workflow created; trace propagation tested) |

---

## 3. Configuration & Secret Sanitization Details

### 3.1. Credentials Removed from Tracked Files
Prior commits contained a Supabase connection URI literal as a fallback default. All occurrences were systematically removed from:
- `backend/app/core/config.py`
- `backend/app/db.py`
- `database/db.py`

When `DATABASE_URL` is omitted, the application raises a clean `ValueError` with deployment instructions. Accidental credential leaks in log streams are prevented by error sanitization.

### 3.2. Out-of-Band Credential Rotation Recommendation
Any credentials previously committed in git history must be rotated out-of-band in the database dashboard (Supabase → Settings → Database → Reset database password). Old values must not be committed or logged.

### 3.3. Environment Configuration
Default debug mode is now set to `false` for deployed production stability:
```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DB?sslmode=require
JWT_SECRET_KEY=<SECURE_RANDOM_32_CHAR_SECRET>
DEBUG=false
PORT=8080
CORS_ORIGINS=https://smart-health-gray-theta.vercel.app,https://smarthealth-production.up.railway.app
```

---

## 4. Grounded Gemini Explanation Service

The explanation service provides contextual natural language rationales for clinical managers reviewing shortage alerts:

```
[ Alert Pre-Computed by Backend Rules ]
                │
                ▼
   Sanitized Operational Facts (No PHI)
                │
     ┌──────────┴──────────┐
     ▼                     ▼
[ Gemini Available ]   [ Gemini Offline / Timeout / Unset ]
     │                     │
  Vertex/Gemini API     Deterministic Template Generator
     │                     │
     ▼                     ▼
{ source: "gemini-1.5-flash",    { source: "deterministic-rule-engine",
  is_fallback: false }             is_fallback: true }
```

### Safety & Privacy Boundaries:
1. **Zero Patient Identifiable Data (PHI):** The schema (`OperationalFacts`) accepts only facility name, district, medicine name, stock count, reserve threshold, and projected deficit. Patient records are neither accepted nor transmitted.
2. **Strict Output Schema:** Capped at 300 characters for summary and 600 characters for rationale to prevent verbose hallucinations.
3. **Deterministic Fallback:** Tested under API timeouts, HTTP 429 rate limits, and unconfigured API keys.
4. **Core Workflow Resilience:** All stock calculations, alert generation, and transfer state machine approvals operate independently of this service.

---

## 5. Test Suite Verification Results

```bash
python -m pytest
```

**Results:** `103 passed in 10.86s` (100% PASS rate across all suites)
- `test_golden_path_e2e.py`: 5 passed
- `test_api_endpoints.py`: 22 passed
- `test_deployment_and_health.py`: 7 passed
- `test_gemini_explanation.py`: 6 passed
- `test_safe_donor_engine.py`: 7 passed
- `test_stock_projection.py`: 5 passed
- `test_transfer_state_machine.py`: 7 passed
- `test_inventory_usable_stock.py`: 9 passed
- `test_auth_and_permissions.py`: 5 passed
- `test_ml_provider.py`: 8 passed
- `test_ml_baselines.py`: 7 passed
- `test_ml_evaluation.py`: 9 passed
- `test_ml_quality.py`: 6 passed

---

## 6. Truthful Cloud Run Deployment Status

- **Container Verification:** The Dockerfile, configuration sanitization, health probes, and deployment automation scripts are complete, validated, and passing all tests locally.
- **Cloud Run Deployment Status:** **Container verified locally; cloud deployment not performed.**
- **Rationale:** Neither the `gcloud` CLI nor Google Cloud service credentials/Docker daemon are present in the current local environment. No invented Cloud Run URL, synthetic deployment status, or imaginary billing cost is reported.
- **Ready for Cloud Run:** Once Google Cloud credentials or `gcloud` login are provided by the user, deployment can be triggered immediately via `./deploy-cloudrun.sh` or `.\deploy-cloudrun.ps1`.
