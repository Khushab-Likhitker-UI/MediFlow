# Smart Health Sentinel — Domain Model

> **Baseline commit:** `cfe5968` (branch: `main`)
> **Date frozen:** 2026-10-13

---

## 1. Entity Relationship Diagram

```mermaid
erDiagram
    facilities ||--o{ inventory : "stocks"
    facilities ||--o{ beds : "has"
    facilities ||--o{ personnel : "employs"
    facilities ||--o{ phc_attendance_summary : "daily summary"
    facilities ||--o{ daily_footfall : "patient visits"
    facilities ||--o{ inventory_transactions : "stock movements"
    facilities ||--o{ medicine_consumption : "usage"
    facilities ||--o{ sync_log : "offline sync"

    medicines ||--o{ inventory : "batch rows"
    medicines ||--o{ inventory_transactions : "movements"
    medicines ||--o{ medicine_consumption : "consumption"

    personnel ||--o{ personnel_attendance : "individual attendance"
    personnel ||--o{ inventory_transactions : "performed_by"

    users {
        int id PK
        string username
        string email UK
        string role "admin|manager|viewer"
        string password_hash
        bool is_active
        timestamptz created_at
        timestamptz updated_at
    }

    facilities {
        string phc_id PK "PHC-XXX"
        string facility_name
        string facility_type "PHC|CHC"
        string district
        string state
        text address
        numeric latitude
        numeric longitude
        string phone_number
        string operational_status "active|inactive|under_maintenance"
    }

    medicines {
        int item_id PK
        string name UK
        string generic_name
        string category
        string unit "default: units"
        int reorder_level "default: 50"
        string supplier
        string dosage_form "tablet|capsule|syrup|..."
    }

    inventory {
        uuid inventory_id PK
        string phc_id FK
        int item_id FK
        string batch_number "default: DEFAULT_BATCH"
        int quantity ">=0"
        date expiry_date
        uuid offline_sync_id
    }

    inventory_transactions {
        uuid transaction_id PK
        string phc_id FK
        int item_id FK
        string batch_number
        string transaction_type "received|dispensed|expired|transferred_in|transferred_out|adjusted|returned"
        int quantity ">0"
        uuid reference_id
        text remarks
        uuid performed_by FK "nullable"
        uuid offline_sync_id
        timestamptz transaction_date
    }

    medicine_consumption {
        uuid consumption_id PK
        string phc_id FK
        int item_id FK
        date consumption_date
        int quantity_consumed ">=0"
        int patients_served
        uuid offline_sync_id
    }

    daily_footfall {
        int id PK
        string phc_id FK
        date date
        int patient_count ">=0"
    }

    beds {
        uuid bed_id PK
        string phc_id FK UK
        int available_beds ">=0"
        timestamptz timestamp
    }

    personnel {
        uuid personnel_id PK
        string phc_id FK
        string first_name
        string last_name
        string role "doctor|nurse|pharmacist|lab_technician"
        string contact_number UK
        string email
        date joining_date
        string status "active|inactive|on_leave|transferred"
    }

    personnel_attendance {
        uuid attendance_id PK
        uuid personnel_id FK
        string phc_id FK
        date attendance_date
        timestamptz check_in_time
        timestamptz check_out_time
        string attendance_status "present|absent|on_leave|half_day"
        uuid offline_sync_id
    }

    phc_attendance_summary {
        int id PK
        string phc_id FK
        date attendance_date
        int doctors_present
        timestamptz timestamp
        uuid offline_sync_id
    }

    sync_log {
        uuid sync_log_id PK
        uuid offline_sync_id
        string device_id
        string phc_id FK
        string table_name
        string sync_status "pending|synced|failed|conflict"
        timestamptz sync_timestamp
        int retry_count
        text error_message
    }
```

---

## 2. Frozen Domain Conventions

### 2.1 Canonical Medicine / Base Units

