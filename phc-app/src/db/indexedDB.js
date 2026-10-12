import { openDB } from 'idb';

export const DB_NAME = 'PHCOfflineDB';
export const DB_VERSION = 2;

export const STORE_QUEUE = 'inventory_sync_queue';
export const STORE_FACILITIES = 'facilities_cache';
export const STORE_CATALOGUE = 'catalogue_cache';
export const STORE_META = 'meta_store';

// Legacy export for backward compatibility
export const STORE_NAME = STORE_QUEUE;

export const initDB = async () => {
  return openDB(DB_NAME, DB_VERSION, {
    upgrade(db, oldVersion, newVersion, transaction) {
      // Create or update outbox queue
      if (!db.objectStoreNames.contains(STORE_QUEUE)) {
        const queueStore = db.createObjectStore(STORE_QUEUE, { keyPath: 'client_operation_id' });
        queueStore.createIndex('sync_state', 'sync_state', { unique: false });
        queueStore.createIndex('occurred_at', 'occurred_at', { unique: false });
      } else if (oldVersion < 2) {
        // Migration from v1: if legacy store had auto-increment numeric 'id',
        // idb preserves it, but if index is missing, we ensure indices exist
        const queueStore = transaction.objectStore(STORE_QUEUE);
        if (!queueStore.indexNames.contains('sync_state')) {
          queueStore.createIndex('sync_state', 'sync_state', { unique: false });
        }
        if (!queueStore.indexNames.contains('occurred_at')) {
          queueStore.createIndex('occurred_at', 'occurred_at', { unique: false });
        }
      }

      // Facilities cache store
      if (!db.objectStoreNames.contains(STORE_FACILITIES)) {
        db.createObjectStore(STORE_FACILITIES, { keyPath: 'id' });
      }

      // Medicine catalogue cache store
      if (!db.objectStoreNames.contains(STORE_CATALOGUE)) {
        db.createObjectStore(STORE_CATALOGUE, { keyPath: 'name' });
      }

      // Metadata store (e.g. cache timestamps, last successful sync time)
      if (!db.objectStoreNames.contains(STORE_META)) {
        db.createObjectStore(STORE_META, { keyPath: 'key' });
      }
    },
  });
};

/**
 * Generate a cryptographically strong UUID (UUID v4)
 */
export const generateUUID = () => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
};

/**
 * Enqueue a new operation durably into IndexedDB before attempting any network delivery.
 * Stable operation identity is guaranteed: client_operation_id is created once here.
 */
export const enqueueOperation = async (payload) => {
  const db = await initDB();
  const clientOperationId = payload.client_operation_id || generateUUID();
  const occurredAt = payload.occurred_at || payload.timestamp || new Date().toISOString();

  const operation = {
    client_operation_id: clientOperationId,
    // Facility identifier (e.g. "PHC-001")
    facility: payload.facility || payload.phc_id,
    phc_id: payload.facility || payload.phc_id, // keep phc_id alias for contract mapping
    // Movement type: 'adjusted' | 'received' | 'dispensed'
    movement_type: payload.movement_type || (payload.update_type === 'Medicine' ? 'adjusted' : 'status_update'),
    update_type: payload.update_type || 'Medicine', // 'Medicine' | 'Beds' | 'Attendance'
    medicine: payload.medicine || payload.medicine_name || null,
    medicine_name: payload.medicine || payload.medicine_name || null, // contract alias
    batch_number: payload.batch_number || 'DEFAULT_BATCH',
    quantity: Number(payload.quantity ?? payload.available_beds ?? payload.doctors_present ?? 0),
    unit: payload.unit || 'units',
    occurred_at: occurredAt,
    timestamp: occurredAt, // contract alias
    // Specific fields for Beds / Attendance
    available_beds: payload.available_beds !== undefined ? Number(payload.available_beds) : undefined,
    doctors_present: payload.doctors_present !== undefined ? Number(payload.doctors_present) : undefined,

    // Outbox states: 'pending' | 'syncing' | 'synced' | 'retry_wait' | 'needs_correction'
    sync_state: 'pending',
    retry_count: 0,
    next_retry_at: null,
    last_attempt_at: null,
    error_message: null,
    http_status: null,
    server_ack: null,
    created_at: new Date().toISOString(),
  };

  await db.put(STORE_QUEUE, operation);
  return operation;
};

// Legacy addSyncItem wrapper for existing calls
export const addSyncItem = async (payload) => {
  return enqueueOperation(payload);
};

/**
 * Retrieve all items in the sync queue
 */
export const getAllSyncItems = async () => {
  const db = await initDB();
  return db.getAll(STORE_QUEUE);
};

/**
 * Get operations pending delivery or waiting for retry
 */
