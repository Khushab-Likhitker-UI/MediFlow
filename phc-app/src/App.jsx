import React, { useState, useEffect } from 'react';
import {
  Wifi,
  WifiOff,
  MapPin,
  RefreshCw,
  Database,
  AlertTriangle,
  CheckCircle,
  Clock,
  RotateCw,
  Trash2,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import Forms from './components/Forms';
import {
  syncQueue,
  fetchAndCacheFacilities,
  fetchAndCacheCatalogue,
  getLastSuccessfulSyncTime,
} from './services/syncService';
import {
  getAllSyncItems,
  getCachedFacilities,
  resetOperationForManualRetry,
  removeSyncItem,
} from './db/indexedDB';
import './index.css';

const FALLBACK_PHCS = [
  { id: 'PHC-001', name: 'Central District Hospital', block: 'North Block' },
  { id: 'PHC-002', name: 'Green Valley PHC', block: 'North Block' },
  { id: 'PHC-003', name: 'Lakeview Clinic', block: 'South Block' },
  { id: 'PHC-004', name: 'Hilltop Health Center', block: 'East Block' },
  { id: 'PHC-005', name: 'Riverside Medical', block: 'West Block' },
  { id: 'PHC-006', name: 'Sunrise Care', block: 'North Block' },
  { id: 'PHC-007', name: 'Pine Grove Clinic', block: 'South Block' },
  { id: 'PHC-008', name: 'Maple Leaf Medical', block: 'East Block' },
  { id: 'PHC-009', name: 'Oaktree Health', block: 'West Block' },
  { id: 'PHC-010', name: 'Willow Branch Clinic', block: 'North Block' },
];

function App() {
  const [isOnline, setIsOnline] = useState(typeof navigator !== 'undefined' ? navigator.onLine : true);
  const [facilities, setFacilities] = useState(FALLBACK_PHCS);
  const [facilitiesCachedAt, setFacilitiesCachedAt] = useState(null);
  const [phcId, setPhcId] = useState('PHC-001');
  const [outboxItems, setOutboxItems] = useState([]);
  const [lastSyncTime, setLastSyncTime] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [showOutboxDetails, setShowOutboxDetails] = useState(false);

  const selectedPHC = facilities.find((p) => p.id === phcId) || facilities[0] || FALLBACK_PHCS[0];

  // Refresh outbox queue stats
  const refreshOutbox = React.useCallback(async () => {
    try {
      const items = await getAllSyncItems();
      // Sort: unacknowledged first, most recent first
      items.sort((a, b) => new Date(b.occurred_at || 0) - new Date(a.occurred_at || 0));
      setOutboxItems(items);

      const lastSync = await getLastSuccessfulSyncTime();
      if (lastSync) setLastSyncTime(lastSync);
    } catch (e) {
      console.error('Error refreshing outbox:', e);
    }
  }, []);

  // Load facilities from API or cache
  const loadFacilities = React.useCallback(async () => {
    try {
      if (navigator.onLine) {
        await fetchAndCacheFacilities();
        await fetchAndCacheCatalogue();
      }
      const cached = await getCachedFacilities();
      if (cached && cached.facilities && cached.facilities.length > 0) {
        setFacilities(cached.facilities);
        setFacilitiesCachedAt(cached.cachedAt);
        setPhcId((prev) => (cached.facilities.some((f) => f.id === prev) ? prev : cached.facilities[0].id));
      }
    } catch (err) {
      console.warn('Facility load failed, using fallback/cached:', err);
    }
  }, []);

  const triggerManualSync = async () => {
    if (!isOnline) return;
    setSyncing(true);
    try {
      await syncQueue(true);
      await refreshOutbox();
    } finally {
      setTimeout(() => setSyncing(false), 500);
    }
  };

  const handleManualRetry = async (clientOpId) => {
    await resetOperationForManualRetry(clientOpId);
    await refreshOutbox();
    if (isOnline) {
      await triggerManualSync();
    }
  };

  const handleDismissFailed = async (clientOpId) => {
    if (window.confirm('Are you sure you want to dismiss this operation from your local outbox? This cannot be undone.')) {
      await removeSyncItem(clientOpId);
      await refreshOutbox();
    }
  };

  useEffect(() => {
    loadFacilities();
    refreshOutbox();

    const handleOnline = async () => {
      setIsOnline(true);
      await loadFacilities();
      await syncQueue();
      await refreshOutbox();
    };

    const handleOffline = () => {
      setIsOnline(false);
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    // Periodic synchronization check every 5 seconds
    const interval = setInterval(() => {
      refreshOutbox();
      if (navigator.onLine) {
        syncQueue();
      }
    }, 5000);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
      clearInterval(interval);
    };
  }, [loadFacilities, refreshOutbox]);

  const pendingCount = outboxItems.filter((i) => i.sync_state === 'pending').length;
  const retryWaitCount = outboxItems.filter((i) => i.sync_state === 'retry_wait').length;
  const needsCorrectionCount = outboxItems.filter((i) => i.sync_state === 'needs_correction').length;
  const unacknowledgedCount = outboxItems.filter((i) => i.sync_state !== 'synced').length;

  return (
    <div className="min-h-screen bg-[#f5f5f7] flex flex-col font-sans">
      {/* Header */}
      <header className="bg-[#111111] text-white border-b-2 border-neutral-800 sticky top-0 z-30 shadow-[0_10px_30px_rgba(0,0,0,0.5)]">
        <div className="max-w-5xl mx-auto px-4 py-4 sm:px-6 flex flex-col sm:flex-row justify-between items-center gap-4">
          {/* Logo & Brand */}
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 border-2 border-white flex items-center justify-center transform rotate-45 shrink-0 shadow-[0_0_15px_rgba(255,255,255,0.2)]">
              <div className="transform -rotate-45 font-black tracking-widest text-[10px]">
                SENTINEL
              </div>
            </div>
            <div>
              <h1 className="text-xs font-bold tracking-[0.25em] text-white uppercase flex items-center gap-2">
                <span>Field Terminal</span>
                <span className="px-1.5 py-0.5 bg-red-600/80 text-white text-[9px] rounded font-mono">OFFLINE-PWA</span>
              </h1>
              <p className="text-[10px] text-neutral-400 mt-0.5 uppercase tracking-[0.2em] font-light">
                Durable Stock-Movement Outbox
              </p>
            </div>
          </div>

          {/* Status & Sync Badge */}
          <div className="flex items-center gap-3 w-full sm:w-auto justify-end">
            <button
              onClick={triggerManualSync}
              disabled={!isOnline || syncing}
              className="px-3 py-1.5 bg-neutral-900 hover:bg-neutral-800 border border-neutral-700 rounded text-[10px] uppercase font-bold tracking-wider text-neutral-300 flex items-center gap-2 transition-all disabled:opacity-50 cursor-pointer"
              title="Force Sync Now"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${syncing ? 'animate-spin text-cyan-400' : ''}`} />
              <span className="hidden sm:inline">Sync Outbox</span>
              {unacknowledgedCount > 0 && (
                <span className="px-1.5 py-0.2 bg-amber-500 text-black font-black rounded-full text-[9px]">
                  {unacknowledgedCount}
                </span>
              )}
            </button>

            <div
              className={`px-3 py-1.5 rounded text-[10px] uppercase font-bold tracking-widest flex items-center gap-2 border shadow-sm ${
                isOnline
                  ? 'bg-emerald-950/80 text-emerald-400 border-emerald-500/50'
                  : 'bg-red-950/80 text-red-400 border-red-500/50 animate-pulse'
              }`}
            >
              {isOnline ? <Wifi className="w-3.5 h-3.5 text-emerald-400" /> : <WifiOff className="w-3.5 h-3.5 text-red-400" />}
              <span>{isOnline ? 'ONLINE' : 'OFFLINE'}</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 p-4 sm:p-8 max-w-5xl w-full mx-auto pb-24">
        {/* Facility Selector */}
        <div className="mb-8 bg-[#111111] text-white p-6 rounded-lg shadow-xl border border-neutral-800 flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
          <div className="flex items-start gap-4">
            <div className="p-3 bg-neutral-900 border border-neutral-800 rounded shrink-0 text-red-500 mt-1">
              <MapPin className="w-6 h-6" />
            </div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-400">
                Assigned Facility
              </div>
              <h2 className="text-xl sm:text-2xl font-black text-white mt-1 tracking-wide">
                {selectedPHC.name}
              </h2>
              <div className="text-xs text-neutral-400 mt-1 uppercase tracking-wider font-mono flex items-center gap-2">
                <span>{selectedPHC.id} • {selectedPHC.block || selectedPHC.district || 'District'}</span>
                {facilitiesCachedAt && (
                  <span className="text-[10px] text-neutral-500 font-mono">
                    (Cache: {new Date(facilitiesCachedAt).toLocaleDateString()})
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="w-full md:w-auto flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
            <label className="text-[10px] font-bold uppercase tracking-wider text-neutral-400 shrink-0">
              Select Facility:
            </label>
            <select
              value={phcId}
              onChange={(e) => setPhcId(e.target.value)}
              className="bg-[#0c0c0c] border border-neutral-700 hover:border-white text-xs text-white uppercase font-bold py-2.5 px-3 rounded focus:outline-none focus:border-cyan-400 transition-colors font-mono cursor-pointer"
            >
              {facilities.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.id} - {p.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Offline Warning Banner */}
        {!isOnline && (
          <div className="mb-8 bg-neutral-900 border-l-4 border-amber-500 p-5 rounded-r shadow-md text-white flex items-center justify-between">
            <div>
              <h3 className="font-bold text-xs uppercase tracking-[0.15em] text-amber-400 flex items-center gap-2">
                <Database className="w-4 h-4" />
                Offline Mode Active — Durable Outbox Engaged
              </h3>
              <p className="text-xs text-neutral-300 mt-1">
                Network connection is absent. Any stock adjustment, bed, or attendance logged will be assigned a stable UUID, stored durably in IndexedDB, and automatically transmitted upon network restoration without data loss.
              </p>
            </div>
          </div>
        )}

        {/* Overview Outbox Summary Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 mb-8">
          <div className="bg-[#111111] text-white p-5 rounded shadow border border-neutral-800">
            <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-400">
              Outbox Total
            </div>
            <div className="text-2xl font-black mt-2 text-white">
              {unacknowledgedCount} <span className="text-xs font-normal text-neutral-400">queued</span>
            </div>
            <div className="text-[10px] text-neutral-500 mt-1 uppercase tracking-widest font-mono">
              {unacknowledgedCount === 0 ? 'All operations synced' : 'Pending server delivery'}
            </div>
          </div>

          <div className="bg-[#111111] text-white p-5 rounded shadow border border-neutral-800">
            <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-400">
              Pending / Syncing
            </div>
            <div className="text-2xl font-black mt-2 text-amber-400">
              {pendingCount}
            </div>
            <div className="text-[10px] text-neutral-500 mt-1 uppercase tracking-widest font-mono">
              Ready for transmit
            </div>
          </div>

          <div className="bg-[#111111] text-white p-5 rounded shadow border border-neutral-800">
            <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-400">
              Retry Wait
            </div>
            <div className={`text-2xl font-black mt-2 ${retryWaitCount > 0 ? 'text-orange-400' : 'text-neutral-500'}`}>
              {retryWaitCount}
            </div>
            <div className="text-[10px] text-neutral-500 mt-1 uppercase tracking-widest font-mono">
              Bounded backoff active
            </div>
          </div>

          <div className="bg-[#111111] text-white p-5 rounded shadow border border-neutral-800">
            <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-400">
              Needs Correction
            </div>
            <div className={`text-2xl font-black mt-2 ${needsCorrectionCount > 0 ? 'text-red-400 animate-pulse' : 'text-neutral-500'}`}>
              {needsCorrectionCount}
            </div>
            <div className="text-[10px] text-neutral-500 mt-1 uppercase tracking-widest font-mono">
              Validation / 4xx errors
            </div>
          </div>
        </div>

        {/* Last Sync Timestamp Banner */}
        <div className="mb-8 bg-neutral-900 border border-neutral-800 px-4 py-2.5 rounded text-neutral-400 text-xs font-mono flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
          <div className="flex items-center gap-2">
            <Clock className="w-3.5 h-3.5 text-neutral-400" />
            <span>
              Last Server Acknowledgement:{' '}
              {lastSyncTime ? new Date(lastSyncTime).toLocaleString() : 'No sync recorded in this session'}
            </span>
          </div>
          <button
            onClick={() => setShowOutboxDetails(!showOutboxDetails)}
            className="text-[11px] font-sans font-bold uppercase tracking-wider text-cyan-400 hover:text-cyan-300 flex items-center gap-1 cursor-pointer"
          >
            {showOutboxDetails ? 'Hide Outbox Inspector' : `Inspect Outbox (${outboxItems.length} records)`}
            {showOutboxDetails ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
        </div>

        {/* Unresolved Failures & Outbox Inspector Drawer */}
        {showOutboxDetails && (
          <div className="mb-8 bg-[#111111] border border-neutral-800 rounded-lg p-5 text-white">
            <div className="flex justify-between items-center pb-4 border-b border-neutral-800 mb-4">
              <h3 className="text-xs font-bold uppercase tracking-[0.2em] text-neutral-300 flex items-center gap-2">
                <Database className="w-4 h-4 text-cyan-400" />
                IndexedDB Outbox Queue Inspector
              </h3>
              <span className="text-[10px] font-mono text-neutral-500">
                KeyPath: client_operation_id
              </span>
            </div>

            {outboxItems.length === 0 ? (
              <p className="text-xs text-neutral-500 font-mono py-4 text-center">Outbox is empty.</p>
            ) : (
              <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
                {outboxItems.map((item) => {
                  const isSynced = item.sync_state === 'synced';
                  const isNeedsCorrection = item.sync_state === 'needs_correction';
                  const isRetryWait = item.sync_state === 'retry_wait';

                  return (
                    <div
                      key={item.client_operation_id}
                      className={`p-3.5 rounded border text-xs font-mono transition-all ${
                        isSynced
                          ? 'bg-neutral-900/40 border-neutral-800 text-neutral-400'
                          : isNeedsCorrection
                          ? 'bg-red-950/40 border-red-800/80 text-red-200'
                          : isRetryWait
                          ? 'bg-amber-950/40 border-amber-800/80 text-amber-200'
                          : 'bg-[#181818] border-neutral-700 text-neutral-200'
                      }`}
                    >
                      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span
                            className={`px-2 py-0.5 rounded text-[9px] uppercase font-bold tracking-wider ${
                              isSynced
                                ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                                : isNeedsCorrection
                                ? 'bg-red-900 text-red-200 border border-red-600'
                                : isRetryWait
                                ? 'bg-amber-900 text-amber-200 border border-amber-600'
                                : 'bg-blue-950 text-blue-300 border border-blue-700'
                            }`}
                          >
                            {item.sync_state}
                          </span>
                          <span className="font-bold text-white">
                            {item.update_type === 'Medicine'
                              ? `${item.quantity} ${item.unit || 'units'} of ${item.medicine_name || item.medicine}`
                              : item.update_type === 'Beds'
                              ? `${item.available_beds ?? item.quantity} Beds`
                              : `${item.doctors_present ?? item.quantity} Doctors`}
                          </span>
                          <span className="text-[10px] text-neutral-500">
                            [{item.facility || item.phc_id}]
                          </span>
                        </div>

                        <div className="flex items-center gap-2 self-end sm:self-auto">
                          {!isSynced && (
                            <button
                              type="button"
                              onClick={() => handleManualRetry(item.client_operation_id)}
                              className="px-2 py-1 bg-neutral-800 hover:bg-neutral-700 border border-neutral-600 rounded text-[9px] font-bold uppercase text-white flex items-center gap-1 cursor-pointer"
                              title="Reset state to pending and retry delivery"
                            >
                              <RotateCw className="w-3 h-3 text-cyan-400" />
                              <span>Retry</span>
                            </button>
                          )}
                          {isNeedsCorrection && (
                            <button
                              type="button"
                              onClick={() => handleDismissFailed(item.client_operation_id)}
                              className="px-2 py-1 bg-red-950 hover:bg-red-900 border border-red-700 rounded text-[9px] font-bold uppercase text-red-300 flex items-center gap-1 cursor-pointer"
                              title="Dismiss from local queue"
                            >
                              <Trash2 className="w-3 h-3 text-red-400" />
                              <span>Dismiss</span>
                            </button>
                          )}
                        </div>
                      </div>

                      <div className="mt-2 text-[10px] text-neutral-400 flex flex-wrap gap-x-4 gap-y-1">
                        <span>ID: {item.client_operation_id}</span>
                        <span>Occurred: {new Date(item.occurred_at || item.timestamp).toLocaleTimeString()}</span>
                        {item.retry_count > 0 && <span>Retries: {item.retry_count}</span>}
                        {item.next_retry_at && (
                          <span>
                            Next retry: {new Date(item.next_retry_at).toLocaleTimeString()}
                          </span>
                        )}
                      </div>

                      {item.error_message && (
                        <div className="mt-2 p-2 bg-black/40 rounded border border-red-900/50 text-[10px] text-red-300 flex items-start gap-1.5">
                          <AlertTriangle className="w-3 h-3 text-red-400 shrink-0 mt-0.5" />
                          <span>Error ({item.http_status || 'Network'}): {item.error_message}</span>
                        </div>
                      )}

                      {item.server_ack && (
                        <div className="mt-1 text-[9px] text-emerald-400 flex items-center gap-1">
                          <CheckCircle className="w-3 h-3 shrink-0" />
                          <span>Server Ack: {JSON.stringify(item.server_ack)}</span>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Input Forms */}
        <Forms phcId={phcId} isOnline={isOnline} onSyncTrigger={refreshOutbox} />
      </main>

      {/* Footer */}
      <footer className="bg-[#111111] text-neutral-500 border-t border-neutral-800 py-6 px-4 text-center text-[10px] uppercase font-mono tracking-widest">
        Sentinel District Health • Offline-First PWA • Durable Outbox Guaranteed
      </footer>
    </div>
  );
}

export default App;
