# Smart Health Sentinel — Phase Plan

> **Baseline commit:** `cfe5968` (branch: `main`)
> **Date frozen:** 2026-10-13
> **Phase 0 author:** Staff Engineer (coordination)

---

## Phase 0 — Baseline & Contract Documents ✅

**Owner:** Staff Engineer (coordination)
**Branch:** `phase-0/baseline-contracts`
**Status:** CURRENT

| Deliverable | File |
|---|---|
| Phase plan | `docs/implementation/PHASE_PLAN.md` (this file) |
| Domain model | `docs/implementation/DOMAIN_MODEL.md` |
| API contract (authoritative) | `docs/implementation/API_CONTRACT.md` |
| Forecast provider interface | `docs/implementation/FORECAST_CONTRACT.md` |
| Integration guide | `docs/implementation/INTEGRATION_GUIDE.md` |
| Architecture decisions | `docs/implementation/DECISIONS.md` |
| PR checklist template | `.github/pull_request_template.md` |
| Security: .env.example credential scrub | `backend/.env.example`, `database/.env.example` |

---

## Phase 1 — Backend Routes & Business Logic

**Owner:** Member A
**Branch:** `phase-1/backend-routes`

### Scope

- Implement/refine all routes defined in `docs/implementation/API_CONTRACT.md`
- Own `backend/app/routes/`, `backend/app/models/schemas.py`
- Integrate `ForecastProvider` interface (call site only — implementation is Member D's)
- Add `client_operation_id` idempotency middleware
- Implement transfer lifecycle (propose → approve → reject → dispatch → receive)
- Add role/facility permission checks to every endpoint
- Write `pytest` unit tests for each endpoint

### Does NOT own

- ML model implementation (Member D)
- Frontend UI (Members B, C)
- Database schema changes (coordinate with Staff Eng)

---

## Phase 2 — Web Dashboard (frontend/)

**Owner:** Member B
**Branch:** `phase-2/web-dashboard`

### Scope

- Own `frontend/src/` entirely
- Consume API contract endpoints for facility list, inventory, forecasts, alerts, transfers
- Implement login with JWT tokens (when backend provides them)
- Display forecast charts (Recharts)
- Build transfer proposal/approval UI
- Maintain `frontend/src/config.js` API base URL pattern

### Does NOT own

- Backend routes (Member A)
- PHC offline app (Member C)
- ML models (Member D)

---

## Phase 3 — PHC Offline-First PWA (phc-app/)

**Owner:** Member C
**Branch:** `phase-3/phc-pwa`

### Scope

- Own `phc-app/src/` entirely
- Maintain IndexedDB sync queue (`phc-app/src/db/`, `phc-app/src/services/`)
- Implement offline stock update forms and sync-on-reconnect
- Consume beds, attendance, and inventory endpoints
- Add `client_operation_id` to every queued mutation for idempotent sync
- Manage PWA service worker configuration (`vite.config.js` VitePWA plugin)

### Does NOT own

- Backend routes (Member A)
- Web dashboard (Member B)
- ML models (Member D)

---

## Phase 4 — Forecasting & Anomaly Detection Module

**Owner:** Member D
**Branch:** `phase-4/ml-forecast`

### Scope

- Own `backend/app/ml/` entirely
- Implement the `ForecastProvider` interface defined in `docs/implementation/FORECAST_CONTRACT.md`
- Maintain Prophet and Isolation Forest model fitting
- Ensure synthetic fallback is clearly labeled (see DECISIONS.md §Synthetic-Demo)
- Provide typed result schemas matching the forecast contract
- Write unit tests for forecast/anomaly pipelines

### Does NOT own

- Route wiring (Member A calls the provider)
- Frontend display (Members B, C)
- Database schema (coordinate with Staff Eng)

---

## Phase 5 — Integration Testing & Polish

**Owner:** All members + Staff Engineer
**Branch:** `phase-5/integration`

### Scope

- End-to-end test: seed → backend → dashboard → PHC app → forecast
- CORS lockdown for production
- Secret audit (no hardcoded credentials remain)
- Performance profiling (connection pool, Prophet thread pool)
- README update with final deployment instructions

---

## Branch Strategy

```
main (protected)
├── phase-0/baseline-contracts   ← Staff Eng, merge first
├── phase-1/backend-routes       ← Member A, depends on Phase 0
├── phase-2/web-dashboard        ← Member B, depends on Phase 0
├── phase-3/phc-pwa              ← Member C, depends on Phase 0
├── phase-4/ml-forecast          ← Member D, depends on Phase 0
└── phase-5/integration          ← All, depends on Phases 1-4
```

- All feature branches are created from `main` after Phase 0 merges.
- Each member opens PRs into `main` using the PR checklist template.
- Merge order: Phase 0 → (1, 2, 3, 4 in parallel) → 5.
- Conflicts between parallel phases are resolved during Phase 5 integration.
