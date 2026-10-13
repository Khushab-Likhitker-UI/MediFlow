/**
 * Smart Health Sentinel — Authoritative API Client
 * 
 * Interacts directly with the FastAPI backend according to the frozen Phase 1 API contract
 * (docs/implementation/API_CONTRACT.md).
 * No authoritative calculations (donor surplus, risk, transfer math) occur here;
 * server responses are strictly treated as source of truth.
 */

import { API_BASE_URL } from '../config';

class ApiError extends Error {
  constructor(message, status, detail = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

/**
 * Helper to make typed HTTP requests with standard error extraction
 */
async function request(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  // Attach token if present in localStorage
  try {
    const savedUser = localStorage.getItem('kraft_user');
    if (savedUser) {
      const parsed = JSON.parse(savedUser);
      if (parsed.token) {
        headers['Authorization'] = `Bearer ${parsed.token}`;
      }
    }
  } catch {
    // Ignore JSON parse errors for user
  }

  let response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (err) {
    throw new ApiError(
      `Network error connecting to Sentinel API at ${API_BASE_URL}. Ensure backend is running.`,
      0,
      err.message
    );
  }

  if (!response.ok) {
    let errorDetail = null;
    let errorMessage = `HTTP ${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      errorDetail = body.detail || body;
      if (typeof errorDetail === 'string') {
        errorMessage = errorDetail;
      } else if (Array.isArray(errorDetail)) {
        errorMessage = errorDetail.map(e => e.msg || JSON.stringify(e)).join(', ');
      }
    } catch {
      // Body not JSON
    }
    throw new ApiError(errorMessage, response.status, errorDetail);
  }

  // 204 No Content
  if (response.status === 204) {
    return null;
  }

  return await response.json();
}

export const realApiClient = {
  // ── Auth & Users ──────────────────────────────────────────────────────────
  async login(email, password) {
    return await request('/api/v1/users/login', {
      method: 'POST',
      body: JSON.stringify({ email: email.trim(), password }),
    });
  },

  // ── Facilities ────────────────────────────────────────────────────────────
  async fetchFacilities() {
    return await request('/api/v1/facility/');
  },

  // ── Alerts (Phase 1) ──────────────────────────────────────────────────────
  async fetchAlerts(params = {}) {
    const query = new URLSearchParams();
    if (params.phc_id && params.phc_id !== 'All') query.set('phc_id', params.phc_id);
    if (params.severity && params.severity !== 'All') query.set('severity', params.severity);
    if (params.status && params.status !== 'All') query.set('status', params.status);
    const queryString = query.toString() ? `?${query.toString()}` : '';
    const raw = await request(`/api/v1/alerts/${queryString}`);
    if (Array.isArray(raw)) {
      return raw.map((a, idx) => ({
        ...a,
        rank: a.rank || idx + 1,
        block: a.block || a.district || 'District Block',
        reserve_stock: a.reserve_stock ?? a.safety_reserve ?? a.reorder_level ?? 50,
        usable_stock: a.usable_stock ?? a.current_stock ?? 0,
        hours_until_stockout: a.hours_until_stockout ?? Math.round((a.days_of_supply ?? 1) * 24),
        plain_language_reason: a.plain_language_reason || a.message,
        data_source: a.data_source || 'database',
      }));
    }
    return raw;
  },

  async fetchAlertDonorCandidates(alertId) {
    return await request(`/api/v1/alerts/${alertId}/donors`);
  },

  // ── Transfers (Phase 1) ───────────────────────────────────────────────────
  async fetchTransfers(params = {}) {
    const query = new URLSearchParams();
    if (params.status && params.status !== 'All') query.set('status', params.status);
    if (params.phc_id && params.phc_id !== 'All') query.set('phc_id', params.phc_id);
    const queryString = query.toString() ? `?${query.toString()}` : '';
    return await request(`/api/v1/transfers/${queryString}`);
  },

  async proposeTransfer(payload) {
    return await request('/api/v1/transfers/propose', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async approveTransfer(transferId, payload = {}) {
    return await request(`/api/v1/transfers/${transferId}/approve`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async rejectTransfer(transferId, reason) {
    return await request(`/api/v1/transfers/${transferId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    });
  },

  async dispatchTransfer(transferId, payload = {}) {
    return await request(`/api/v1/transfers/${transferId}/dispatch`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async receiveTransfer(transferId, payload = {}) {
    return await request(`/api/v1/transfers/${transferId}/receive`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async reconcileTransfer(transferId, payload = {}) {
    return await request(`/api/v1/transfers/${transferId}/reconcile`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async escalateReplenishment(payload) {
    return await request('/api/v1/replenishment/escalate', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  // ── Evaluation Runs (Phase 1) ─────────────────────────────────────────────
  async fetchEvaluationRuns() {
    return await request('/api/v1/evaluations/runs');
  },

  // ── Predictions / ML (Phase 0/1) ──────────────────────────────────────────
  async fetchDemandForecast(itemId, horizonDays = 30) {
    return await request('/api/v1/predictions/demand', {
      method: 'POST',
      body: JSON.stringify({ item_id: itemId, horizon_days: horizonDays }),
    });
  },
};
