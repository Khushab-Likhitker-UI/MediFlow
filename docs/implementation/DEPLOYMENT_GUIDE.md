# Google Cloud Run Deployment & Operations Guide

**Project:** Smart Health Sentinel (`MediFlow`)  
**Phase:** 3 — Secure Deployment, Cloud Run, and Grounded Gemini Explanation  
**Author:** Integration Lead / DevOps Owner  

---

## 1. Overview & Architecture

Smart Health Sentinel's FastAPI backend is packaged as an unprivileged, OCI-compliant container and deployed to **Google Cloud Run**. Cloud Run delivers automated HTTPS termination, horizontal autoscaling, request-driven resource provisioning, and zero-downtime rolling deployments.

```
                           ┌────────────────────────────────────────┐
                           │       External Clients                 │
                           │  - React Dashboard (Vercel)            │
                           │  - Offline PHC PWA (Vite)              │
                           └──────────────────┬─────────────────────┘
                                              │ HTTPS (CORS enforced)
                                              ▼
                           ┌────────────────────────────────────────┐
                           │        Google Cloud Run                │
                           │   Service: sentinel-backend (Port 8080)│
                           │   Runtime: Python 3.11-slim (non-root) │
                           │   Probes: /api/v1/health               │
                           └───────┬────────────────────┬───────────┘
                                   │                    │
                  Secret Bindings  │                    │ TLS egress (Port 6543)
                                   ▼                    ▼
        ┌───────────────────────────────┐   ┌────────────────────────────────┐
        │     Google Secret Manager     │   │ Authoritative PostgreSQL DB    │
        │ - sentinel-database-url       │   │ - Supabase Transaction Pooler  │
        │ - sentinel-jwt-secret-key     │   │ - sslmode=require              │
        │ - sentinel-gemini-api-key     │   │ - Threaded pool (1-20 conns)   │
        └───────────────────────────────┘   └────────────────────────────────┘
```

---

## 2. Prerequisites

1. **Google Cloud SDK (`gcloud`)**: Installed and initialized (`gcloud init`).
2. **Billing Enabled Project**: A GCP Project with billing active.
3. **Required APIs Enabled**:
   ```bash
   gcloud services enable \
       run.googleapis.com \
       cloudbuild.googleapis.com \
       secretmanager.googleapis.com \
       artifactregistry.googleapis.com
   ```

---

## 3. Secret Management (Google Secret Manager)

To adhere strictly to zero-secret repository practices, secrets are stored in Google Secret Manager and injected at container runtime as environment variables.

### 3.1. Create Secrets
```bash
# 1. Database Connection URL (Supabase Pooler URI)
echo -n "postgresql://<USER>:<PASSWORD>@<HOST>:6543/<DB>?sslmode=require" | \
  gcloud secrets create sentinel-database-url --data-file=-

# 2. JWT Cryptographic Signing Key (min 32 characters)
openssl rand -hex 32 | \
  gcloud secrets create sentinel-jwt-secret-key --data-file=-

# 3. Optional Google Gemini API Key
echo -n "<YOUR_GEMINI_API_KEY>" | \
  gcloud secrets create sentinel-gemini-api-key --data-file=-
```

### 3.2. Grant Least-Privilege IAM Access
The Cloud Run runtime service account must have permission to read these secrets:
```bash
PROJECT_NUMBER=$(gcloud projects describe $(gcloud config get-value project) --format='value(projectNumber)')
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

for SECRET in sentinel-database-url sentinel-jwt-secret-key sentinel-gemini-api-key; do
  gcloud secrets add-iam-policy-binding ${SECRET} \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor"
done
```

---

## 4. Deployment Instructions

### 4.1. Automated Deployment via Script
Linux/macOS:
```bash
chmod +x deploy-cloudrun.sh
./deploy-cloudrun.sh
```

Windows PowerShell:
```powershell
.\deploy-cloudrun.ps1
```

### 4.2. Declarative Deployment via Knative Spec
Update `PROJECT_ID` in `cloudrun-service.yaml`, then apply:
```bash
gcloud run services replace cloudrun-service.yaml --region=us-central1
```

