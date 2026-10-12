# Smart Health Sentinel — Architecture Decisions

> **Baseline commit:** `cfe5968` (branch: `main`)
> **Date frozen:** 2026-10-13

Each decision is numbered and immutable once frozen. New decisions get new numbers.

---

## ADR-001: Preserve Existing Architecture

**Status:** ACCEPTED

**Context:** The repository has a working FastAPI backend, React/Vite frontend, React/Vite PWA,
and PostgreSQL database with raw SQL (no ORM). The Sentinel redesign adds capabilities but
does not rewrite the foundation.

**Decision:** All phases build on the existing architecture. No wholesale rewrites.
No migration to an ORM (SQLAlchemy/Prisma). Keep psycopg2 parameterized SQL.

**Consequences:**
- New tables require manual `ALTER TABLE` or new `CREATE TABLE` statements.
- No auto-generated migrations — schema changes are coordinated by Staff Engineer.

---

## ADR-002: No Database Migration in Phase 0

**Status:** ACCEPTED

**Context:** Phase 0 is documentation and contracts only.

**Decision:** Phase 0 does not modify `database/schema.sql`, run migrations, or reset any database.

**Consequences:** Phase 1 will add a `transfers` table and possibly `alerts` table.

---

## ADR-003: Credential Rotation Required

**Status:** ACCEPTED — URGENT

**Context:** The `.env.example` files in `backend/` and `database/` contained what appears to be
a live Supabase database connection string with embedded password. The same credential is
hardcoded as a fallback default in:
- `backend/app/core/config.py` (line 48-49)
- `backend/app/db.py` (line 49-50)
- `database/db.py` (line 33-34)

These credentials are present in git history even after the `.env.example` files are cleaned.

**Decision:**
1. `.env.example` files have been scrubbed to contain only placeholders (Phase 0 deliverable).
2. The hardcoded fallback defaults in Python source files are **not modified in Phase 0** to
   avoid breaking the production Railway deployment.
3. The repository owner MUST:
   - **Rotate the Supabase database password immediately** (out-of-band).
   - In Phase 1, remove the hardcoded fallback URLs from `config.py`, `app/db.py`, and `database/db.py`
     so the app fails explicitly when `DATABASE_URL` is not set.
   - The credentials remain in git history. Consider `git filter-repo` or BFG Repo-Cleaner
     **after** credential rotation, but this is not a Phase 0 action.

**Consequences:** Until the credential is rotated, anyone with read access to the git history
can connect to the database.

---

## ADR-004: CORS Configuration

**Status:** ACCEPTED (documented finding — fix in Phase 1)

**Context:** The CORS middleware in `backend/main.py` is configured with:
```python
allow_origin_regex=".*",
allow_credentials=True,
allow_methods=["*"],
allow_headers=["*"],
```

The `allow_origin_regex=".*"` effectively allows **any origin**, making the explicit
`allow_origins` list meaningless. This is a security concern for production.

**Decision:**
- Phase 0: Document the finding (this ADR).
- Phase 1: Remove `allow_origin_regex=".*"`. Rely on the explicit `allow_origins` list from
  `CORS_ORIGINS` environment variable. Add the production frontend domain.

---

## ADR-005: Authentication — Current State and Target

**Status:** ACCEPTED (gap documented)

**Context:** The current login endpoint (`POST /api/v1/users/login`) returns a fake token:
```python
"token": f"jwt-supabase-{user['id']}-{user['role']}"
```
No middleware validates this token on subsequent requests. All endpoints are effectively
unauthenticated.

The frontend stores user data in `localStorage` under key `kraft_user` and gates the UI
client-side, but no server-side enforcement exists.

**Decision:**
- Phase 1 will implement proper JWT signing (using `python-jose` or `PyJWT`) with:
  - Token expiry (configurable, default 24h)
  - Role claim (`role` field in JWT payload)
  - Middleware/dependency injection that extracts and validates the token
- Phase 0 does NOT modify the login endpoint.

---

## ADR-006: ForecastProvider Protocol Boundary

**Status:** ACCEPTED

**Context:** The ML code and route code are currently tightly coupled. Member A (routes) directly
imports `forecast_demand`, `predict_demand`, `forecast_footfall`, and `detect_anomalies` from
specific module files.

**Decision:** Member D creates a `ForecastProvider` Protocol class (see FORECAST_CONTRACT.md).
Member A imports only from `app.ml.provider` or `app.ml.__init__`. This allows independent
development without import conflicts.

**Consequences:** Member D must refactor existing functions into a class implementing the protocol.

---

## ADR-007: Idempotency via `client_operation_id`

**Status:** ACCEPTED (Phase 1)

**Context:** The PHC app queues mutations offline and replays them on reconnect. Currently,
replaying the same sync item creates duplicate inventory entries (because the UPSERT is
on `phc_id + item_id + batch_number`, not on the sync ID).

**Decision:**
- Phase 1 adds a `client_operation_id` (UUID) header or body field on all mutation endpoints.
- The backend stores processed operation IDs in a `processed_operations` table (or column)
  and returns the cached response for duplicates.
- The `offline_sync_id` column already exists on most tables and can serve this purpose
  with a UNIQUE constraint and dedup check.

---

## ADR-008: Reserved Stock

**Status:** DEFERRED

**Context:** Transfer proposals may need to "hold" stock to prevent other operations from
consuming it before dispatch.

**Decision:** Defer to Phase 1 evaluation. If needed, add a `reserved_quantity` column to
`inventory` or a separate `stock_reservations` table.

---

## ADR-009: Synthetic Data Labeling

**Status:** ACCEPTED

**Context:** The ML module falls back to synthetic data when `< 30` consumption rows exist
for a medicine. This is useful for demos but can mislead users in production.

**Decision:**
- The `ForecastResult` schema includes `data_source: "database" | "synthetic"`.
- The API response includes a `method` field that reflects whether real or synthetic data was used.
- The frontend SHOULD display a warning banner when `data_source == "synthetic"`.
- Synthetic data generation functions are RETAINED (not deleted) as documented fallbacks.

---

## ADR-010: Event Time vs Server Time Convention

**Status:** ACCEPTED

**Context:** Multiple timestamp columns exist with ambiguous semantics.

**Decision:** See DOMAIN_MODEL.md §2.7. Key rules:
- `timestamp` = client-reported event time (when the measurement was taken)
- `created_at` = server INSERT time (immutable)
- `updated_at` = server UPDATE time (auto-trigger)
- All columns use `TIMESTAMPTZ` in UTC.

---

## ADR-011: PWA API URL Hardcoding

**Status:** ACCEPTED (fix in Phase 3)

**Context:** `phc-app/src/services/syncService.js` hardcodes `http://localhost:8000/api/v1`.
The web dashboard (`frontend/src/config.js`) correctly uses `import.meta.env.VITE_API_URL`
with a production fallback.

**Decision:** Phase 3 (Member C) will extract the PHC app API URL to `VITE_API_URL`
environment variable, matching the pattern in the web dashboard.

---

## ADR-012: Facility Auto-Polling

**Status:** DOCUMENTED

**Context:** The frontend `App.jsx` polls `GET /api/v1/facility/` every **4 seconds**
(line 46: `setInterval(() => fetchLiveData(false), 4000)`).

**Decision:** This is aggressive for production. Phase 2 should:
- Increase the interval to 30-60 seconds, OR
- Switch to WebSocket/SSE push notifications.
- For now, no change in Phase 0.
