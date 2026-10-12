# Smart Health Sentinel — API Contract (Authoritative)

> **Baseline commit:** `cfe5968` (branch: `main`)
> **Date frozen:** 2026-10-13
> **Supersedes:** root `API_CONTRACT.md` (which documents the legacy 5-endpoint set)

This document is the **single authoritative API contract** for the Smart Health Sentinel project.
The root `API_CONTRACT.md` remains for reference to the existing endpoints. This document extends
it with the full Sentinel capability set.

---

## Conventions

| Convention | Value |
|---|---|
| Base URL (local dev) | `http://localhost:8000` |
| Base URL (production) | Set via `VITE_API_URL` env var / Railway |
| Content-Type | `application/json` |
| Timestamps | ISO 8601 with timezone (`YYYY-MM-DDTHH:mm:ss.ffffffZ`) |
| Date fields | `YYYY-MM-DD` |
| Error shape | `{"detail": "..."}`  or `{"detail": [{"loc":..., "msg":..., "type":...}]}` (FastAPI 422) |
| Auth header (future) | `Authorization: Bearer <token>` |
| Idempotency header (future) | `X-Client-Operation-Id: <uuid>` |

---

## Roles & Permissions

| Role | Can read all facilities | Can modify own facility | Can modify any facility | Can manage users | Can approve transfers |
|---|---|---|---|---|---|
| `admin` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `manager` | ✅ | ✅ | ❌ | ❌ | ✅ (own district) |
| `viewer` | ✅ | ❌ | ❌ | ❌ | ❌ |

> **Current state:** No permission enforcement exists. All endpoints are unauthenticated.
> Phase 1 will add role-based guards.

---

## 1. Authentication

### 1.1 `POST /api/v1/users/login`

**Existing endpoint.** Verifies email/username + bcrypt password against `users` table.

**Request:**
```json
{
  "email": "admin@smarthealth.local",
  "password": "admin123"
}
```

**Response (200):**
```json
{
  "id": 1,
  "username": "admin",
  "email": "admin@smarthealth.local",
  "role": "admin",
  "token": "jwt-supabase-1-admin"
}
```

> ⚠️ **Current `token` is a static placeholder string**, not a real JWT. Phase 1 must implement proper JWT signing.

**Errors:** `401` Invalid credentials, `500` DB error.

### 1.2 `POST /api/v1/users/` — Register user

**Existing endpoint.** Creates user with bcrypt-hashed password.

### 1.3 `GET /api/v1/users/` — List users

**Existing endpoint.** Returns all users (password_hash excluded).

### 1.4 `GET /api/v1/users/{user_id}` — Get user

### 1.5 `DELETE /api/v1/users/{user_id}` — Delete user

---

## 2. Facilities

### 2.1 `GET /api/v1/facility/` — List all facilities (with stock, beds, attendance)

**Existing endpoint.** Returns enriched facility objects with stock items, beds, attendance.

**Response (200):**
```json
[
  {
    "id": "PHC-001",
    "name": "Central District Hospital",
    "block": "North Block",
    "lat": 12.9716,
    "lng": 77.5946,
    "availableBeds": 25,
    "doctorsPresent": 3,
    "stockItems": [
      {
        "itemName": "Paracetamol 500mg",
        "currentUnits": 520,
        "avgDailyConsumption": 45,
        "unit": "tablets",
        "reorderLevel": 200
      }
    ],
    "lastUpdated": "2026-10-12T10:00:00+00:00"
  }
]
```

### 2.2 `POST /api/v1/facility/` — Create facility

**Existing endpoint.** Creates new PHC with auto-generated `phc_id`.

**Request:**
```json
{
  "name": "New Village PHC",
  "block": "West Block",
  "stockItems": [
    {"itemName": "Paracetamol 500mg", "currentUnits": 200, "avgDailyConsumption": 10}
  ]
}
```

### 2.3 `POST /api/v1/facility/beds` — Update beds

**Existing endpoint.** UPSERT available beds for a PHC.

### 2.4 `POST /api/v1/facility/attendance` — Update attendance

**Existing endpoint.** UPSERT daily doctor attendance summary.

---

## 3. Inventory (Catalogue)

### 3.1 `GET /api/v1/inventory/` — List all supply items

**Existing endpoint.** Aggregates quantity across all facilities.

Query params: `?category=PPE&low_stock=true`

### 3.2 `GET /api/v1/inventory/{item_id}` — Get single item

### 3.3 `POST /api/v1/inventory/` — Add new medicine to catalogue

### 3.4 `PUT /api/v1/inventory/{item_id}` — Update catalogue entry

### 3.5 `DELETE /api/v1/inventory/{item_id}` — Delete medicine

Returns `400` if inventory records reference the item.

---

## 4. PHC Stock Operations

### 4.1 `POST /api/v1/inventory/update` — Log stock update

**Existing endpoint.** UPSERT inventory + creates transaction record.

**Request:**
```json
{
  "phc_id": "PHC-001",
  "medicine_name": "Paracetamol 500mg",
  "quantity": 450,
  "timestamp": "2026-07-06T06:30:00Z"
}
```