### 4.3. Manual Step-by-Step CLI Deployment
```bash
# 1. Build and push image via Cloud Build
gcloud builds submit --tag gcr.io/$(gcloud config get-value project)/sentinel-backend:latest .

# 2. Deploy to Cloud Run
gcloud run deploy sentinel-backend \
  --image gcr.io/$(gcloud config get-value project)/sentinel-backend:latest \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --set-env-vars="DEBUG=false,APP_NAME=Healthcare Supply Chain API,APP_VERSION=0.1.0,PLANNING_HORIZON_DAYS=30,SAFETY_RESERVE_DAYS=7,CORS_ORIGINS=https://smart-health-gray-theta.vercel.app,https://smarthealth-production.up.railway.app" \
  --set-secrets="DATABASE_URL=sentinel-database-url:latest,JWT_SECRET_KEY=sentinel-jwt-secret-key:latest,GEMINI_API_KEY=sentinel-gemini-api-key:latest"
```

---

## 5. Authoritative Database Strategy: Supabase vs. Cloud SQL

### 5.1. Current Configuration (Authoritative Supabase PostgreSQL)
- **Networking**: Cloud Run connects to Supabase pooler via outbound TLS egress on port 6543.
- **Pooling**: `psycopg2.pool.ThreadedConnectionPool(1, 20)` manages active connections per container instance.
- **TLS Enforcement**: `sslmode=require` is appended automatically by `app/db.py` to prevent plaintext network transit.

### 5.2. Optional Cloud SQL Migration Plan (Non-Disruptive)
A migration from Supabase to Google Cloud SQL should only occur after completing this 4-step staging export/import procedure:
1. **Staging Export**:
   ```bash
   pg_dump -h <SUPABASE_HOST> -p 5432 -U <USER> -d postgres \
     --no-owner --no-acl --format=c -f sentinel_staging_backup.dump
   ```
2. **Cloud SQL Import**:
   ```bash
   # Provision Cloud SQL Postgres instance
   gcloud sql instances create sentinel-postgres --database-version=POSTGRES_15 --tier=db-f1-micro --region=us-central1
   gcloud sql databases create sentinel sentinel-postgres
   # Restore schema and data
   pg_restore -h <CLOUD_SQL_IP> -U <USER> -d sentinel -v sentinel_staging_backup.dump
   ```
3. **Smoke Verification**:
   Point a staging Cloud Run instance to Cloud SQL via Cloud SQL Auth Proxy (`/cloudsql/PROJECT:REGION:INSTANCE`). Verify table row counts and run `pytest backend/tests`.
4. **Rollback Runbook**:
   If schema discrepancies or connection pooling errors arise in Cloud SQL, revert the Cloud Run secret `sentinel-database-url` back to the Supabase URI:
   ```bash
   echo -n "<PREVIOUS_SUPABASE_URI>" | gcloud secrets versions add sentinel-database-url --data-file=-
   ```

---

## 6. Post-Deployment Verification & Smoke Tests

Execute these verification checks against the returned Cloud Run service URL (`SERVICE_URL`):

```bash
# 1. Health Probe Verification
curl -i "${SERVICE_URL}/api/v1/health"
# Expected: HTTP 200 OK, {"status": "healthy", "service": "...", "version": "..."}

# 2. Authentication Rejection (Unauthorized access prohibited)
curl -i -X POST "${SERVICE_URL}/api/v1/explain/decision" \
  -H "Content-Type: application/json" \
  -d '{"facility_name":"PHC A","district":"Central","item_name":"Gloves","current_usable_stock":0,"safety_reserve":10,"projected_deficit":10,"recommended_action":"Transfer"}'
# Expected: HTTP 401 Unauthorized

# 3. CORS Preflight Header Validation
curl -i -X OPTIONS "${SERVICE_URL}/api/v1/health" \
  -H "Origin: https://smart-health-gray-theta.vercel.app" \
  -H "Access-Control-Request-Method: GET"
# Expected: HTTP 200 OK, Access-Control-Allow-Origin: https://smart-health-gray-theta.vercel.app

# 4. Request ID Trace Propagation
curl -i "${SERVICE_URL}/api/v1/health" -H "X-Request-ID: trace-audit-12345"
# Expected: X-Request-ID header returned in HTTP response
```
