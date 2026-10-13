import {
  getAllSyncItems,
  getPendingOrRetryOperations,
  updateOperationState,
  markOperationSynced,
  markOperationNeedsCorrection,
  markOperationRetryWait,
  cacheFacilities,
  cacheMedicines,
  setMeta,
  getMeta,
} from '../db/indexedDB';
import { ENDPOINTS } from '../config';

// Exponential backoff configuration
const BASE_RETRY_DELAY_MS = 2000; // 2 seconds
const MAX_RETRY_DELAY_MS = 60000;  // 60 seconds max backoff cap
const REQUEST_TIMEOUT_MS = 10000;  // 10 second timeout

let isSyncInProgress = false;

/**
 * Calculate bounded exponential backoff with jitter
 */
export const calculateBackoffDelay = (retryCount) => {
  const exponential = BASE_RETRY_DELAY_MS * Math.pow(2, Math.max(0, retryCount));
  const bounded = Math.min(MAX_RETRY_DELAY_MS, exponential);
  const jitter = Math.floor(Math.random() * 1000);
  return bounded + jitter;
};

/**
 * Perform a fetch with timeout
 */
const fetchWithTimeout = async (url, options = {}, timeoutMs = REQUEST_TIMEOUT_MS) => {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    return response;
  } finally {
    clearTimeout(timeoutId);
  }
};

/**
 * Format human-readable error messages from server response
 */
const extractErrorMessage = async (response) => {
  try {
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      const data = await response.json();
      if (typeof data.detail === 'string') {
        return data.detail;
      }
      if (Array.isArray(data.detail)) {
        return data.detail.map((err) => `${err.loc?.slice(-1)[0] || 'Field'}: ${err.msg}`).join('; ');
      }
      if (data.message) {
        return data.message;
      }
      return JSON.stringify(data);
    }
    const text = await response.text();
    return text || `HTTP ${response.status} ${response.statusText}`;
  } catch {
    return `HTTP ${response.status} ${response.statusText}`;
  }
};

/**
 * Sync the local outbox queue with the backend
 */