**Response (200):**
```json
{"status": "success", "message": "Stock logged"}
```

**Idempotency:** Not currently enforced. Phase 1 will add `client_operation_id`.

### 4.2 `GET /api/v1/inventory/status/{phc_id}` — PHC stock levels

**Existing endpoint.** Returns all medicines' stock at a PHC.

---

## 5. Predictions & Forecasting

### 5.1 `POST /api/v1/predictions/demand` — Supply item demand forecast

**Existing endpoint.** Prophet forecast + Isolation Forest anomaly detection.

**Request:**
```json
{"item_id": 3, "horizon_days": 30}
```

**Response (200):** See `FORECAST_CONTRACT.md` for detailed typed schema.

### 5.2 `POST /api/predict` — Patient footfall prediction (7-day)

**Existing endpoint.** Accepts `FootfallPredictionRequest`.

### 5.3 `POST /api/predict-shortage` — Footfall shortage prediction (7-day)

**Existing endpoint.** Simpler payload (no `phc_id`).

### 5.4 `GET /api/v1/predictions/health` — ML pipeline health check

---

## 6. Transfers (Phase 1 — NEW)

> These endpoints do not exist yet. Member A will implement them.

### 6.1 `POST /api/v1/transfers/propose`

Propose a stock transfer between two facilities.

**Request:**
```json
{
  "from_phc_id": "PHC-001",
  "to_phc_id": "PHC-003",
  "item_id": 3,
  "quantity": 100,
  "reason": "Rebalancing surplus",
  "client_operation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response (201):**
```json
{
  "transfer_id": "uuid",
  "status": "proposed",
  "created_at": "2026-10-13T00:00:00Z"
}
```

**Permissions:** `admin` or `manager` of source facility's district.

### 6.2 `POST /api/v1/transfers/{transfer_id}/approve`

**Permissions:** `admin` or `manager` of destination facility's district.

### 6.3 `POST /api/v1/transfers/{transfer_id}/reject`

**Request:**
```json
{"reason": "Insufficient stock at destination"}
```

### 6.4 `POST /api/v1/transfers/{transfer_id}/dispatch`

Creates `transferred_out` transaction at source. Deducts from source inventory.

### 6.5 `POST /api/v1/transfers/{transfer_id}/receive`

Creates `transferred_in` transaction at destination. Adds to destination inventory.

### 6.6 `GET /api/v1/transfers/?status=proposed&phc_id=PHC-001`

List transfers filtered by status and/or facility.

---

## 7. Alerts (Phase 1 — NEW)

### 7.1 `GET /api/v1/alerts/?phc_id=PHC-001&severity=critical`

Returns computed alerts based on:
- Stock below reorder level → `low_stock`
- Stock at zero → `critical_stock`
- Expiring batches (< 30 days) → `expiring_soon`
- Anomaly flags from ML → `consumption_anomaly`

**Response (200):**
```json
[
  {
    "alert_id": "computed-uuid",
    "phc_id": "PHC-001",
    "type": "low_stock",
    "severity": "warning",
    "item_name": "ORS Packets",
    "message": "Stock at 85 sachets, below reorder level of 500",
    "generated_at": "2026-10-13T00:00:00Z"
  }
]
```

---

## 8. Health Check

### 8.1 `GET /` — Root health check

**Existing endpoint.**

```json
{
  "service": "Healthcare Supply Chain API",
  "version": "0.1.0",
  "status": "running",
  "docs": "/docs"
}
```

---

## Quick Reference — All Routes

```
# Existing (confirmed in code)
GET   /                                      → Health check
POST  /api/v1/users/login                    → Login
POST  /api/v1/users/                         → Register user
GET   /api/v1/users/                         → List users
GET   /api/v1/users/{user_id}                → Get user
DELETE /api/v1/users/{user_id}               → Delete user
GET   /api/v1/facility/                      → List facilities
POST  /api/v1/facility/                      → Create facility
POST  /api/v1/facility/beds                  → Update beds
POST  /api/v1/facility/attendance            → Update attendance
GET   /api/v1/inventory/                     → List items
GET   /api/v1/inventory/{item_id}            → Get item
POST  /api/v1/inventory/                     → Add item
PUT   /api/v1/inventory/{item_id}            → Update item
DELETE /api/v1/inventory/{item_id}           → Delete item
POST  /api/v1/inventory/update               → Log stock update
GET   /api/v1/inventory/status/{phc_id}      → PHC stock levels
POST  /api/v1/predictions/demand             → Item demand forecast
GET   /api/v1/predictions/health             → ML health
POST  /api/predict                           → Footfall prediction
POST  /api/predict-shortage                  → Shortage prediction

# Phase 1 (new)
POST  /api/v1/transfers/propose              → Propose transfer
POST  /api/v1/transfers/{id}/approve         → Approve transfer
POST  /api/v1/transfers/{id}/reject          → Reject transfer
POST  /api/v1/transfers/{id}/dispatch        → Dispatch transfer
POST  /api/v1/transfers/{id}/receive         → Receive transfer
GET   /api/v1/transfers/                     → List transfers
GET   /api/v1/alerts/                        → Computed alerts
```
