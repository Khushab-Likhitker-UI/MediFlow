/**
 * Smart Health Sentinel — API Adapter with Production Safeguard
 * 
 * Provides a unified facade for all Sentinel data services.
 * In production builds, this adapter delegates EXCLUSIVELY to `realApiClient`.
 * In development builds, an explicit toggle allows switching between:
 *   - 'real': Live FastAPI / Supabase backend
 *   - 'mock': Isolated simulated fixtures (Phase 1 development adapter)
 * 
 * Mocks are NEVER silently used in production.
 */

import { realApiClient } from './client';
import {
  INITIAL_FIXTURE_ALERTS,
  INITIAL_FIXTURE_TRANSFERS,
  INITIAL_FIXTURE_EVALUATION_RUNS
} from './fixtures';

const IS_PROD = Boolean(import.meta.env.PROD);
const STORAGE_KEY = 'sentinel_api_mode';

// In-memory mutable state for development simulation
let mockAlerts = JSON.parse(JSON.stringify(INITIAL_FIXTURE_ALERTS));
let mockTransfers = JSON.parse(JSON.stringify(INITIAL_FIXTURE_TRANSFERS));
let mockEvaluationRuns = JSON.parse(JSON.stringify(INITIAL_FIXTURE_EVALUATION_RUNS));
let currentMockScenario = 'normal'; // 'normal' | 'empty' | 'error' | 'permission_denied'

// Reset or configure test scenarios
export function resetMockData() {
  mockAlerts = JSON.parse(JSON.stringify(INITIAL_FIXTURE_ALERTS));
  mockTransfers = JSON.parse(JSON.stringify(INITIAL_FIXTURE_TRANSFERS));
  mockEvaluationRuns = JSON.parse(JSON.stringify(INITIAL_FIXTURE_EVALUATION_RUNS));
  currentMockScenario = 'normal';
}

export function setMockScenario(scenario) {
  currentMockScenario = scenario;
}

let currentMemoryApiMode = null;

export function getApiMode() {
  if (IS_PROD) {
    return 'real';
  }
  if (currentMemoryApiMode) {
    return currentMemoryApiMode;
  }
  const saved = typeof window !== 'undefined' ? sessionStorage.getItem(STORAGE_KEY) : null;
  if (saved === 'mock') return 'mock';
  return 'real';
}

export function setApiMode(mode) {
  if (IS_PROD && mode === 'mock') {
    throw new Error('Security Violation: Mock mode is strictly forbidden in production builds.');
  }
  currentMemoryApiMode = mode;
  if (typeof window !== 'undefined') {
    sessionStorage.setItem(STORAGE_KEY, mode);
  }
}

