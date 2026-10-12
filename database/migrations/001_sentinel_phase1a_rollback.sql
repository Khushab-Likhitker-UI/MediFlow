-- ============================================================
-- Smart Health Sentinel — Phase 1A Schema Rollback
-- Rollback: 001_sentinel_phase1a_rollback.sql
-- ============================================================

BEGIN;

DROP TRIGGER IF EXISTS trg_reservations_updated_at ON stock_reservations;
DROP TRIGGER IF EXISTS trg_transfers_updated_at ON transfers;
DROP FUNCTION IF EXISTS update_sentinel_updated_at();

DROP TABLE IF EXISTS audit_events;
DROP TABLE IF EXISTS stock_reservations;
DROP TABLE IF EXISTS transfers;
DROP TABLE IF EXISTS processed_operations;

COMMIT;
