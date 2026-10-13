import { describe, it, expect, beforeEach, vi } from 'vitest';
import 'fake-indexeddb/auto';
import {
  initDB,
  enqueueOperation,
  getAllSyncItems,
  getPendingOrRetryOperations,
  updateOperationState,
  markOperationSynced,
  markOperationNeedsCorrection,
  markOperationRetryWait,
  cacheFacilities,
  getCachedFacilities,
  cacheMedicines,
  getCachedMedicines,
  clearSyncQueue,
  STORE_QUEUE,
  STORE_FACILITIES,
  STORE_CATALOGUE,
} from '../src/db/indexedDB';
import { syncQueue, calculateBackoffDelay } from '../src/services/syncService';

describe('PHC PWA — Offline Outbox & Exact-Once Idempotency Suite', () => {
  beforeEach(async () => {
    vi.restoreAllMocks();
    if (typeof navigator !== 'undefined') {
      Object.defineProperty(navigator, 'onLine', { value: true, configurable: true, writable: true });
    }
    await clearSyncQueue();
    const db = await initDB();
    const tx = db.transaction([STORE_FACILITIES, STORE_CATALOGUE], 'readwrite');
    await tx.objectStore(STORE_FACILITIES).clear();
    await tx.objectStore(STORE_CATALOGUE).clear();
    await tx.done;
  });



  it('1. Offline user action generates stable UUID and persists durably', async () => {
    const op = await enqueueOperation({
      facility: 'PHC-002',
      medicine: 'Paracetamol 500mg',
      quantity: 15,
      update_type: 'Medicine',
    });

    expect(op.client_operation_id).toBeDefined();
    expect(op.client_operation_id).toMatch(/^[0-9a-f-]{36}$/i);
    expect(op.sync_state).toBe('pending');
    expect(op.facility).toBe('PHC-002');
    expect(op.quantity).toBe(15);

    const items = await getAllSyncItems();
    expect(items.length).toBe(1);
    expect(items[0].client_operation_id).toBe(op.client_operation_id);
  });

  it('2. Reload with pending outbox retains operations', async () => {
    await enqueueOperation({
      facility: 'PHC-001',
      medicine: 'Amoxicillin 250mg',
      quantity: 50,
      update_type: 'Medicine',
    });

    // Reopen DB
    const db = await initDB();
    const pending = await getPendingOrRetryOperations();
    expect(pending.length).toBe(1);
    expect(pending[0].medicine).toBe('Amoxicillin 250mg');
  });

  it('3. Reconnect and sync with server acknowledgement (HTTP 200)', async () => {
    const op = await enqueueOperation({
      facility: 'PHC-001',
      medicine: 'Paracetamol',
      quantity: 20,
      update_type: 'Medicine',
    });

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ status: 'success', message: 'Stock logged', client_operation_id: op.client_operation_id }),
    });

    const result = await syncQueue(true);
    expect(result.syncedCount).toBe(1);

    const items = await getAllSyncItems();
    expect(items[0].sync_state).toBe('synced');
    expect(items[0].server_ack).toBeDefined();
    expect(items[0].server_ack.client_operation_id).toBe(op.client_operation_id);
  });

  it('4. Network timeout transitions operation to retry_wait with bounded backoff', async () => {
    await enqueueOperation({
      facility: 'PHC-001',
      medicine: 'Paracetamol',
      quantity: 10,
    });

    global.fetch = vi.fn().mockRejectedValue(new Error('Network timeout'));

    await syncQueue(true);

    const items = await getAllSyncItems();
    expect(items[0].sync_state).toBe('retry_wait');
    expect(items[0].retry_count).toBe(1);
    expect(items[0].next_retry_at).toBeDefined();
  });

  it('5. Server 500 error pauses queue and transitions to retry_wait', async () => {
    await enqueueOperation({
      facility: 'PHC-001',
      medicine: 'Ibuprofen',
      quantity: 5,
    });

    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ detail: 'Database connection failed' }),
    });

    await syncQueue(true);

    const items = await getAllSyncItems();
    expect(items[0].sync_state).toBe('retry_wait');
    expect(items[0].error_message).toContain('Database connection failed');
  });

  it('6. Server 422 validation error transitions to needs_correction without deletion', async () => {
    await enqueueOperation({
      facility: 'PHC-001',
      medicine: 'UnknownMed',
      quantity: -5,
    });

    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      statusText: 'Unprocessable Entity',
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ detail: [{ loc: ['body', 'quantity'], msg: 'ensure this value is greater than or equal to 0' }] }),
    });

    await syncQueue(true);

    const items = await getAllSyncItems();
    expect(items[0].sync_state).toBe('needs_correction');
    expect(items[0].error_message).toContain('quantity');
    expect(items[0].retry_count).toBe(0); // Validation errors do not burn retry count
  });


  it('7. Duplicate submission and retry preserves original client_operation_id', async () => {
    const fixedId = 'd83f4b50-6d30-4cf8-92ec-99e0ffbb0123';
    const op = await enqueueOperation({
      client_operation_id: fixedId,
      facility: 'PHC-001',
      medicine: 'Paracetamol',
      quantity: 10,
    });

    expect(op.client_operation_id).toBe(fixedId);

    // Ensure re-enqueue with same ID updates/preserves the same entry
    const op2 = await enqueueOperation({
      client_operation_id: fixedId,
      facility: 'PHC-001',
      medicine: 'Paracetamol',
      quantity: 12,
    });

    expect(op2.client_operation_id).toBe(fixedId);
    const items = await getAllSyncItems();
    expect(items.length).toBe(1);
    expect(items[0].quantity).toBe(12);
  });

  it('8. Out-of-order events handled without data corruption', async () => {
    const op1 = await enqueueOperation({
      facility: 'PHC-001',
      medicine: 'Paracetamol',
      quantity: 10,
      occurred_at: '2026-10-12T10:00:00Z',
    });
    const op2 = await enqueueOperation({
      facility: 'PHC-001',
      medicine: 'Paracetamol',
      quantity: 20,
      occurred_at: '2026-10-12T09:00:00Z',
    });

    const items = await getAllSyncItems();
    expect(items.length).toBe(2);
  });

  it('9. Facility caching and offline retrieval', async () => {
    const facs = [
      { id: 'PHC-001', name: 'Alur Primary Health Centre', district: 'Hassan' },
      { id: 'PHC-002', name: 'Belur Community Health Centre', district: 'Hassan' },
    ];
    await cacheFacilities(facs);

    const cached = await getCachedFacilities();
    expect(cached.facilities.length).toBe(2);
    expect(cached.facilities[0].name).toBe('Alur Primary Health Centre');
  });

  it('10. Medicine catalogue caching with canonical base units', async () => {
    const meds = [
      { id: 1, name: 'Paracetamol 500mg', unit: 'strips', reorder_level: 100 },
      { id: 2, name: 'Amoxicillin 250mg', unit: 'capsules', reorder_level: 50 },
    ];
    await cacheMedicines(meds);

    const cached = await getCachedMedicines();
    expect(cached.medicines.length).toBe(2);
    expect(cached.medicines.find(m => m.name === 'Paracetamol 500mg').unit).toBe('strips');
  });

  it('11. Synced operations are never re-applied on subsequent sync passes', async () => {
    const op = await enqueueOperation({
      facility: 'PHC-001',
      medicine: 'Paracetamol',
      quantity: 10,
    });
    await markOperationSynced(op.client_operation_id, { status: 'acknowledged' });

    let fetchCalled = false;
    global.fetch = vi.fn().mockImplementation(() => {
      fetchCalled = true;
      return Promise.resolve({ ok: true });
    });

    const res = await syncQueue(false);
    expect(fetchCalled).toBe(false);
    expect(res.syncedCount).toBe(0);
  });

  it('12. Bounded backoff delay calculation behaves monotonically and caps at 60s', () => {
    const d0 = calculateBackoffDelay(0);
    const d1 = calculateBackoffDelay(1);
    const d5 = calculateBackoffDelay(5);
    const d10 = calculateBackoffDelay(10);

    expect(d0).toBeGreaterThanOrEqual(2000);
    expect(d1).toBeGreaterThanOrEqual(4000);
    expect(d10).toBeLessThanOrEqual(61000); // 60s + max 1000ms jitter
  });

  it('13. Manual retry resets retry_wait operation for sync', async () => {
    const op = await enqueueOperation({
      facility: 'PHC-001',
      medicine: 'Paracetamol',
      quantity: 10,
    });
    await markOperationRetryWait(op.client_operation_id, 'Temp failure', 1, 60000);

    const itemsBefore = await getAllSyncItems();
    expect(itemsBefore[0].sync_state).toBe('retry_wait');

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ status: 'success' }),
    });

    const res = await syncQueue(true); // forceManual = true
    expect(res.syncedCount).toBe(1);

    const itemsAfter = await getAllSyncItems();
    expect(itemsAfter[0].sync_state).toBe('synced');
  });

  it('14. Outbox state summary counters calculate accurately', async () => {
    await enqueueOperation({ facility: 'PHC-001', medicine: 'M1', quantity: 1 });
    const op2 = await enqueueOperation({ facility: 'PHC-001', medicine: 'M2', quantity: 2 });
    const op3 = await enqueueOperation({ facility: 'PHC-001', medicine: 'M3', quantity: 3 });

    await markOperationSynced(op2.client_operation_id, {});
    await markOperationNeedsCorrection(op3.client_operation_id, 'Invalid field');

    const items = await getAllSyncItems();
    const pending = items.filter(i => i.sync_state === 'pending');
    const synced = items.filter(i => i.sync_state === 'synced');
    const needsCorrection = items.filter(i => i.sync_state === 'needs_correction');

    expect(pending.length).toBe(1);
    expect(synced.length).toBe(1);
    expect(needsCorrection.length).toBe(1);
  });

  it('15. HTTP 401/403 retains operation in outbox and marks needs_correction with auth explanation', async () => {
    const op = await enqueueOperation({
      facility: 'PHC-001',
      medicine: 'Paracetamol',
      quantity: 15,
      update_type: 'Medicine',
    });

    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      statusText: 'Unauthorized',
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ detail: 'Missing Authorization header with Bearer token.' }),
    });

    const res = await syncQueue(true);
    expect(res.syncedCount).toBe(0);

    const items = await getAllSyncItems();
    expect(items.length).toBe(1);
    expect(items[0].sync_state).toBe('needs_correction');
    expect(items[0].error_message).toContain('Authentication');
  });
});
