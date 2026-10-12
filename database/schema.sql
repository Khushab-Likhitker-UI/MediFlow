-- ============================================================
-- Healthcare Resource Optimization Platform
-- PostgreSQL Database Schema (Refactored & Purged)
-- ============================================================

BEGIN;

-- pgcrypto provides gen_random_uuid() — recommended on Supabase
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ----------------------------------------------------------
-- 0. USERS (Used by backend user routes)
-- ----------------------------------------------------------
CREATE TABLE users (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(255) NOT NULL,
    email         VARCHAR(255) NOT NULL UNIQUE,
    role          VARCHAR(50)  NOT NULL DEFAULT 'viewer' 
                  CHECK (role IN ('admin', 'manager', 'viewer')),
    password_hash VARCHAR(255) NOT NULL,
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------
-- 1. HEALTHCARE FACILITIES (Used globally)
-- ----------------------------------------------------------
CREATE TABLE facilities (
    phc_id          VARCHAR(50) PRIMARY KEY, -- "PHC-XXX"
    facility_name   VARCHAR(255) NOT NULL,
    facility_type   VARCHAR(10)  NOT NULL CHECK (facility_type IN ('PHC', 'CHC')),
    district        VARCHAR(150) NOT NULL,
    state           VARCHAR(150) NOT NULL,
    address         TEXT         NOT NULL,
    latitude        NUMERIC(9, 6) NOT NULL,
    longitude       NUMERIC(9, 6) NOT NULL,
    phone_number    VARCHAR(20),
    operational_status VARCHAR(20) NOT NULL DEFAULT 'active'
                       CHECK (operational_status IN ('active', 'inactive', 'under_maintenance')),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_facility_name_district UNIQUE (facility_name, district)
);

-- ----------------------------------------------------------
-- 2. MEDICINES / SUPPLY ITEMS (Used by inventory and predictions)
-- ----------------------------------------------------------
CREATE TABLE medicines (
    item_id         SERIAL PRIMARY KEY,
    name            VARCHAR(255) NOT NULL, 
    generic_name    VARCHAR(255),
    category        VARCHAR(100) NOT NULL,
    unit            VARCHAR(50)  NOT NULL DEFAULT 'units',
    reorder_level   INTEGER      NOT NULL DEFAULT 50 CHECK (reorder_level >= 0),
    supplier        VARCHAR(255),
    dosage_form     VARCHAR(50)  
                    CHECK (dosage_form IS NULL OR dosage_form IN (
                        'tablet', 'capsule', 'syrup', 'injection',
                        'ointment', 'drops', 'inhaler', 'powder',
                        'suspension', 'cream', 'gel', 'solution', 'other'
                    )),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_medicine_name UNIQUE (name)
);

-- ----------------------------------------------------------
-- 3. INVENTORY (Single source of truth for stock)
-- ----------------------------------------------------------
CREATE TABLE inventory (
    inventory_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phc_id          VARCHAR(50)  NOT NULL REFERENCES facilities (phc_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    item_id         INTEGER      NOT NULL REFERENCES medicines (item_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    batch_number    VARCHAR(100) NOT NULL DEFAULT 'DEFAULT_BATCH',
    quantity        INTEGER      NOT NULL CHECK (quantity >= 0),
    expiry_date     DATE         NOT NULL DEFAULT CURRENT_DATE + INTERVAL '1 year',
    offline_sync_id UUID,
    timestamp       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_inventory_batch UNIQUE (phc_id, item_id, batch_number)
);

-- ----------------------------------------------------------
-- 4. BEDS (Used by backend `/facility/beds`)
-- ----------------------------------------------------------
CREATE TABLE beds (
    bed_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phc_id          VARCHAR(50) NOT NULL UNIQUE REFERENCES facilities (phc_id) ON UPDATE CASCADE ON DELETE CASCADE,
    available_beds  INTEGER NOT NULL DEFAULT 0 CHECK (available_beds >= 0),
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    offline_sync_id UUID,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------
-- 5. PERSONNEL & DETAILED ATTENDANCE
-- ----------------------------------------------------------
CREATE TABLE personnel (
    personnel_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phc_id          VARCHAR(50)   NOT NULL REFERENCES facilities (phc_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    first_name      VARCHAR(100)  NOT NULL,
    last_name       VARCHAR(100)  NOT NULL,
    role            VARCHAR(30)   NOT NULL
                    CHECK (role IN ('doctor', 'nurse', 'pharmacist', 'lab_technician')),
    contact_number  VARCHAR(20)   NOT NULL,
    email           VARCHAR(255),
    joining_date    DATE          NOT NULL,
    status          VARCHAR(20)   NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'inactive', 'on_leave', 'transferred')),
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_personnel_contact UNIQUE (contact_number)
);

CREATE TABLE personnel_attendance (
    attendance_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    personnel_id    UUID         NOT NULL REFERENCES personnel (personnel_id) ON UPDATE CASCADE ON DELETE CASCADE,
    phc_id          VARCHAR(50)  NOT NULL REFERENCES facilities (phc_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    attendance_date DATE         NOT NULL,
    check_in_time   TIMESTAMPTZ,
    check_out_time  TIMESTAMPTZ,
    attendance_status VARCHAR(20) NOT NULL DEFAULT 'present'
                      CHECK (attendance_status IN ('present', 'absent', 'on_leave', 'half_day')),
    offline_sync_id UUID,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_personnel_date UNIQUE (personnel_id, attendance_date)
);

-- ----------------------------------------------------------
-- 6. PHC ATTENDANCE SUMMARY (Required by backend `/facility/attendance`)
-- ----------------------------------------------------------
CREATE TABLE phc_attendance_summary (
    id              SERIAL PRIMARY KEY,
    phc_id          VARCHAR(50)  NOT NULL REFERENCES facilities (phc_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    attendance_date DATE         NOT NULL DEFAULT CURRENT_DATE,
    doctors_present INTEGER      NOT NULL CHECK (doctors_present >= 0),
    timestamp       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    offline_sync_id UUID,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_attendance_daily UNIQUE (phc_id, attendance_date)
);

-- ----------------------------------------------------------
-- 7. DAILY FOOTFALL (Used by backend predictive models)
-- ----------------------------------------------------------
CREATE TABLE daily_footfall (
    id            SERIAL PRIMARY KEY,
    phc_id        VARCHAR(50) NOT NULL REFERENCES facilities (phc_id) ON UPDATE CASCADE ON DELETE CASCADE,
    date          DATE        NOT NULL,
    patient_count INTEGER     NOT NULL CHECK (patient_count >= 0),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT uq_footfall_daily UNIQUE (phc_id, date)
);

-- ----------------------------------------------------------
-- 8. SYNCHRONIZATION LOG (Used by offline PHC App flow)
-- ----------------------------------------------------------
CREATE TABLE sync_log (
    sync_log_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    offline_sync_id UUID         NOT NULL,
    device_id       VARCHAR(255) NOT NULL,
    phc_id          VARCHAR(50)  NOT NULL REFERENCES facilities (phc_id) ON UPDATE CASCADE ON DELETE CASCADE,
    table_name      VARCHAR(100) NOT NULL,
    sync_status     VARCHAR(20)  NOT NULL DEFAULT 'pending'
                    CHECK (sync_status IN ('pending', 'synced', 'failed', 'conflict')),
    sync_timestamp  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    retry_count     INTEGER      NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
    error_message   TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_sync_entry UNIQUE (offline_sync_id, table_name)
);

-- ----------------------------------------------------------
-- 9. INVENTORY TRANSACTIONS (Written on stock updates)
-- ----------------------------------------------------------
CREATE TABLE inventory_transactions (
    transaction_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phc_id           VARCHAR(50)   NOT NULL REFERENCES facilities (phc_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    item_id          INTEGER       NOT NULL REFERENCES medicines (item_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    batch_number     VARCHAR(100),
    transaction_type VARCHAR(20)   NOT NULL
                     CHECK (transaction_type IN (
                         'received', 'dispensed', 'expired',
                         'transferred_in', 'transferred_out', 'adjusted', 'returned'
                     )),
    quantity         INTEGER       NOT NULL CHECK (quantity > 0),
    reference_id     UUID,
    remarks          TEXT,
    performed_by     UUID REFERENCES personnel (personnel_id) ON UPDATE CASCADE ON DELETE SET NULL,
    offline_sync_id  UUID,
    transaction_date TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------
-- 10. MEDICINE CONSUMPTION (Used by ML Demand Forecast)
-- ----------------------------------------------------------
CREATE TABLE medicine_consumption (
    consumption_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phc_id           VARCHAR(50)   NOT NULL REFERENCES facilities (phc_id) ON UPDATE CASCADE ON DELETE CASCADE,
    item_id          INTEGER       NOT NULL REFERENCES medicines (item_id) ON UPDATE CASCADE ON DELETE CASCADE,
    consumption_date DATE          NOT NULL,
    quantity_consumed INTEGER      NOT NULL CHECK (quantity_consumed >= 0),
    patients_served  INTEGER       CHECK (patients_served >= 0),
    offline_sync_id  UUID,
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_consumption_daily UNIQUE (phc_id, item_id, consumption_date)
);

-- ============================================================
-- INDEXES
-- ============================================================
CREATE INDEX idx_facilities_district    ON facilities (district);
CREATE INDEX idx_medicines_category     ON medicines (category);
CREATE INDEX idx_medicines_name         ON medicines (name);
CREATE INDEX idx_inventory_facility     ON inventory (phc_id);
CREATE INDEX idx_inventory_medicine     ON inventory (item_id);
CREATE INDEX idx_inventory_sync         ON inventory (offline_sync_id) WHERE offline_sync_id IS NOT NULL;
CREATE INDEX idx_phc_attendance_date    ON phc_attendance_summary (attendance_date);
CREATE INDEX idx_footfall_date          ON daily_footfall (date);
CREATE INDEX idx_inv_txn_facility       ON inventory_transactions (phc_id);
CREATE INDEX idx_inv_txn_medicine       ON inventory_transactions (item_id);
CREATE INDEX idx_consumption_forecast   ON medicine_consumption (phc_id, item_id, consumption_date);

-- ============================================================
-- TRIGGERS (Auto-update updated_at)
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_facilities_updated_at BEFORE UPDATE ON facilities FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_medicines_updated_at BEFORE UPDATE ON medicines FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_inventory_updated_at BEFORE UPDATE ON inventory FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_personnel_updated_at BEFORE UPDATE ON personnel FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_personnel_att_updated_at BEFORE UPDATE ON personnel_attendance FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_phc_att_updated_at BEFORE UPDATE ON phc_attendance_summary FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_beds_updated_at BEFORE UPDATE ON beds FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_footfall_updated_at BEFORE UPDATE ON daily_footfall FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_sync_log_updated_at BEFORE UPDATE ON sync_log FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_inv_txn_updated_at BEFORE UPDATE ON inventory_transactions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_consumption_updated_at BEFORE UPDATE ON medicine_consumption FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

COMMIT;
