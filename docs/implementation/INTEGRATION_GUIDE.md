# Smart Health Sentinel — Local Integration Guide

> **Baseline commit:** `cfe5968` (branch: `main`)
> **Date frozen:** 2026-10-13

All commands below are **verified from repository config files** — not guessed.

---

## 1. Prerequisites

| Tool | Minimum Version | Verification |
|---|---|---|
| Python | 3.10+ | `python --version` |
| pip | latest | `pip --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |
| PostgreSQL | 16 | `psql --version` or Docker |

---

## 2. Database Setup

### Option A: Docker (recommended for local dev)

```powershell
# From project root:
cd database
docker compose up -d
```

**Source:** `database/docker-compose.yml` — starts PostgreSQL 16 + pgAdmin.

| Service | Port | Default Credentials |
|---|---|---|
| PostgreSQL | 5432 | user: `smarthealth`, password: `smarthealth_dev`, db: `smarthealth_db` |
| pgAdmin | 5050 | email: `admin@smarthealth.local`, password: `admin` |

The `schema.sql` is auto-loaded via Docker entrypoint (`/docker-entrypoint-initdb.d/init.sql`).

### Option B: Native PostgreSQL

```powershell
psql -U postgres -c "CREATE DATABASE smarthealth_db;"
psql -U postgres -c "CREATE USER smarthealth WITH PASSWORD 'smarthealth_dev';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE smarthealth_db TO smarthealth;"
psql -U smarthealth -d smarthealth_db -f database/schema.sql
```

### Option C: Supabase (cloud)

Configure `DATABASE_URL` in your `.env` to point to your Supabase pooler endpoint.
The schema must be applied manually via the Supabase SQL Editor or `psql` using the direct connection URL.

---

## 3. Environment Variables

### 3.1 Backend (`backend/.env`)

Copy from template:
```powershell
cd backend
Copy-Item .env.example .env
```

Edit `.env` and set `DATABASE_URL` to your actual connection string.

| Variable | Required | Default | Notes |
|---|---|---|---|
| `DATABASE_URL` | ✅ | *(placeholder)* | PostgreSQL connection URI |
| `APP_NAME` | ❌ | `Healthcare Supply Chain API` | |
| `APP_VERSION` | ❌ | `0.1.0` | |
| `DEBUG` | ❌ | `true` | Set `false` in production |
| `CORS_ORIGINS` | ❌ | localhost:3000,5173,5174 + production URLs | Comma-separated |

### 3.2 Database Seeder (`database/.env`)

Copy from template:
```powershell
cd database
Copy-Item .env.example .env
```

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | ✅ | Same DB as backend |
| `DIRECT_DATABASE_URL` | ❌ | For schema migrations bypassing pooler |

### 3.3 Frontend (`frontend/.env`)

No template exists. Create manually if needed:
```
VITE_API_URL=http://localhost:8000
```

**Default behavior (from `frontend/src/config.js`):** Falls back to
`https://smarthealth-production.up.railway.app` when `VITE_API_URL` is not set.

> ⚠️ For local development, you MUST set `VITE_API_URL=http://localhost:8000` or the
> dashboard will connect to the production Railway deployment.

### 3.4 PHC App (`phc-app/`)

The API base URL is **hardcoded** in `phc-app/src/services/syncService.js`:
```javascript
const API_BASE_URL = 'http://localhost:8000/api/v1';
```

> ⚠️ Phase 3 should extract this to a `.env` variable (`VITE_API_URL`).

---

## 4. Seed the Database

```powershell
cd database
pip install psycopg2-binary python-dotenv passlib[bcrypt]
python seed.py
```

**Source:** `database/seed.py` — idempotent (`ON CONFLICT DO NOTHING`).

Seeds:
- 3 users (admin, manager, viewer)
- 10 facilities (PHC-001 through PHC-010)
- 25 medicines with dosage forms
- Inventory batches per facility/medicine (with intentional shortages/surpluses)
- 180 days of daily consumption history + footfall
- Personnel and attendance records
- Beds availability

**Seeded login credentials:**

