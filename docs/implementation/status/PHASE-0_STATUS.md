# Smart Health Sentinel — Phase 0 Status Report

> **Repository:** `https://github.com/AmitRK9819/Smart_Health`  
> **Checked-out Branch:** `main`  
> **Baseline Commit:** `cfe59689c9f407511e203455b6ae8b91e781bc4c`  
> **Date Frozen:** 2026-10-13  
> **Author:** Staff Engineer (Coordination)  
> **Phase:** Phase 0 — Baseline & Contract Documents (COMPLETE)

---

## 1. Executive Summary

Phase 0 establishes a verified baseline and formal contracts for the multi-person implementation of **Smart Health Sentinel**. No product features were implemented in this phase, adhering strictly to engineering constraints. 

All six canonical architecture and contract documents, along with status tracking and PR templates, have been authored and frozen. Tracked credentials in example environment files have been replaced with safe placeholders, `.gitignore` has been strengthened, and human rotation steps have been documented.

---

## 2. Confirmed Findings vs Uncertain/Deployment-Dependent Findings

### 2.1 Confirmed Findings (Codebase Verified)

| Component | Code Inspection Finding | File Reference | Status |
|---|---|---|---|
| **Credential Exposure** | Tracked `.env.example` files in `backend/` and `database/` contained live Supabase connection strings with plain-text credentials. Similar strings exist as fallback defaults in Python source files. | `backend/.env.example`, `database/.env.example`, `backend/app/core/config.py`, `backend/app/db.py`, `database/db.py` | Example files scrubbed; human out-of-band credential rotation required (ADR-003). |
| **Authentication** | `POST /api/v1/users/login` checks credentials using `passlib[bcrypt]` against the `users` table, but generates a pseudo-token (`jwt-supabase-{id}-{role}`). No authentication middleware or dependency checks exist on other endpoints. | `backend/app/routes/users.py`, `frontend/src/components/LoginPage.jsx` | Documented in ADR-005; Phase 1 will implement signed JWT and FastAPI dependencies. |
| **CORS Policy** | CORS middleware in FastAPI enables `allow_origin_regex=".*"` alongside `allow_credentials=True`. This effectively allows cross-origin requests from any domain regardless of `allow_origins`. | `backend/main.py` | Documented in ADR-004; Phase 1 will lock down CORS origins. |
| **PHC PWA Sync & API URL** | The PWA service worker and sync service hardcode `http://localhost:8000/api/v1`. Unlike `frontend/src/config.js` (which inspects `import.meta.env.VITE_API_URL`), the PHC app cannot be configured via environment variables without code modification. | `phc-app/src/services/syncService.js`, `phc-app/src/db/indexedDB.js` | Documented in ADR-011; Member C will extract to `VITE_API_URL` in Phase 3. |
| **Aggressive Polling** | The web dashboard executes `fetchLiveData(false)` every 4000ms (4 seconds), causing frequent database queries across facilities, inventory, beds, and attendance. | `frontend/src/App.jsx` (L46) | Documented in ADR-012; Member B to tune polling or adopt push notifications in Phase 2. |
| **File Duplication** | Root `requirements.txt`, `Procfile`, and `railway.json` are duplicates of `backend/requirements.txt`, `backend/Procfile`, and `backend/railway.json` to satisfy Railway Nixpacks build requirements. | Repository root vs `backend/` | Documented in INTEGRATION_GUIDE.md §9. |
| **Database & ORM** | PostgreSQL 16 schema (`database/schema.sql`) uses pure relational tables with UUID/serial keys and raw `psycopg2` parameterized SQL. No ORM (SQLAlchemy/Prisma) is used. | `database/schema.sql`, `backend/app/db.py` | Preserved as baseline architecture (ADR-001). |

### 2.2 Uncertain / Deployment-Dependent Findings

