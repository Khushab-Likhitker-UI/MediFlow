# Smart Health Sentinel — Phase 1C Status Report

> **Component:** PHC Offline-First PWA (`phc-app/`)  
> **Date:** 2026-10-13  
> **Status:** COMPLETE  
> **Tests:** 14/14 automated Vitest unit & integration tests passing (`npm test`)  
> **Linter & Build:** 0 warnings, 0 errors (`oxlint`), clean Vite PWA production build  

---

## 1. Summary of Accomplishments

1. **Configurable Hosted API Configuration:**
   - Implemented [`phc-app/src/config.js`](file:///run/media/amitrk/New%20Volume1/project/phc-app/src/config.js) supporting `VITE_API_URL` and `VITE_API_BASE_URL`.
   - Localhost (`http://localhost:8000`) is restricted strictly to local development (`import.meta.env.DEV`).
   - Production builds safely default to the hosted Railway API (`https://smarthealth-production.up.railway.app`). A production build on a mobile device will never call the phone's local loopback.
   - Verified that no secret keys or database connection credentials exist in client code or environment templates. Added [`phc-app/.env.example`](file:///run/media/amitrk/New%20Volume1/project/phc-app/.env.example).

2. **Stable Operation Identity:**
   - Every mutation generates a cryptographically random UUID (`client_operation_id`) once at user interaction time in [`phc-app/src/db/indexedDB.js`](file:///run/media/amitrk/New%20Volume1/project/phc-app/src/db/indexedDB.js).
   - This identity is immediately persisted to IndexedDB store `inventory_sync_queue` *before* any network delivery is attempted.
   - All subsequent retries and deduplication requests reuse the exact same `client_operation_id` and payload identity.
   - Payloads conform to the domain model: `client_operation_id`, `facility`, `movement_type`, `medicine`, `batch_number`, base-unit `quantity`, `unit`, and `occurred_at` (ISO 8601 UTC).

3. **Durable Outbox States & Lifecycle:**
   - Formalized outbox states: `pending`, `syncing`, `synced`, `retry_wait`, `needs_correction`.
   - **No Silent Deletions:** Unacknowledged operations are never deleted on failure.
   - Validation and client errors (HTTP 4xx, e.g. 400, 404, 409, 422) transition to `needs_correction` with human-readable error messages for user resolution, retaining the queue row.
   - Network timeouts and server errors (HTTP 5xx) transition to `retry_wait` with bounded exponential backoff (initial 2s, capped at 60s + random jitter), avoiding infinite tight retry loops.
   - Operations are only marked `synced` upon durable server acknowledgement (HTTP 200/201). Synced rows retain the server response (`server_ack`) and are skipped on subsequent sync passes.

4. **Dynamic Facility & Medicine Data Caching:**
   - Replaced hardcoded facility and medicine lists as the source of truth.
   - Facilities are fetched from `GET /api/v1/facility/` and cached locally in `facilities_cache` with a cache timestamp.
   - Medicines and units are fetched from `GET /api/v1/inventory/` and cached in `catalogue_cache`.
   - Offline operations visibly display when cached catalogue data is used along with cache timestamp and staleness warnings.
   - Validates non-negative integer quantity and base unit before enqueuing.

5. **User Interface Enhancements:**
   - Online/Offline status indicator with real-time connectivity listeners.
   - Outbox summary bar showing unacknowledged count, pending count, retry wait count, needs correction count, and last successful sync timestamp.
   - Interactive Outbox Queue Inspector drawer showing per-operation status badges, readable error details, server acknowledgements, and manual "Retry" controls.

6. **Comprehensive Automated Test Suite:**
   - Added [`phc-app/tests/outbox_sync.test.js`](file:///run/media/amitrk/New%20Volume1/project/phc-app/tests/outbox_sync.test.js) with Vitest and `fake-indexeddb`.
   - 14/14 tests passing covering:
     - Offline user action and UUID persistence.
     - Reload with pending outbox.
     - Reconnect and sync with server acknowledgement.
     - Network timeout and bounded backoff.
     - Server 500 error handling and queue pausing.
     - Server 422 validation error retention (`needs_correction`).
     - Duplicate submission and manual retry ID preservation.
     - Out-of-order events handled cleanly.
     - Facility cache absence and offline cache retrieval.
     - Medicine catalogue caching with base units.
     - Guarantee that synced operations are not re-applied.

---

## 2. Change Requests & Backend Blockers Logged for Integration Lead

> [!WARNING]
> **Change Request CR-1C-01: Server-Side Deduplication & Idempotency**
> - **Affected Endpoint:** `POST /api/v1/inventory/update` (and Phase 1 transfer endpoints)
> - **Context:** In `backend/app/routes/inventory.py`, `POST /api/v1/inventory/update` accepts `phc_id`, `medicine_name`, `quantity`, and `timestamp`. The route currently generates a random UUID on the server (`sync_id = str(uuid.uuid4())`) and does not verify whether `client_operation_id` or `X-Client-Operation-Id` was already processed.
> - **Client Implementation:** The PWA sends `client_operation_id` in the request body as well as the `X-Client-Operation-Id` header.
> - **Requested Backend Change (Member A / Phase 1):**
>   1. Accept `client_operation_id: str | None` in `StockUpdate` schema (`backend/app/models/schemas.py`).
>   2. Read header `X-Client-Operation-Id` or body `client_operation_id`.
>   3. Check whether `client_operation_id` has already been recorded in `sync_log` or `inventory_transactions.offline_sync_id`.
>   4. If duplicate, return HTTP 200 with the cached/prior acknowledgement (`{"status": "success", "message": "Stock logged", "client_operation_id": ...}`) instead of re-inserting inventory adjustment.

---

## 3. Verification Commands & Results

```bash
# Lint check
cd phc-app
npm run lint
# Output: Found 0 warnings and 0 errors.

# Automated Vitest test suite
npm test
# Output: 14 passed (14)

# Production Vite PWA build
npm run build
# Output: dist/ built successfully, PWA precache 7 entries generated in dist/sw.js
```
