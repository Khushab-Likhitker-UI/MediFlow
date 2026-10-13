import React, { useState, useEffect, useCallback } from 'react';
import { DistrictCommandCenter } from './components/DistrictCommandCenter';
import { AlertDetailAndDonorReview } from './components/AlertDetailAndDonorReview';
import { TransferTracking } from './components/TransferTracking';
import { EvaluationPanel } from './components/EvaluationPanel';
import { PHCGrid } from './components/PHCGrid';
import { RedistributionSankey } from './components/RedistributionSankey';
import { LoginPage } from './components/LoginPage';
import { SyntheticDemoBadge } from './components/Badges';
import { api, getApiMode, setApiMode } from './api/adapter';
import { API_BASE_URL } from './config';
import {
  Activity,
  AlertOctagon,
  CheckCircle2,
  Database,
  FlaskConical,
  GitMerge,
  LogOut,
  Shield,
  Truck
} from 'lucide-react';

function App() {
  const [user, setUser] = useState(() => {
    try {
      const saved = localStorage.getItem('kraft_user');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  const [activeTab, setActiveTab] = useState('command'); // 'command' | 'transfers' | 'evaluation' | 'overview' | 'redistribution'
  const [selectedAlert, setSelectedAlert] = useState(null);
  const [apiMode, setApiModeState] = useState(getApiMode);

  // Data states
  const [alerts, setAlerts] = useState([]);
  const [transfers, setTransfers] = useState([]);
  const [facilities, setFacilities] = useState([]);
  const [evaluationRuns, setEvaluationRuns] = useState([]);

  // Status & loading
  const [loadingAlerts, setLoadingAlerts] = useState(false);
  const [loadingTransfers, setLoadingTransfers] = useState(false);
  const [loadingEvaluation, setLoadingEvaluation] = useState(false);
  const [alertsError, setAlertsError] = useState(null);
  const [transfersError, setTransfersError] = useState(null);
  const [evalError, setEvalError] = useState(null);
  const [globalNotice, setGlobalNotice] = useState(null);

  // Sync all core data
  const loadAllData = useCallback(async () => {
    setLoadingAlerts(true);
    setLoadingTransfers(true);
    setLoadingEvaluation(true);
    setAlertsError(null);
    setTransfersError(null);
    setEvalError(null);

    // 1. Fetch Alerts
    try {
      const alertData = await api.fetchAlerts();
      setAlerts(Array.isArray(alertData) ? alertData : []);
    } catch (err) {
      setAlertsError(err.message || 'Failed to fetch shortage alerts');
    } finally {
      setLoadingAlerts(false);
    }

    // 2. Fetch Transfers
    try {
      const transferData = await api.fetchTransfers();
      setTransfers(Array.isArray(transferData) ? transferData : []);
    } catch (err) {
      setTransfersError(err.message || 'Failed to fetch transfer ledger');
    } finally {
      setLoadingTransfers(false);
    }

    // 3. Fetch Facilities (for legacy view)
    try {
      const facilityData = await api.fetchFacilities();
      setFacilities(Array.isArray(facilityData) ? facilityData : []);
    } catch {
      // Non-critical for coordinator workflow
    }

    // 4. Fetch Evaluation Runs
    try {
      const runData = await api.fetchEvaluationRuns();
      setEvaluationRuns(Array.isArray(runData) ? runData : []);
    } catch (err) {
      setEvalError(err.message || 'Failed to fetch evaluation runs');
    } finally {
      setLoadingEvaluation(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      loadAllData();
    }
  }, [user, apiMode, loadAllData]);

  const handleLogin = (userData) => {
    localStorage.setItem('kraft_user', JSON.stringify(userData));
    setUser(userData);
  };

  const handleLogout = () => {
    localStorage.removeItem('kraft_user');
    setUser(null);
  };

  const handleToggleApiMode = (newMode) => {
    try {
      setApiMode(newMode);
      setApiModeState(newMode);
      setGlobalNotice(`Switched API mode to: ${newMode.toUpperCase()}`);
      setTimeout(() => setGlobalNotice(null), 3500);
    } catch (err) {
      alert(err.message);
    }
  };

  const handleSwitchRole = (role) => {
    if (!user) return;
    const updated = { ...user, role };
    setUser(updated);
    localStorage.setItem('kraft_user', JSON.stringify(updated));
    setGlobalNotice(`Role switched to: ${role.toUpperCase()}`);
    setTimeout(() => setGlobalNotice(null), 3000);
  };

  // Workflow Handlers
  const handleSelectAlert = (alert) => {
    setSelectedAlert(alert);
    setActiveTab('command');
  };

  const handleProposalApproved = async (proposalPayload) => {
    if (proposalPayload.is_rejection) {
      // Rejection flow
      await api.rejectTransfer(
        proposalPayload.alert_id,
        proposalPayload.reason,
        user
      );
      setGlobalNotice('Proposal rejected and recorded with mandatory justification.');
      setSelectedAlert(null);
      await loadAllData();
      return;
    }

    // Approval flow: Propose and approve
    const newTransfer = await api.proposeTransfer(proposalPayload, user);
    await api.approveTransfer(newTransfer.transfer_id, user);

    // Refresh server state
    await loadAllData();

    // Transition to Screen 3 (Transfer Tracking)
    setSelectedAlert(null);
    setActiveTab('transfers');
    setGlobalNotice(`Transfer ${newTransfer.transfer_id} approved! Currently pending physical dispatch.`);
    setTimeout(() => setGlobalNotice(null), 5000);
  };

  const handleEscalateReplenishment = async (escalationPayload) => {
    await api.escalateReplenishment(escalationPayload, user);
    setGlobalNotice(`Emergency depot requisition dispatched for ${escalationPayload.item_name}.`);
    setTimeout(() => setGlobalNotice(null), 4000);
  };

  const handleDispatchTransfer = async (transferId, payload) => {
    await api.dispatchTransfer(transferId, payload, user);
    await loadAllData();
    setGlobalNotice(`Transfer ${transferId} dispatched via courier.`);
    setTimeout(() => setGlobalNotice(null), 3000);
  };

  const handleReceiveTransfer = async (transferId, payload) => {
    await api.receiveTransfer(transferId, payload, user);
    await loadAllData();
    setGlobalNotice(`Transfer ${transferId} received and actual count verified.`);
    setTimeout(() => setGlobalNotice(null), 3000);
  };

  const handleReconcileTransfer = async (transferId) => {
    await api.reconcileTransfer(transferId, {}, user);
    await loadAllData();
    setGlobalNotice(`Transfer ${transferId} reconciled into permanent ledger.`);
    setTimeout(() => setGlobalNotice(null), 3000);
  };

  if (!user) {
    return <LoginPage onLogin={handleLogin} />;
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col md:flex-row font-sans text-slate-900">
      {/* Sidebar Navigation */}
      <aside className="w-full md:w-72 bg-slate-900 border-r border-slate-800 flex flex-col z-20 sticky top-0 md:h-screen text-white justify-between shadow-xl">
        <div>
          {/* Logo Header */}
          <div className="p-8 pb-6 flex flex-col items-center justify-center text-center mt-2 border-b border-slate-800">
            <div className="w-12 h-12 border-2 border-slate-400 flex items-center justify-center mb-4 transform rotate-45 shadow-sm">
              <div className="transform -rotate-45 font-black tracking-[0.2em] text-[10px] text-white">MED</div>
            </div>
            <h1 className="text-xs font-bold tracking-[0.25em] text-white uppercase">
              District Sentinel
            </h1>
            <p className="text-[9px] text-slate-400 mt-1 uppercase tracking-[0.25em] font-mono">
              Medical Triage Operations
            </p>
          </div>

          {/* Primary Navigation Tabs */}
          <nav className="p-4 flex flex-row md:flex-col gap-1.5 overflow-x-auto md:overflow-hidden">
            <button
              onClick={() => {
                setActiveTab('command');
                setSelectedAlert(null);
              }}
              className={`flex items-center justify-start gap-3.5 px-4 py-3 text-xs font-semibold uppercase tracking-[0.12em] transition-all rounded cursor-pointer ${
                activeTab === 'command'
                  ? 'bg-slate-800 text-white border-l-4 border-rose-500 shadow-sm'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/50 border-l-4 border-transparent'
              }`}
            >
              <AlertOctagon className="h-4 w-4 shrink-0 text-rose-400" />
              <span>1. Command Center</span>
            </button>

            <button
              onClick={() => setActiveTab('transfers')}
              className={`flex items-center justify-start gap-3.5 px-4 py-3 text-xs font-semibold uppercase tracking-[0.12em] transition-all rounded cursor-pointer ${
                activeTab === 'transfers'
                  ? 'bg-slate-800 text-white border-l-4 border-blue-500 shadow-sm'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/50 border-l-4 border-transparent'
              }`}
            >
              <Truck className="h-4 w-4 shrink-0 text-blue-400" />
              <span>2. Transfer Tracking</span>
            </button>

            <button
              onClick={() => setActiveTab('evaluation')}
              className={`flex items-center justify-start gap-3.5 px-4 py-3 text-xs font-semibold uppercase tracking-[0.12em] transition-all rounded cursor-pointer ${
                activeTab === 'evaluation'
                  ? 'bg-slate-800 text-white border-l-4 border-indigo-500 shadow-sm'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/50 border-l-4 border-transparent'
              }`}
            >
              <FlaskConical className="h-4 w-4 shrink-0 text-indigo-400" />
              <span>3. Model Evaluation</span>
            </button>

            <div className="my-2 border-t border-slate-800 px-4 pt-2">
              <span className="text-[9px] font-mono uppercase tracking-widest text-slate-500">
                District Registry
              </span>
            </div>

            <button
              onClick={() => setActiveTab('overview')}
              className={`flex items-center justify-start gap-3.5 px-4 py-2.5 text-xs font-medium uppercase tracking-[0.12em] transition-all rounded cursor-pointer ${
                activeTab === 'overview'
                  ? 'bg-slate-800 text-white border-l-4 border-slate-300'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/40 border-l-4 border-transparent'
              }`}
            >
              <Activity className="h-3.5 w-3.5 shrink-0 text-slate-400" />
              <span>Facility Grid</span>
            </button>

            <button
              onClick={() => setActiveTab('redistribution')}
              className={`flex items-center justify-start gap-3.5 px-4 py-2.5 text-xs font-medium uppercase tracking-[0.12em] transition-all rounded cursor-pointer ${
                activeTab === 'redistribution'
                  ? 'bg-slate-800 text-white border-l-4 border-slate-300'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/40 border-l-4 border-transparent'
              }`}
            >
              <GitMerge className="h-3.5 w-3.5 shrink-0 text-slate-400" />
              <span>Sankey Flow</span>
            </button>
          </nav>
        </div>

        {/* Bottom Drawer: Environment, Dev Switcher & Officer Profile */}
        <div className="p-5 border-t border-slate-800 bg-slate-950 flex flex-col gap-3">
          {/* API Mode Indicator & Switcher */}
          <div className="bg-slate-900 border border-slate-800 p-2.5 rounded text-[10px] space-y-2">
            <div className="flex items-center justify-between font-mono">
              <span className="text-slate-400 uppercase">API Adapter:</span>
              {apiMode === 'real' ? (
                <span className="text-emerald-400 font-bold flex items-center gap-1">
                  <Database className="w-3 h-3" /> Live Backend
                </span>
              ) : (
                <span className="text-amber-400 font-medium flex items-center gap-1">
                  <FlaskConical className="w-3 h-3" /> Dev Adapter
                </span>
              )}
            </div>

            {/* Development Only Switcher */}
            {!api.isProduction && (
              <div className="flex items-center gap-1 pt-1 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => handleToggleApiMode('mock')}
                  className={`flex-1 py-1 px-1.5 text-[9px] font-semibold rounded uppercase cursor-pointer transition-colors ${
                    apiMode === 'mock'
                      ? 'bg-slate-700 text-white'
                      : 'bg-slate-800 text-slate-400 hover:text-white'
                  }`}
                  title="Switch to simulated Phase 1 fixtures"
                >
                  Mock Fixtures
                </button>
                <button
                  type="button"
                  onClick={() => handleToggleApiMode('real')}
                  className={`flex-1 py-1 px-1.5 text-[9px] font-semibold rounded uppercase cursor-pointer transition-colors ${
                    apiMode === 'real'
                      ? 'bg-blue-600 text-white shadow-sm'
                      : 'bg-slate-800 text-slate-400 hover:text-white'
                  }`}
                  title="Connect to live backend"
                >
                  Live Backend
                </button>
              </div>
            )}
          </div>

          {/* Role Clearance & Dev Switcher */}
          <div className="bg-slate-900/80 p-2.5 rounded border border-slate-800 text-[10px] flex items-center justify-between">
            <div className="flex items-center gap-2 overflow-hidden">
              <div className="w-7 h-7 rounded bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0">
                <Shield className="w-3.5 h-3.5 text-slate-300" />
              </div>
              <div className="overflow-hidden">
                <div className="font-bold text-white truncate text-xs">{user.username}</div>
                <div className="text-neutral-500 font-mono text-[9px] uppercase tracking-wider">
                  Role: <strong>{user.role}</strong>
                </div>
              </div>
            </div>

            {/* Quick role switcher for testing authorization states */}
            {!api.isProduction && (
              <div className="flex gap-1">
                {['admin', 'manager', 'viewer'].map((r) => (
                  <button
                    key={r}
                    onClick={() => handleSwitchRole(r)}
                    className={`px-1.5 py-0.5 rounded text-[8px] font-bold uppercase font-mono cursor-pointer ${
                      user.role === r
                        ? 'bg-white text-black'
                        : 'bg-neutral-800 text-neutral-400 hover:text-white'
                    }`}
                    title={`Switch test role to ${r}`}
                  >
                    {r[0]}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Sign Out */}
          <button
            onClick={handleLogout}
            className="w-full py-2 px-3 flex items-center justify-center gap-2 text-xs font-bold uppercase tracking-wider text-neutral-400 hover:text-red-400 bg-neutral-900/40 hover:bg-neutral-900 rounded border border-neutral-800/80 transition-colors cursor-pointer"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 p-6 md:p-10 overflow-y-auto w-full max-w-7xl mx-auto">
        {/* Global Action Toast / Notice */}
        {globalNotice && (
          <div className="mb-6 p-4 bg-emerald-950 text-emerald-200 border-l-4 border-emerald-400 text-xs font-bold uppercase tracking-wider flex items-center justify-between rounded-r shadow-lg animate-in fade-in slide-in-from-top-2">
            <div className="flex items-center gap-2.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>{globalNotice}</span>
            </div>
            <button
              onClick={() => setGlobalNotice(null)}
              className="text-emerald-400 hover:text-white cursor-pointer"
            >
              &times;
            </button>
          </div>
        )}

        {/* Dev Mode Banner with Synthetic Demo Badge */}
        {apiMode === 'mock' && (
          <div className="mb-6 p-3 bg-amber-500/10 border border-amber-500/40 rounded flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-amber-900">
            <div className="flex items-center gap-2">
              <SyntheticDemoBadge />
              <span className="font-medium">
                Running with Phase 1 Development Adapter Fixtures. All shortage risk calculations and donor rankings are simulated.
              </span>
            </div>
            <span className="text-[10px] font-mono text-amber-800 shrink-0">
              Target API: <code>{API_BASE_URL}</code>
            </span>
          </div>
        )}

        {/* View Router */}
        {activeTab === 'command' && (
          selectedAlert ? (
            <AlertDetailAndDonorReview
              alert={selectedAlert}
              user={user}
              onBack={() => setSelectedAlert(null)}
              onProposalApproved={handleProposalApproved}
              onEscalateReplenishment={handleEscalateReplenishment}
            />
          ) : (
            <DistrictCommandCenter
              alerts={alerts}
              loading={loadingAlerts}
              error={alertsError}
              onRefresh={loadAllData}
              onSelectAlert={handleSelectAlert}
            />
          )
        )}

        {activeTab === 'transfers' && (
          <TransferTracking
            transfers={transfers}
            user={user}
            loading={loadingTransfers}
            error={transfersError}
            onRefresh={loadAllData}
            onDispatch={handleDispatchTransfer}
            onReceive={handleReceiveTransfer}
            onReconcile={handleReconcileTransfer}
          />
        )}

        {activeTab === 'evaluation' && (
          <EvaluationPanel
            runs={evaluationRuns}
            loading={loadingEvaluation}
            error={evalError}
            isProduction={api.isProduction}
            onRefresh={loadAllData}
          />
        )}

        {activeTab === 'overview' && (
          <PHCGrid phcs={facilities} onAddPHC={loadAllData} />
        )}

        {activeTab === 'redistribution' && (
          <RedistributionSankey phcs={facilities} />
        )}
      </main>
    </div>
  );
}

export default App;