export const syncQueue = async (forceManual = false) => {
  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    return { syncedCount: 0, pendingCount: 0, offline: true };
  }

  if (isSyncInProgress) {
    return { syncing: true };
  }

  isSyncInProgress = true;
  let syncedCount = 0;

  try {
    const itemsToProcess = forceManual
      ? (await getAllSyncItems()).filter((i) => i.sync_state !== 'synced')
      : await getPendingOrRetryOperations();

    if (itemsToProcess.length === 0) {
      return { syncedCount: 0, pendingCount: 0 };
    }

    for (const item of itemsToProcess) {
      const opId = item.client_operation_id;

      // Mark operation as syncing
      await updateOperationState(opId, {
        sync_state: 'syncing',
        last_attempt_at: new Date().toISOString(),
      });

      let endpoint = ENDPOINTS.stockMovements || ENDPOINTS.inventoryUpdate;
      let payload = {};

      if (item.update_type === 'Medicine') {
        endpoint = ENDPOINTS.stockMovements || ENDPOINTS.inventoryUpdate;
        payload = {
          client_operation_id: opId,
          phc_id: item.facility || item.phc_id,
          medicine_name: item.medicine || item.medicine_name,
          quantity: Number(item.quantity),
          batch_number: item.batch_number || 'DEFAULT_BATCH',
          movement_type: item.movement_type || 'dispensed',
          occurred_at: item.occurred_at || item.timestamp || new Date().toISOString(),
          expiry_date: item.expiry_date || null,
          remarks: item.remarks || null,
        };
        if (item.item_id) {
          payload.item_id = Number(item.item_id);
        }
      } else if (item.update_type === 'Beds') {
        endpoint = ENDPOINTS.facilityBeds;
        payload = {
          client_operation_id: opId,
          phc_id: item.facility || item.phc_id,
          available_beds: Number(item.available_beds ?? item.quantity),
          timestamp: item.occurred_at || item.timestamp,
        };
      } else if (item.update_type === 'Attendance') {
        endpoint = ENDPOINTS.facilityAttendance;
        payload = {
          client_operation_id: opId,
          phc_id: item.facility || item.phc_id,
          doctors_present: Number(item.doctors_present ?? item.quantity),
          timestamp: item.occurred_at || item.timestamp,
        };
      } else {
        endpoint = ENDPOINTS.stockMovements || ENDPOINTS.inventoryUpdate;
        payload = {
          client_operation_id: opId,
          phc_id: item.facility || item.phc_id,
          medicine_name: item.medicine || item.medicine_name,
          quantity: Number(item.quantity),
          batch_number: item.batch_number || 'DEFAULT_BATCH',
          movement_type: item.movement_type || 'dispensed',
          occurred_at: item.occurred_at || item.timestamp || new Date().toISOString(),
        };
      }

      // Attach auth token if available in localStorage
      const headers = {
        'Content-Type': 'application/json',
        'X-Client-Operation-Id': opId,
      };
      try {
        let token = null;
        if (typeof localStorage !== 'undefined') {
          token = localStorage.getItem('access_token') || localStorage.getItem('token');
          if (!token) {
            const savedUser = localStorage.getItem('kraft_user') || localStorage.getItem('user');
            if (savedUser) {
              const u = JSON.parse(savedUser);
              token = u.token || u.access_token;
            }
          }
        }
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }
      } catch {
        // Ignore localStorage retrieval issues in sandbox environments
      }

      try {
        const response = await fetchWithTimeout(endpoint, {
          method: 'POST',
          headers,
          body: JSON.stringify(payload),
        });

        if (response.ok) {
          let ackData = null;
          try {
            ackData = await response.json();
          } catch {
            ackData = { status: 'success' };
          }

          // Durable acknowledgement: mark synced and record server acknowledgment
          await markOperationSynced(opId, ackData);
          syncedCount++;

          // Update last successful sync timestamp
          await setMeta('last_successful_sync_time', new Date().toISOString());
        } else if (response.status === 401 || response.status === 403) {
          // Authentication or permission required: preserve in outbox, pause processing
          const errorMsg = await extractErrorMessage(response);
          await markOperationNeedsCorrection(
            opId,
            `Authentication / permission required (${response.status}): ${errorMsg}`,
            response.status
          );
          // Pause queue processing so unauthenticated requests are not lost
          break;
        } else if (response.status >= 400 && response.status < 500) {
          // Client or Validation Error (400, 404, 409, 422)
          // MUST NEVER silently delete. Transition to needs_correction so user can see & resolve
          const errorMsg = await extractErrorMessage(response);
          await markOperationNeedsCorrection(opId, errorMsg, response.status);
        } else {
          // Server Error (500, 502, 503, 504) -> Bounded exponential backoff
          const errorMsg = await extractErrorMessage(response);
          const nextRetryDelay = calculateBackoffDelay(item.retry_count || 0);
          const nextRetryAt = new Date(Date.now() + nextRetryDelay).toISOString();
          await markOperationRetryWait(
            opId,
            `Server Error (${response.status}): ${errorMsg}`,
            nextRetryAt,
            (item.retry_count || 0) + 1,
            response.status
          );
          // Pause queue processing on 5xx to avoid pounding a struggling server
          break;
        }
      } catch (networkError) {
        // Network failure or timeout -> Bounded exponential backoff
        const isTimeout = networkError.name === 'AbortError';
        const errorDesc = isTimeout
          ? 'Network request timed out (10s)'
          : (networkError.message || 'Network connection failed');
        const nextRetryDelay = calculateBackoffDelay(item.retry_count || 0);
        const nextRetryAt = new Date(Date.now() + nextRetryDelay).toISOString();

        await markOperationRetryWait(
          opId,
          errorDesc,
          nextRetryAt,
          (item.retry_count || 0) + 1,
          0
        );

        // Discontinue processing queue on network error
        break;
      }
    }
  } finally {
    isSyncInProgress = false;
  }

  const allItems = await getAllSyncItems();
  const pendingCount = allItems.filter((i) => i.sync_state !== 'synced').length;
  return { syncedCount, pendingCount };
};

/**
 * Fetch facilities from live API and cache locally
 */
export const fetchAndCacheFacilities = async () => {
  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    return { success: false, offline: true };
  }

  try {
    const response = await fetchWithTimeout(ENDPOINTS.facilityList, { method: 'GET' }, 8000);
    if (response.ok) {
      const data = await response.json();
      if (Array.isArray(data) && data.length > 0) {
        await cacheFacilities(data);
        return { success: true, count: data.length, facilities: data };
      }
    }
    return { success: false, status: response.status };
  } catch (err) {
    return { success: false, error: err.message };
  }
};

/**
 * Fetch medicine catalogue from live API and cache locally
 */
export const fetchAndCacheCatalogue = async () => {
  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    return { success: false, offline: true };
  }

  try {
    const response = await fetchWithTimeout(ENDPOINTS.inventoryCatalogue, { method: 'GET' }, 8000);
    if (response.ok) {
      const data = await response.json();
      if (Array.isArray(data) && data.length > 0) {
        await cacheMedicines(data);
        return { success: true, count: data.length, medicines: data };
      }
    }
    return { success: false, status: response.status };
  } catch (err) {
    return { success: false, error: err.message };
  }
};

/**
 * Get timestamp of the last successful sync
 */
export const getLastSuccessfulSyncTime = async () => {
  return getMeta('last_successful_sync_time');
};