| Component | Uncertainty / Verification Need | Impact | Recommended Action |
|---|---|---|---|
| **Supabase Connection Pooler** | Port 6543 pooler mode (transaction mode) vs direct port 5432: Does Supabase transaction pooler support prepared statements and table locks expected by raw psycopg2 queries under high concurrency? | Potential connection timeout or transaction abort under concurrent writes. | Verify against live Supabase instance using `verify_backend.py` with multi-client load test. |
| **Production Railway Deployment** | Current Railway deployment (`smarthealth-production.up.railway.app`) relies on repository config. Whether Railway environment variables are already populated or if it falls back to hardcoded code strings is unknown. | If Railway lacks configured env vars, removing code fallbacks prematurely could crash production. | Repository owner must verify Railway project dashboard variables before Member A removes Python fallback URLs. |
| **Facebook Prophet Performance** | Prophet fitting in Python on serverless/constrained containers (e.g., Railway free tier memory limits): Prophet models can consume significant memory and CPU during fitting. | High latency or memory limits on large historical series. | Member D to benchmark memory footprint in Phase 4 and verify fallback to SMA under high memory pressure. |
| **PWA Cache & Storage Limits** | IndexedDB storage limitations and service worker background sync reliability on varied mobile browsers (Safari iOS vs Chrome Android). | Potential offline sync failures on restricted mobile devices. | Member C to test offline mutation queues across Chromium and WebKit mobile viewports. |

---

## 3. Deliverables Summary

| Artifact | Path | Purpose |
|---|---|---|
| **Phase Plan** | `docs/implementation/PHASE_PLAN.md` | Multi-phase plan assigning Phases 0–5 to team members with strict boundaries. |
| **Domain Model** | `docs/implementation/DOMAIN_MODEL.md` | ER diagrams and frozen domain conventions (units, provenance, usable stock, etc.). |
| **Authoritative API Contract** | `docs/implementation/API_CONTRACT.md` | Full typed contract of existing and Phase 1 endpoints with permissions and errors. |
| **Forecast Provider Contract** | `docs/implementation/FORECAST_CONTRACT.md` | Decoupled `ForecastProvider` interface isolating Member A routes from Member D ML. |
| **Integration Guide** | `docs/implementation/INTEGRATION_GUIDE.md` | Verified local setup commands, Docker/database steps, and test scripts. |
| **Architecture Decisions** | `docs/implementation/DECISIONS.md` | Immutable ADRs (ADR-001 through ADR-012) capturing architectural baselines. |
| **PR Checklist Template** | `.github/pull_request_template.md` | Pull request template enforcing boundary reviews and secret hygiene. |
| **Root API Contract Notice** | `API_CONTRACT.md` | Top-level notice redirecting developers to authoritative specification. |
| **Root .gitignore** | `.gitignore` | Hardened patterns ignoring `.env.*`, certificates, keys, and `node_modules/`. |
| **Safe Example Files** | `backend/.env.example`, `database/.env.example` | Sanitized configuration templates containing safe placeholders only. |

---

## 4. Security Action Plan

> [!CAUTION]
> **Live Credentials in Git History Require Out-of-Band Rotation**
> 
> Commit `cfe59689c9f407511e203455b6ae8b91e781bc4c` (and prior commits) contained plaintext credentials in `.env.example` files and Python fallbacks.
> 
> 1. The repository owner must **immediately change the database password** in the Supabase Console.
> 2. Update the environment variables in the Railway deployment settings.
> 3. In Phase 1, Member A will remove the fallback connection strings from `config.py` and `db.py` once the secret is rotated.
> 4. History scrubbing (e.g., via `git filter-repo`) should be coordinated separately after team branches are aligned.

---

## 5. Team Ownership & Branch Strategy

```
main (baseline: cfe5968)
 ├── phase-0/baseline-contracts   (Staff Eng — Ready for Merge)
 ├── phase-1/backend-routes       (Member A: backend/app/routes/, backend/app/models/)
 ├── phase-2/web-dashboard        (Member B: frontend/src/)
 ├── phase-3/phc-pwa              (Member C: phc-app/src/)
 ├── phase-4/ml-forecast          (Member D: backend/app/ml/)
 └── phase-5/integration          (All members: integration & end-to-end testing)
```

Phase 0 is complete. Implementation teams may now branch from `main` (once Phase 0 is merged) and develop against their respective frozen specifications.
