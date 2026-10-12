-- ============================================================
-- Smart Health Sentinel — Phase 1A Schema Migration
-- Migration: 001_sentinel_phase1a.sql
-- Description: Additive schema for stock transfers, reservations,
--              idempotency tracking, and audit logging.
-- ============================================================

BEGIN;

-- 1. Idempotent operations ledger for client_operation_id deduplication
CREATE TABLE IF NOT EXISTS processed_operations (
    operation_id        UUID PRIMARY KEY,
    endpoint            VARCHAR(150) NOT NULL,
    phc_id              VARCHAR(50),
    status_code         INTEGER NOT NULL,
    response_payload    TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_proc_ops_created ON processed_operations (created_at);

-- 2. Stock transfers table
CREATE TABLE IF NOT EXISTS transfers (
    transfer_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_phc_id         VARCHAR(50) NOT NULL REFERENCES facilities (phc_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    to_phc_id           VARCHAR(50) NOT NULL REFERENCES facilities (phc_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    item_id             INTEGER NOT NULL REFERENCES medicines (item_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    batch_number        VARCHAR(100) NOT NULL DEFAULT 'DEFAULT_BATCH',
    quantity            INTEGER NOT NULL CHECK (quantity > 0),
    received_quantity   INTEGER CHECK (received_quantity IS NULL OR received_quantity >= 0),
    status              VARCHAR(30) NOT NULL DEFAULT 'proposed'
                        CHECK (status IN (
                            'proposed', 'approved', 'dispatched',
                            'received', 'reconciled', 'rejected',
                            'cancelled', 'exception'
                        )),
    reason              TEXT,
    rejection_reason    TEXT,
    discrepancy_reason  TEXT,
    client_operation_id UUID UNIQUE,
    proposed_by         VARCHAR(255),
    approved_by         VARCHAR(255),
    dispatched_by       VARCHAR(255),
    received_by         VARCHAR(255),
    dispatched_at       TIMESTAMPTZ,
    received_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_different_facilities CHECK (from_phc_id <> to_phc_id)
);

CREATE INDEX IF NOT EXISTS idx_transfers_from_phc ON transfers (from_phc_id);
CREATE INDEX IF NOT EXISTS idx_transfers_to_phc   ON transfers (to_phc_id);
CREATE INDEX IF NOT EXISTS idx_transfers_status   ON transfers (status);
CREATE INDEX IF NOT EXISTS idx_transfers_item     ON transfers (item_id);

-- 3. Stock reservations table (atomic reservation holds)
CREATE TABLE IF NOT EXISTS stock_reservations (
    reservation_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transfer_id         UUID NOT NULL REFERENCES transfers (transfer_id) ON UPDATE CASCADE ON DELETE CASCADE,
    phc_id              VARCHAR(50) NOT NULL REFERENCES facilities (phc_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    item_id             INTEGER NOT NULL REFERENCES medicines (item_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    batch_number        VARCHAR(100) NOT NULL,
    reserved_quantity   INTEGER NOT NULL CHECK (reserved_quantity > 0),
    status              VARCHAR(20) NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'fulfilled', 'released')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reservations_lookup ON stock_reservations (phc_id, item_id, batch_number, status);

-- 4. Audit events table (immutable operational log)
CREATE TABLE IF NOT EXISTS audit_events (
    event_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type         VARCHAR(50) NOT NULL,
    entity_id           VARCHAR(100) NOT NULL,
    action              VARCHAR(50) NOT NULL,
    actor_id            VARCHAR(100),
    actor_role          VARCHAR(50),
    details             TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_events (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_events (created_at);

-- 5. Trigger for updated_at on transfers & reservations
CREATE OR REPLACE FUNCTION update_sentinel_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_transfers_updated_at ON transfers;
CREATE TRIGGER trg_transfers_updated_at
    BEFORE UPDATE ON transfers
    FOR EACH ROW EXECUTE FUNCTION update_sentinel_updated_at();

DROP TRIGGER IF EXISTS trg_reservations_updated_at ON stock_reservations;
CREATE TRIGGER trg_reservations_updated_at
    BEFORE UPDATE ON stock_reservations
    FOR EACH ROW EXECUTE FUNCTION update_sentinel_updated_at();

COMMIT;