export const getPendingOrRetryOperations = async () => {
  const all = await getAllSyncItems();
  const now = Date.now();
  return all
    .filter((item) => {
      if (item.sync_state === 'pending') return true;
      if (item.sync_state === 'retry_wait') {
        return !item.next_retry_at || new Date(item.next_retry_at).getTime() <= now;
      }
      return false;
    })
    .sort((a, b) => {
      const diff = new Date(a.occurred_at || 0).getTime() - new Date(b.occurred_at || 0).getTime();
      if (diff !== 0) return diff;
      return new Date(a.created_at || 0).getTime() - new Date(b.created_at || 0).getTime();
    });
};

/**
 * Update an existing operation record
 */
export const updateSyncItem = async (item) => {
  const db = await initDB();
  return db.put(STORE_QUEUE, item);
};

export const updateOperationState = async (clientOperationId, updates) => {
  const db = await initDB();
  const tx = db.transaction(STORE_QUEUE, 'readwrite');
  const store = tx.objectStore(STORE_QUEUE);
  const existing = await store.get(clientOperationId);
  if (!existing) {
    await tx.done;
    return null;
  }
  const merged = { ...existing, ...updates };
  await store.put(merged);
  await tx.done;
  return merged;
};

/**
 * Mark operation as successfully acknowledged by the server.
 * Retains the operation record with synced state and server acknowledgement.
 */
export const markOperationSynced = async (clientOperationId, serverAck) => {
  return updateOperationState(clientOperationId, {
    sync_state: 'synced',
    server_ack: serverAck,
    synced_at: new Date().toISOString(),
    error_message: null,
    http_status: 200,
  });
};

/**
 * Mark operation in needs_correction / failed state due to validation (4xx) error.
 * Must NEVER be silently deleted.
 */
export const markOperationNeedsCorrection = async (clientOperationId, errorMessage, httpStatus) => {
  return updateOperationState(clientOperationId, {
    sync_state: 'needs_correction',
    error_message: errorMessage,
    http_status: httpStatus,
    last_attempt_at: new Date().toISOString(),
  });
};

/**
 * Schedule operation for retry with exponential backoff (e.g. 5xx or network timeout).
 */
export const markOperationRetryWait = async (clientOperationId, errorMessage, nextRetryAt, retryCount, httpStatus) => {
  return updateOperationState(clientOperationId, {
    sync_state: 'retry_wait',
    error_message: errorMessage,
    next_retry_at: nextRetryAt,
    retry_count: retryCount,
    http_status: httpStatus || 0,
    last_attempt_at: new Date().toISOString(),
  });
};

/**
 * Reset an operation to pending state to trigger an immediate manual retry.
 */
export const resetOperationForManualRetry = async (clientOperationId) => {
  return updateOperationState(clientOperationId, {
    sync_state: 'pending',
    next_retry_at: null,
    error_message: null,
  });
};

/**
 * Delete an operation from the local queue (explicit user action only).
 */
export const removeSyncItem = async (idOrClientOpId) => {
  const db = await initDB();
  return db.delete(STORE_QUEUE, idOrClientOpId);
};

export const clearSyncQueue = async () => {
  const db = await initDB();
  return db.clear(STORE_QUEUE);
};

// ── Cache & Meta Storage Helpers ──────────────────────────────────────────────

export const setMeta = async (key, value) => {
  const db = await initDB();
  return db.put(STORE_META, { key, value, updated_at: new Date().toISOString() });
};

export const getMeta = async (key) => {
  const db = await initDB();
  const record = await db.get(STORE_META, key);
  return record ? record.value : null;
};

export const cacheFacilities = async (facilities) => {
  if (!Array.isArray(facilities) || facilities.length === 0) return;
  const db = await initDB();
  const tx = db.transaction([STORE_FACILITIES, STORE_META], 'readwrite');
  const facStore = tx.objectStore(STORE_FACILITIES);
  for (const fac of facilities) {
    await facStore.put(fac);
  }
  const metaStore = tx.objectStore(STORE_META);
  await metaStore.put({
    key: 'facilities_cache_timestamp',
    value: new Date().toISOString(),
    count: facilities.length,
  });
  await tx.done;
};

export const getCachedFacilities = async () => {
  const db = await initDB();
  const items = await db.getAll(STORE_FACILITIES);
  const cacheTimestamp = await getMeta('facilities_cache_timestamp');
  return { facilities: items, cachedAt: cacheTimestamp };
};

export const cacheMedicines = async (medicines) => {
  if (!Array.isArray(medicines) || medicines.length === 0) return;
  const db = await initDB();
  const tx = db.transaction([STORE_CATALOGUE, STORE_META], 'readwrite');
  const catStore = tx.objectStore(STORE_CATALOGUE);
  for (const med of medicines) {
    await catStore.put(med);
  }
  const metaStore = tx.objectStore(STORE_META);
  await metaStore.put({
    key: 'medicines_cache_timestamp',
    value: new Date().toISOString(),
    count: medicines.length,
  });
  await tx.done;
};

export const getCachedMedicines = async () => {
  const db = await initDB();
  const items = await db.getAll(STORE_CATALOGUE);
  const cacheTimestamp = await getMeta('medicines_cache_timestamp');
  return { medicines: items, cachedAt: cacheTimestamp };
};