export const api = {
  getApiMode,
  setApiMode,
  isProduction: IS_PROD,

  // ── Authentication ────────────────────────────────────────────────────────
  async login(email, password) {
    const mode = getApiMode();
    if (mode === 'real') {
      return await realApiClient.login(email, password);
    }

    if (currentMockScenario === 'error') {
      throw new Error('Simulated Backend 500: Database authentication failure.');
    }

    // Development fallback mock login
    await new Promise(r => setTimeout(r, 200));
    const role = email.includes('admin') ? 'admin' : email.includes('manager') ? 'manager' : 'viewer';
    return {
      id: 99,
      username: email.split('@')[0],
      email,
      role,
      token: `dev-simulated-token-${role}`,
      data_source: 'synthetic',
    };
  },

  // ── Facilities ────────────────────────────────────────────────────────────
  async fetchFacilities() {
    const mode = getApiMode();
    if (mode === 'real') {
      return await realApiClient.fetchFacilities();
    }

    if (currentMockScenario === 'error') {
      throw new Error('Simulated Backend Error: Could not fetch facility registry.');
    }
    if (currentMockScenario === 'empty') {
      return [];
    }

    await new Promise(r => setTimeout(r, 150));
    // Provide facilities derived from alerts
    const facilitiesMap = new Map();
    mockAlerts.forEach(a => {
      if (!facilitiesMap.has(a.phc_id)) {
        facilitiesMap.set(a.phc_id, {
          id: a.phc_id,
          name: a.facility_name,
          block: a.block,
          district: a.district,
          stockItems: [
            {
              itemName: a.item_name,
              currentUnits: a.usable_stock,
              avgDailyConsumption: a.avg_daily_consumption,
              unit: a.unit,
              reorderLevel: a.reserve_stock,
            }
          ],
          lastUpdated: a.last_verified_at,
          data_source: 'synthetic',
        });
      }
    });
    return Array.from(facilitiesMap.values());
  },

  // ── Alerts (Screen 1) ─────────────────────────────────────────────────────
  async fetchAlerts(params = {}) {
    const mode = getApiMode();
    if (mode === 'real') {
      return await realApiClient.fetchAlerts(params);
    }

    if (currentMockScenario === 'error') {
      throw new Error('Simulated API Error (500): ML Shortage inference pipeline timed out.');
    }
    if (currentMockScenario === 'empty') {
      return [];
    }

    await new Promise(r => setTimeout(r, 200));
    let filtered = [...mockAlerts];

    if (params.phc_id && params.phc_id !== 'All') {
      filtered = filtered.filter(a => a.phc_id === params.phc_id);
    }
    if (params.severity && params.severity !== 'All') {
      filtered = filtered.filter(a => a.severity === params.severity);
    }
    if (params.status && params.status !== 'All') {
      filtered = filtered.filter(a => a.status === params.status);
    }
    if (params.block && params.block !== 'All') {
      filtered = filtered.filter(a => a.block === params.block);
    }

    // Ranked by priority rank ascending
    return filtered.sort((a, b) => a.rank - b.rank);
  },

  async fetchAlertDonorCandidates(alertId) {
    const mode = getApiMode();
    if (mode === 'real') {
      return await realApiClient.fetchAlertDonorCandidates(alertId);
    }

    if (currentMockScenario === 'error') {
      throw new Error('Simulated API Error (500): Donor candidate solver unavailable.');
    }

    await new Promise(r => setTimeout(r, 150));
    const alert = mockAlerts.find(a => a.alert_id === alertId);
    if (!alert) {
      throw new Error(`Alert with ID ${alertId} not found.`);
    }
    return alert.donor_candidates || [];
  },

  // ── Transfers (Screens 2 & 3) ─────────────────────────────────────────────
  async fetchTransfers(params = {}) {
    const mode = getApiMode();
    if (mode === 'real') {
      return await realApiClient.fetchTransfers(params);
    }

    if (currentMockScenario === 'error') {
      throw new Error('Simulated API Error: Transfers ledger unavailable.');
    }
    if (currentMockScenario === 'empty') {
      return [];
    }

    await new Promise(r => setTimeout(r, 150));
    let filtered = [...mockTransfers];
    if (params.status && params.status !== 'All') {
      filtered = filtered.filter(t => t.status === params.status);
    }
    if (params.phc_id && params.phc_id !== 'All') {
      filtered = filtered.filter(t => t.from_phc_id === params.phc_id || t.to_phc_id === params.phc_id);
    }
    return filtered;
  },

  async proposeTransfer(payload, user = null) {
    const mode = getApiMode();
    if (mode === 'real') {
      return await realApiClient.proposeTransfer(payload);
    }

    if (currentMockScenario === 'permission_denied' || (user && user.role === 'viewer')) {
      const err = new Error('Permission Denied: Viewer role cannot propose stock redistribution.');
      err.status = 403;
      throw err;
    }

    await new Promise(r => setTimeout(r, 200));
    const newId = `TR-2026-${Math.floor(1000 + Math.random() * 9000)}`;
    const now = new Date().toISOString();

    const newTransfer = {
      transfer_id: newId,
      alert_id: payload.alert_id || null,
      from_phc_id: payload.from_phc_id,
      from_phc_name: payload.from_phc_name || payload.from_phc_id,
      to_phc_id: payload.to_phc_id,
      to_phc_name: payload.to_phc_name || payload.to_phc_id,
      item_id: payload.item_id,
      item_name: payload.item_name || 'Medicine',
      unit: payload.unit || 'units',
      proposed_quantity: Number(payload.quantity),
      actual_received_quantity: null,
      batch_number: payload.batch_number || 'BATCH-PROPOSED',
      expiry_date: payload.expiry_date || '2027-12-31',
      status: 'proposed',
      reason: payload.reason || 'Coordinator rebalancing proposal',
      created_at: now,
      updated_at: now,
      timeline: [
        {
          event_id: `EVT-${Date.now()}-1`,
          status: 'proposed',
          timestamp: now,
          actor_name: user ? user.username : 'Authorized Coordinator',
          actor_role: user ? user.role : 'manager',
          note: payload.reason || 'Proposal generated from shortage triage.',
        }
      ],
      simulation_fixture: true,
    };

    mockTransfers.unshift(newTransfer);

    // Update associated alert status if applicable
    if (payload.alert_id) {
      const targetAlert = mockAlerts.find(a => a.alert_id === payload.alert_id);
      if (targetAlert) targetAlert.status = 'proposal_pending';
    }

    return newTransfer;
  },

  async approveTransfer(transferId, user = null) {
    const mode = getApiMode();
    if (mode === 'real') {
      return await realApiClient.approveTransfer(transferId);
    }

    if (currentMockScenario === 'permission_denied' || (user && user.role === 'viewer')) {
      const err = new Error('Permission Denied: Viewer role is not authorized to approve transfers.');
      err.status = 403;
      throw err;
    }

    await new Promise(r => setTimeout(r, 200));
    const transfer = mockTransfers.find(t => t.transfer_id === transferId);
    if (!transfer) {
      throw new Error(`Transfer ${transferId} not found.`);
    }

    const now = new Date().toISOString();
    transfer.status = 'approved';
    transfer.approved_by = user ? `${user.username} (${user.role.toUpperCase()})` : 'Authorized Officer';
    transfer.updated_at = now;
    transfer.timeline.push({
      event_id: `EVT-${Date.now()}-2`,
      status: 'approved',
      timestamp: now,
      actor_name: user ? user.username : 'Authorized Officer',
      actor_role: user ? user.role : 'admin',
      note: 'Explicit approval granted. Stock reserved at donor facility.',
    });

    return { ...transfer };
  },

  async rejectTransfer(transferId, reason, user = null) {
    const mode = getApiMode();
    if (mode === 'real') {
      return await realApiClient.rejectTransfer(transferId, reason);
    }

    if (!reason || !reason.trim()) {
      const err = new Error('Rejection requires an explicit plain-language clinical or operational reason.');
      err.status = 422;
      throw err;
    }

    if (currentMockScenario === 'permission_denied' || (user && user.role === 'viewer')) {
      const err = new Error('Permission Denied: Viewer role cannot reject transfers.');
      err.status = 403;
      throw err;
    }

    await new Promise(r => setTimeout(r, 200));
    const transfer = mockTransfers.find(t => t.transfer_id === transferId);
    if (!transfer) {
      throw new Error(`Transfer ${transferId} not found.`);
    }

    const now = new Date().toISOString();
    transfer.status = 'rejected';
    transfer.rejection_reason = reason.trim();
    transfer.updated_at = now;
    transfer.timeline.push({
      event_id: `EVT-${Date.now()}-rej`,
      status: 'rejected',
      timestamp: now,
      actor_name: user ? user.username : 'Review Officer',
      actor_role: user ? user.role : 'manager',
      note: `REJECTED: ${reason.trim()}`,
    });

    return { ...transfer };
  },

  async dispatchTransfer(transferId, payload = {}, user = null) {
    const mode = getApiMode();
    if (mode === 'real') {
      return await realApiClient.dispatchTransfer(transferId, payload);
    }

    await new Promise(r => setTimeout(r, 200));
    const transfer = mockTransfers.find(t => t.transfer_id === transferId);
    if (!transfer) throw new Error(`Transfer ${transferId} not found.`);

    const now = new Date().toISOString();
    transfer.status = 'dispatched';
    transfer.vehicle_id = payload.vehicle_id || 'Cold-Chain Van DL-01-M-4822';
    transfer.dispatched_by = user ? user.username : 'Dispatch Logistics Officer';
    transfer.updated_at = now;
    transfer.timeline.push({
      event_id: `EVT-${Date.now()}-disp`,
      status: 'dispatched',
      timestamp: now,
      actor_name: user ? user.username : 'Dispatch Officer',
      actor_role: 'courier',
      note: `Dispatched via ${transfer.vehicle_id}. Cold chain verified.`,
    });

    return { ...transfer };
  },

  async receiveTransfer(transferId, payload = {}, user = null) {
    const mode = getApiMode();
    if (mode === 'real') {
      return await realApiClient.receiveTransfer(transferId, payload);
    }

    await new Promise(r => setTimeout(r, 200));
    const transfer = mockTransfers.find(t => t.transfer_id === transferId);
    if (!transfer) throw new Error(`Transfer ${transferId} not found.`);

    const actualQty = payload.actual_received_quantity !== undefined && payload.actual_received_quantity !== null
      ? Number(payload.actual_received_quantity)
      : transfer.proposed_quantity;

    const now = new Date().toISOString();
    transfer.status = 'received';
    transfer.actual_received_quantity = actualQty;
    transfer.received_by = user ? user.username : 'Receiving Pharmacist';
    transfer.updated_at = now;

    const difference = actualQty - transfer.proposed_quantity;
    const diffNote = difference === 0
      ? 'Full proposed quantity verified.'
      : `Discrepancy logged: ${difference > 0 ? '+' : ''}${difference} units difference.`;

    transfer.timeline.push({
      event_id: `EVT-${Date.now()}-recv`,
      status: 'received',
      timestamp: now,
      actor_name: user ? user.username : 'Receiving Pharmacist',
      actor_role: 'manager',
      note: `Received ${actualQty} ${transfer.unit}. ${diffNote} Remarks: ${payload.remarks || 'None'}`,
    });

    return { ...transfer };
  },

  async reconcileTransfer(transferId, payload = {}, user = null) {
    const mode = getApiMode();
    if (mode === 'real') {
      return await realApiClient.reconcileTransfer(transferId, payload);
    }

    await new Promise(r => setTimeout(r, 200));
    const transfer = mockTransfers.find(t => t.transfer_id === transferId);
    if (!transfer) throw new Error(`Transfer ${transferId} not found.`);

    const now = new Date().toISOString();
    transfer.status = 'reconciled';
    transfer.updated_at = now;
    transfer.timeline.push({
      event_id: `EVT-${Date.now()}-rec`,
      status: 'reconciled',
      timestamp: now,
      actor_name: user ? user.username : 'Chief Inventory Auditor',
      actor_role: 'admin',
      note: 'Audit reconciliation complete. Inventory ledger balances settled in database.',
    });

    return { ...transfer };
  },

  async escalateReplenishment(payload, user = null) {
    const mode = getApiMode();
    if (mode === 'real') {
      return await realApiClient.escalateReplenishment(payload);
    }

    await new Promise(r => setTimeout(r, 200));
    return {
      ticket_id: `REQ-${Date.now()}`,
      status: 'escalated_to_central_depot',
      requested_by: user ? user.username : 'District Coordinator',
      item_name: payload.item_name,
      facility_name: payload.facility_name,
      message: 'Emergency central requisition dispatched to State Medical Depot.',
      data_source: 'synthetic',
    };
  },

  // ── Evaluation Runs (Screen 4) ────────────────────────────────────────────
  async fetchEvaluationRuns() {
    const mode = getApiMode();
    if (mode === 'real') {
      return await realApiClient.fetchEvaluationRuns();
    }

    if (currentMockScenario === 'error') {
      throw new Error('Simulated API Error: Evaluation repository unavailable.');
    }
    if (currentMockScenario === 'empty') {
      return [];
    }

    await new Promise(r => setTimeout(r, 150));
    return [...mockEvaluationRuns];
  },
};
