## Pull Request Checklist — Smart Health Sentinel

### 1. Phase & Ownership Boundary
- [ ] **Phase:** (e.g., Phase 1 — Backend, Phase 2 — Web Dashboard, Phase 3 — PHC PWA, Phase 4 — ML Forecast, Phase 5 — Integration)
- [ ] **Assigned Owner:** (Member A / Member B / Member C / Member D / Staff Engineer)
- [ ] **Branch Name:** follows convention `phase-<N>/<feature-name>` (e.g., `phase-1/backend-routes`)
- [ ] **File Scope:** Changes are strictly within the assigned module/path ownership:
  - Phase 1 (Member A): `backend/app/routes/`, `backend/app/models/`
  - Phase 2 (Member B): `frontend/src/`
  - Phase 3 (Member C): `phc-app/src/`
  - Phase 4 (Member D): `backend/app/ml/`
- [ ] Any modifications to shared files (`backend/main.py`, `backend/app/db.py`, `database/`, root configs) are explicitly called out and coordinated.

---

### 2. Contract Conformity
- [ ] Routes and schemas strictly adhere to [docs/implementation/API_CONTRACT.md](file:///docs/implementation/API_CONTRACT.md).
- [ ] ML interfaces adhere to [docs/implementation/FORECAST_CONTRACT.md](file:///docs/implementation/FORECAST_CONTRACT.md).
- [ ] Entity conventions adhere to [docs/implementation/DOMAIN_MODEL.md](file:///docs/implementation/DOMAIN_MODEL.md) (e.g., canonical units, UTC timestamps, `client_operation_id`).
- [ ] Architectural decisions align with [docs/implementation/DECISIONS.md](file:///docs/implementation/DECISIONS.md).

---

### 3. Security & Secrets Hygiene
- [ ] **No credentials or connection strings** are committed in code, configs, or test files.
- [ ] Environment variables are read via configuration helpers (no hardcoded credentials).
- [ ] Any new environment variable is added to `.env.example` with a safe placeholder.
- [ ] Inputs are validated (Pydantic / parameterized SQL — no raw string concatenation).

---

### 4. Verification & Testing
- [ ] Linter passed (e.g., `npm run lint` for frontend/phc-app, flake8/black if configured).
- [ ] Build passed (e.g., `npm run build` for frontend/phc-app).
- [ ] Local tests executed and passing (e.g., `python verify_backend.py`, `python test_predictions.py`, or pytest).
- [ ] Manual verification done locally against running PostgreSQL / local backend.

---

### 5. Description of Changes
*(Provide a concise summary of what was added, modified, or fixed)*