| Aspect | Convention |
|---|---|
| **Primary key** | `medicines.item_id` (SERIAL) |
| **Unique identifier** | `medicines.name` (UNIQUE constraint) |
| **Unit column** | `medicines.unit` — free-text but seeded values are: `tablets`, `capsules`, `sachets`, `vials`, `bags`, `units`, `boxes`, `rolls`, `tubes` |
| **Dosage form** | `medicines.dosage_form` — constrained enum: `tablet`, `capsule`, `syrup`, `injection`, `ointment`, `drops`, `inhaler`, `powder`, `suspension`, `cream`, `gel`, `solution`, `other` |
| **Reorder level** | Per-medicine global default; not per-facility. `medicines.reorder_level >= 0`. |
| **Quantity semantics** | `inventory.quantity` = physical count of `medicines.unit` at a specific facility + batch. Always `>= 0`. |

### 2.2 Source Data Provenance

| Source | Description |
|---|---|
| **Seeder** | `database/seed.py` populates 10 facilities, 25 medicines, ~180 days of consumption/footfall history. Idempotent via `ON CONFLICT DO NOTHING`. |
| **Live API** | Backend routes write to same tables via parameterized SQL. |
| **Offline sync** | PHC PWA queues mutations in IndexedDB, posts to backend on reconnect. `offline_sync_id` column tracks origin. |

### 2.3 Consumption vs Receipt/Adjustment

| Term | DB column/table | Semantics |
|---|---|---|
| **Consumption** | `medicine_consumption.quantity_consumed` | Daily outgoing: medicines dispensed to patients. Used by ML forecasting. |
| **Receipt** | `inventory_transactions` where `transaction_type = 'received'` | Stock arriving at facility. |
| **Adjustment** | `inventory_transactions` where `transaction_type = 'adjusted'` | Manual correction or stock-take update (the current `/inventory/update` endpoint logs this type). |
| **Dispensed** | `inventory_transactions` where `transaction_type = 'dispensed'` | Explicit patient-dispensing log (not currently populated by any route). |

### 2.4 Usable Inventory

```
usable_inventory(facility, medicine) =
    SUM(inventory.quantity)
    WHERE inventory.phc_id = facility
      AND inventory.item_id = medicine
      AND inventory.expiry_date > CURRENT_DATE
```

> **Note:** The current backend queries do NOT filter by `expiry_date` for stock status. This is an enhancement for Phase 1.

### 2.5 Reserved Stock

**Not currently implemented.** No `reserved_quantity` column or logic exists.

> **Decision:** Defer reserved stock to Phase 1 if transfer proposals need hold-aside quantities. See DECISIONS.md §Reserved-Stock.

### 2.6 Transfer Lifecycle

**Not currently implemented.** The schema has `transferred_in` / `transferred_out` transaction types but no transfer-request workflow exists.

Proposed lifecycle for Phase 1:

```
PROPOSED → APPROVED → DISPATCHED → RECEIVED
         ↘ REJECTED
```

Each state transition creates an `inventory_transactions` record. See API_CONTRACT.md §Transfers.

### 2.7 Event Time vs Server Recorded Time

| Column | Semantics |
|---|---|
| `timestamp` (on inventory, beds, attendance) | **Client-reported event time** — when the measurement was taken. |
| `created_at` | **Server recorded time** — `DEFAULT NOW()`, set by PostgreSQL at INSERT. Immutable. |
| `updated_at` | **Server recorded time** — auto-updated by trigger on every UPDATE. |
| `transaction_date` | **Server recorded time** — when the transaction was persisted. |

> **Convention:** All `TIMESTAMPTZ` columns use UTC. Frontend must convert for display.

### 2.8 Idempotent `client_operation_id`

**Not currently implemented.** The `offline_sync_id` column exists on several tables and is generated client-side, but no deduplication logic prevents re-processing a replayed sync item.

> **Decision:** Phase 1 will add `client_operation_id` middleware. See DECISIONS.md §Idempotency.

### 2.9 Synthetic-Demo Labeling

The ML module (`backend/app/ml/forecaster.py`, `anomaly_detector.py`) generates synthetic data when `medicine_consumption` / `inventory_transactions` tables have fewer than 30 rows for an item.

> **Convention:** Any API response that used synthetic fallback data MUST include a field or log indicating `"data_source": "synthetic"`. See FORECAST_CONTRACT.md for the typed schema.