| Email | Password | Role |
|---|---|---|
| `admin@smarthealth.local` | `admin123` | admin |
| `manager1@smarthealth.local` | `manager123` | manager |
| `viewer1@smarthealth.local` | `viewer123` | viewer |

---

## 5. Start the Backend

```powershell
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Source:** `backend/Procfile`, `backend/main.py`

Verify: Open `http://localhost:8000/docs` for Swagger UI.

---

## 6. Start the Web Dashboard

```powershell
cd frontend
npm install
npm run dev
```

**Source:** `frontend/package.json` — scripts: `dev`, `build`, `lint`, `preview`

Runs on: `http://localhost:5173` (Vite default)

---

## 7. Start the PHC Offline PWA

```powershell
cd phc-app
npm install
npm run dev -- --port 5174
```

**Source:** `phc-app/package.json` — scripts: `dev`, `build`, `lint`, `preview`

Runs on: `http://localhost:5174`

---

## 8. Available Test/Verification Commands

| What | Command | Working Dir | Notes |
|---|---|---|---|
| Backend smoke test (footfall) | `python verify_backend.py` | `backend/` | Requires backend running on :8000 |
| Backend integration test (shortage) | `python test_predictions.py` | `backend/` | Requires backend running on :8000 |
| Frontend lint | `npm run lint` | `frontend/` | Uses `oxlint` |
| PHC app lint | `npm run lint` | `phc-app/` | Uses `oxlint` |
| Frontend build | `npm run build` | `frontend/` | Vite production build |
| PHC app build | `npm run build` | `phc-app/` | Vite production build |

> **No pytest suite exists yet.** Phase 1 should add `pytest` tests in `backend/tests/`.
> No CI pipeline (GitHub Actions) exists yet.

---

## 9. Deployment Configuration

| File | Purpose |
|---|---|
| `Procfile` (root) | Railway/Heroku: starts uvicorn from `backend/` |
| `railway.json` (root) | Railway platform config: Nixpacks builder |
| `backend/Procfile` | Duplicate Procfile in backend dir |
| `backend/railway.json` | Duplicate Railway config in backend dir |
| `requirements.txt` (root) | Python deps — **identical copy** of `backend/requirements.txt` |

> ⚠️ The root `requirements.txt` and `Procfile` are duplicates of the ones in `backend/`.
> Railway reads from the project root, so both copies must stay in sync.

---

## 10. Branch Strategy & Ownership

See `docs/implementation/PHASE_PLAN.md` for full details.

| Phase | Branch | Owner | Owned Paths |
|---|---|---|---|
| 0 | `phase-0/baseline-contracts` | Staff Eng | `docs/`, `.github/`, `.env.example` files |
| 1 | `phase-1/backend-routes` | Member A | `backend/app/routes/`, `backend/app/models/` |
| 2 | `phase-2/web-dashboard` | Member B | `frontend/src/` |
| 3 | `phase-3/phc-pwa` | Member C | `phc-app/src/` |
| 4 | `phase-4/ml-forecast` | Member D | `backend/app/ml/` |
| 5 | `phase-5/integration` | All | Cross-cutting |

### Shared files (coordinate changes)

- `backend/main.py` — router registration (Member A adds new routers)
- `backend/app/db.py` — database helpers (Staff Eng reviews changes)
- `database/schema.sql` — schema (Staff Eng reviews, no Phase 0 changes)
- `database/seed.py` — seed data (coordinate between phases)
- `requirements.txt` — Python deps (any member may add, Staff Eng reviews)

---

## 11. .gitignore Coverage

The root `.gitignore` covers:
- ✅ `.env` files
- ✅ `__pycache__/`, `*.pyc`
- ✅ `venv/`, `.venv/`
- ✅ `*.sqlite3`, `*.db`
- ✅ `.vscode/`, `.idea/`
- ❌ `node_modules/` — **NOT in root .gitignore** (but in `frontend/.gitignore` and `phc-app/.gitignore`)
- ❌ `dist/`, `build/` for JS — partially covered by frontend/phc-app `.gitignore`

> Both `frontend/.gitignore` and `phc-app/.gitignore` include `node_modules` and `dist`.
