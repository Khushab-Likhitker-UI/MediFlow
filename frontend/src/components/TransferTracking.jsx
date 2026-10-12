import React, { useState, useMemo } from 'react';
import { TransferStatusBadge } from './Badges';
import {
  Truck,
  CheckCircle2,
  CheckCheck,
  Shield,
  FileText,
  Search,
  Filter,
  RefreshCw,
  Box
} from 'lucide-react';

const LIFECYCLE_STEPS = ['proposed', 'approved', 'dispatched', 'received', 'reconciled'];

export const TransferTracking = ({
  transfers = [],
  _user,
  loading = false,
  error = null,
  onRefresh,
  onDispatch,
  onReceive,
  onReconcile,
}) => {
  const [filterStatus, setFilterStatus] = useState('All');
  const [search, setSearch] = useState('');
  const [expandedTransferId, setExpandedTransferId] = useState(null);

  // Dispatch Modal state
  const [dispatchModalOpen, setDispatchModalOpen] = useState(false);
  const [activeTransferForDispatch, setActiveTransferForDispatch] = useState(null);
  const [vehicleId, setVehicleId] = useState('Cold-Chain Van KA-04-E-1192');
  const [dispatchNote, setDispatchNote] = useState('');

  // Receive Modal state
  const [receiveModalOpen, setReceiveModalOpen] = useState(false);
  const [activeTransferForReceive, setActiveTransferForReceive] = useState(null);
  const [receivedQuantity, setReceivedQuantity] = useState('');
  const [receiveRemarks, setReceiveRemarks] = useState('Inspected and verified tamper-evident seal intact.');

  const [submittingAction, setSubmittingAction] = useState(false);
  const [actionError, setActionError] = useState(null);

  const filteredTransfers = useMemo(() => {
    return transfers.filter((t) => {
      const q = search.toLowerCase();
      const matchesSearch =
        !search ||
        t.transfer_id.toLowerCase().includes(q) ||
        t.item_name.toLowerCase().includes(q) ||
        t.from_phc_name.toLowerCase().includes(q) ||
        t.to_phc_name.toLowerCase().includes(q);

      const matchesStatus = filterStatus === 'All' || t.status === filterStatus;

      return matchesSearch && matchesStatus;
    });
  }, [transfers, search, filterStatus]);

  const handleOpenDispatch = (t) => {
    setActiveTransferForDispatch(t);
    setVehicleId('Cold-Chain Van KA-04-E-1192');
    setDispatchNote('');
    setActionError(null);
    setDispatchModalOpen(true);
  };

  const handleConfirmDispatch = async () => {
    if (!activeTransferForDispatch) return;
    setSubmittingAction(true);
    setActionError(null);
    try {
      await onDispatch(activeTransferForDispatch.transfer_id, {
        vehicle_id: vehicleId.trim() || 'Logistics Van',
        note: dispatchNote.trim() || 'Dispatched from donor PHC.',
      });
      setDispatchModalOpen(false);
    } catch (err) {
      setActionError(err.message || 'Dispatch submission failed.');
    } finally {
      setSubmittingAction(false);
    }
  };

  const handleOpenReceive = (t) => {
    setActiveTransferForReceive(t);
    setReceivedQuantity(String(t.proposed_quantity));
    setReceiveRemarks('Inspected and verified tamper-evident seal intact.');
    setActionError(null);
    setReceiveModalOpen(true);
  };

  const handleConfirmReceive = async () => {
    if (!activeTransferForReceive) return;
    setSubmittingAction(true);
    setActionError(null);
    try {
      await onReceive(activeTransferForReceive.transfer_id, {
        actual_received_quantity: Number(receivedQuantity) || activeTransferForReceive.proposed_quantity,
        remarks: receiveRemarks.trim(),
      });
      setReceiveModalOpen(false);
    } catch (err) {
      setActionError(err.message || 'Receipt confirmation failed.');
    } finally {
      setSubmittingAction(false);
    }
  };

  const handleConfirmReconcile = async (transferId) => {
    setSubmittingAction(true);
    setActionError(null);
    try {
      await onReconcile(transferId);
    } catch (err) {
      setActionError(err.message || 'Ledger reconciliation failed.');
    } finally {
      setSubmittingAction(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 w-full pb-16">
      {/* Title & Stats */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-4 border-b-2 border-neutral-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-500 animate-pulse"></span>
            <span className="text-[10px] font-mono tracking-[0.25em] text-neutral-400 uppercase">
              Chain of Custody &amp; Verification
            </span>
          </div>
          <h2 className="text-2xl font-black uppercase tracking-[0.1em] text-slate-900">
            Transfer Tracking &amp; Audit Timeline
          </h2>
          <p className="text-xs text-neutral-500 uppercase tracking-wider mt-1">
            Lifecycle Management: Proposed &rarr; Approved &rarr; Dispatched &rarr; Received &rarr; Reconciled
          </p>
        </div>

        <button
          onClick={onRefresh}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-[#111] hover:bg-black text-white text-xs font-bold uppercase tracking-wider rounded transition-all cursor-pointer shadow-sm disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Ledger</span>
        </button>
      </div>

      {/* Critical Verification Notice Banner */}
      <div className="p-3 bg-neutral-900 text-neutral-300 border-l-4 border-cyan-400 text-xs rounded-r flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <Shield className="w-4 h-4 text-cyan-400 shrink-0" />
          <span>
            <strong>Protocol Constraint:</strong> Approved transfers remain in state <code>APPROVED</code> (Pending Dispatch). They are <strong>never</strong> marked completed until verified physical receipt and ledger reconciliation.
          </span>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-red-50 border border-red-500 text-red-700 text-xs rounded font-mono">
          Ledger Error: {error}
        </div>
      )}

      {actionError && (
        <div className="p-3 bg-red-50 border border-red-500 text-red-700 text-xs rounded font-mono">
          {actionError}
        </div>
      )}

      {/* Search and Filters */}
      <div className="bg-white p-4 rounded border border-neutral-200 shadow-sm flex flex-col md:flex-row gap-4 items-stretch md:items-center justify-between">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="w-4 h-4 text-neutral-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search transfer ID, medicine, or facility..."
            className="w-full pl-9 pr-4 py-2 text-xs bg-neutral-50 border border-neutral-200 focus:border-[#111] rounded outline-none transition-colors"
          />
        </div>

        <div className="flex items-center gap-2">
          <Filter className="w-3.5 h-3.5 text-neutral-500" />
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="text-xs bg-neutral-50 border border-neutral-200 rounded px-3 py-1.5 font-bold uppercase focus:outline-none focus:border-[#111]"
            aria-label="Filter transfers by status"
          >
            <option value="All">All Transfer States</option>
            <option value="proposed">Proposed</option>
            <option value="approved">Approved</option>
            <option value="dispatched">Dispatched</option>
            <option value="received">Received</option>
            <option value="reconciled">Reconciled</option>
            <option value="rejected">Rejected</option>
          </select>
        </div>
      </div>

      {/* Main Transfer List */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 bg-white rounded border border-neutral-200">
          <RefreshCw className="w-8 h-8 text-[#111] animate-spin mb-4" />
          <div className="text-xs font-bold uppercase tracking-[0.2em] text-[#111]">
            Loading Transfer Ledger...
          </div>
        </div>
      ) : filteredTransfers.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 bg-white rounded border border-neutral-200 text-center p-6">
          <Box className="w-12 h-12 text-neutral-300 mb-3" />
          <h3 className="text-sm font-bold uppercase tracking-wider text-neutral-700">
            No Transfers Found
          </h3>
          <p className="text-xs text-neutral-500 mt-1 max-w-sm">
            No active or historical transfers match the selected filters.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {filteredTransfers.map((t) => {
            const isExpanded = expandedTransferId === t.transfer_id;
            const currentStepIdx = LIFECYCLE_STEPS.indexOf(t.status);
            const isTerminated = t.status === 'rejected' || t.status === 'cancelled';

            return (
              <div
                key={t.transfer_id}
                className="bg-white rounded border border-neutral-200 shadow-sm overflow-hidden transition-all duration-200"
              >
                {/* Main Card Header */}
                <div className="p-5 md:p-6 flex flex-col md:flex-row md:items-center justify-between gap-6 border-b border-neutral-100">
                  <div className="space-y-2 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <TransferStatusBadge status={t.status} />
                      <span className="text-xs font-mono font-bold text-neutral-500">
                        {t.transfer_id}
                      </span>
                      {t.batch_number && (
                        <span className="text-[10px] font-mono text-neutral-400 bg-neutral-100 px-2 py-0.5 rounded">
                          Batch: {t.batch_number} (Exp: {t.expiry_date})
                        </span>
                      )}
                    </div>

                    <div className="flex items-baseline gap-2">
                      <h3 className="text-base font-black uppercase text-neutral-900 tracking-wide">
                        {t.item_name}
                      </h3>
                      <span className="text-xs font-bold text-neutral-600 font-mono">
                        {t.proposed_quantity} {t.unit}
                      </span>
                    </div>

                    {/* Routing Path */}
                    <div className="flex items-center gap-2 text-xs font-mono text-neutral-700 bg-neutral-50 p-2.5 rounded border border-neutral-100 max-w-2xl">
                      <span className="text-neutral-400 uppercase text-[10px]">Source:</span>
                      <strong className="text-neutral-900">{t.from_phc_name}</strong>
                      <span className="text-neutral-400">&rarr;</span>
                      <span className="text-neutral-400 uppercase text-[10px]">Destination:</span>
                      <strong className="text-neutral-900">{t.to_phc_name}</strong>
                    </div>

                    {/* Received Quantity Callout if applicable */}
                    {t.actual_received_quantity !== null && t.actual_received_quantity !== undefined && (
                      <div className="text-xs font-mono pt-1 flex items-center gap-2">
                        <span className="text-neutral-500">Dispatched: <strong>{t.proposed_quantity}</strong></span>
                        <span>&bull;</span>
                        <span className="text-emerald-700 font-bold">
                          Actual Received: <strong>{t.actual_received_quantity} {t.unit}</strong>
                        </span>
                        {t.actual_received_quantity !== t.proposed_quantity && (
                          <span className="text-red-600 text-[10px] font-bold">
                            (Discrepancy: {t.actual_received_quantity - t.proposed_quantity} units)
                          </span>
                        )}
                      </div>
                    )}

                    {t.status === 'rejected' && t.rejection_reason && (
                      <div className="text-xs text-red-700 bg-red-50 p-2 rounded border border-red-200">
                        <strong>Rejection Reason:</strong> {t.rejection_reason}
                      </div>
                    )}
                  </div>

                  {/* Actions depending on state */}
                  <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 shrink-0">
                    {/* Action: Dispatch (Only if Approved) */}
                    {t.status === 'approved' && (
                      <button
                        onClick={() => handleOpenDispatch(t)}
                        className="px-4 py-2.5 bg-amber-500 hover:bg-amber-600 text-black text-xs font-bold uppercase tracking-wider rounded transition-colors flex items-center justify-center gap-1.5 cursor-pointer shadow-sm"
                      >
                        <Truck className="w-3.5 h-3.5" />
                        <span>Dispatch Courier</span>
                      </button>
                    )}

                    {/* Action: Receive (Only if Dispatched) */}
                    {t.status === 'dispatched' && (
                      <button
                        onClick={() => handleOpenReceive(t)}
                        className="px-4 py-2.5 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold uppercase tracking-wider rounded transition-colors flex items-center justify-center gap-1.5 cursor-pointer shadow-sm"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Confirm Receipt</span>
                      </button>
                    )}

                    {/* Action: Reconcile (Only if Received) */}
                    {t.status === 'received' && (
                      <button
                        onClick={() => handleConfirmReconcile(t.transfer_id)}
                        disabled={submittingAction}
                        className="px-4 py-2.5 bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-bold uppercase tracking-wider rounded transition-colors flex items-center justify-center gap-1.5 cursor-pointer shadow-sm"
                      >
                        <CheckCheck className="w-3.5 h-3.5" />
                        <span>Reconcile Ledger</span>
                      </button>
                    )}

                    {/* Expand/Collapse Timeline button */}
                    <button
                      onClick={() => setExpandedTransferId(isExpanded ? null : t.transfer_id)}
                      className="px-3 py-2 text-xs font-bold uppercase tracking-wider text-neutral-600 hover:text-black border border-neutral-300 hover:border-black rounded transition-colors cursor-pointer"
                    >
                      {isExpanded ? 'Hide Timeline' : 'View Audit Timeline'}
                    </button>
                  </div>
                </div>

                {/* Visual Step Progress Bar */}
                {!isTerminated && (
                  <div className="bg-neutral-50 px-6 py-3 border-b border-neutral-100 flex items-center justify-between text-[10px] font-mono">
                    {LIFECYCLE_STEPS.map((step, idx) => {
                      const isComplete = currentStepIdx >= idx;
                      const isCurrent = currentStepIdx === idx;
                      return (
                        <div key={step} className="flex items-center gap-2">
                          <div className={`w-5 h-5 rounded-full flex items-center justify-center font-bold ${
                            isComplete
                              ? 'bg-neutral-900 text-white'
                              : 'bg-neutral-200 text-neutral-500'
                          }`}>
                            {idx + 1}
                          </div>
                          <span className={`uppercase font-bold ${
                            isCurrent
                              ? 'text-neutral-900 underline'
                              : isComplete
                              ? 'text-neutral-700'
                              : 'text-neutral-400'
                          }`}>
                            {step}
                          </span>
                          {idx < LIFECYCLE_STEPS.length - 1 && (
                            <span className="text-neutral-300 mx-2">&rarr;</span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Expanded Audit Timeline */}
                {isExpanded && (
                  <div className="p-6 bg-neutral-900 text-white space-y-4 font-mono">
                    <div className="flex items-center justify-between border-b border-neutral-800 pb-2">
                      <div className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-neutral-400" />
                        <span className="text-xs font-bold uppercase tracking-wider text-neutral-300">
                          Immutable Audit Timeline ({t.timeline ? t.timeline.length : 0} Events)
                        </span>
                      </div>
                      <span className="text-[10px] text-neutral-500">
                        LAST UPDATED: {new Date(t.updated_at).toLocaleString()}
                      </span>
                    </div>

                    <div className="space-y-3">
                      {t.timeline && t.timeline.length > 0 ? (
                        t.timeline.map((evt, idx) => (
                          <div
                            key={evt.event_id || idx}
                            className="flex items-start gap-4 text-xs border-l-2 border-neutral-700 pl-4 py-1"
                          >
                            <div className="text-neutral-500 min-w-[150px] shrink-0 text-[10px]">
                              {new Date(evt.timestamp).toLocaleString()}
                            </div>
                            <div className="space-y-0.5">
                              <div className="flex items-center gap-2">
                                <span className="font-bold text-neutral-200 uppercase">
                                  [{evt.status}]
                                </span>
                                <span className="text-neutral-400 text-[11px]">
                                  by {evt.actor_name} ({evt.actor_role})
                                </span>
                              </div>
                              <p className="text-neutral-300 text-xs font-sans">
                                {evt.note}
                              </p>
                            </div>
                          </div>
                        ))
                      ) : (
                        <div className="text-neutral-500 text-xs">No audit events logged.</div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Dispatch Modal */}
      {dispatchModalOpen && activeTransferForDispatch && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
          <div className="bg-white rounded border-2 border-neutral-900 w-full max-w-lg p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="text-sm font-black uppercase tracking-wider text-neutral-900 flex items-center gap-2">
                <Truck className="w-4 h-4 text-amber-500" />
                Dispatch Transfer ({activeTransferForDispatch.transfer_id})
              </h3>
              <button
                onClick={() => setDispatchModalOpen(false)}
                className="text-neutral-400 hover:text-black font-bold text-sm cursor-pointer"
              >
                &times;
              </button>
            </div>

            <div className="text-xs text-neutral-600 space-y-1">
              <div>Medicine: <strong>{activeTransferForDispatch.item_name}</strong></div>
              <div>Quantity: <strong>{activeTransferForDispatch.proposed_quantity} {activeTransferForDispatch.unit}</strong></div>
              <div>Route: {activeTransferForDispatch.from_phc_name} &rarr; {activeTransferForDispatch.to_phc_name}</div>
            </div>

            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-neutral-600 mb-1">
                Vehicle / Cold-Chain Carrier ID
              </label>
              <input
                type="text"
                value={vehicleId}
                onChange={(e) => setVehicleId(e.target.value)}
                className="w-full p-2.5 text-xs bg-neutral-50 border border-neutral-300 rounded focus:outline-none focus:border-black font-mono"
              />
            </div>

            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-neutral-600 mb-1">
                Courier / Dispatch Remarks
              </label>
              <input
                type="text"
                value={dispatchNote}
                onChange={(e) => setDispatchNote(e.target.value)}
                placeholder="e.g. Temperature monitored at 4°C, sealed in container..."
                className="w-full p-2.5 text-xs bg-neutral-50 border border-neutral-300 rounded focus:outline-none focus:border-black"
              />
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => setDispatchModalOpen(false)}
                className="px-4 py-2 text-xs font-bold uppercase text-neutral-600 hover:text-black cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmDispatch}
                disabled={submittingAction}
                className="px-5 py-2 bg-amber-500 hover:bg-amber-600 text-black text-xs font-black uppercase tracking-wider rounded transition-colors cursor-pointer disabled:opacity-50"
              >
                Confirm Dispatch
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Receive Modal */}
      {receiveModalOpen && activeTransferForReceive && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
          <div className="bg-white rounded border-2 border-neutral-900 w-full max-w-lg p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="text-sm font-black uppercase tracking-wider text-neutral-900 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-teal-600" />
                Confirm Physical Receipt ({activeTransferForReceive.transfer_id})
              </h3>
              <button
                onClick={() => setReceiveModalOpen(false)}
                className="text-neutral-400 hover:text-black font-bold text-sm cursor-pointer"
              >
                &times;
              </button>
            </div>

            <div className="text-xs text-neutral-600 space-y-1">
              <div>Medicine: <strong>{activeTransferForReceive.item_name}</strong></div>
              <div>Dispatched Quantity: <strong>{activeTransferForReceive.proposed_quantity} {activeTransferForReceive.unit}</strong></div>
            </div>

            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-neutral-600 mb-1">
                Actual Verified Received Quantity ({activeTransferForReceive.unit})
              </label>
              <input
                type="number"
                min="0"
                value={receivedQuantity}
                onChange={(e) => setReceivedQuantity(e.target.value)}
                className="w-full p-2.5 text-xs bg-neutral-50 border border-neutral-300 rounded focus:outline-none focus:border-black font-mono font-bold"
              />
              <span className="text-[10px] text-neutral-500 font-mono mt-1 block">
                Enter actual physical count counted by receiving pharmacist
              </span>
            </div>

            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-neutral-600 mb-1">
                Receipt Inspection Notes
              </label>
              <input
                type="text"
                value={receiveRemarks}
                onChange={(e) => setReceiveRemarks(e.target.value)}
                className="w-full p-2.5 text-xs bg-neutral-50 border border-neutral-300 rounded focus:outline-none focus:border-black"
              />
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => setReceiveModalOpen(false)}
                className="px-4 py-2 text-xs font-bold uppercase text-neutral-600 hover:text-black cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmReceive}
                disabled={submittingAction || !receivedQuantity}
                className="px-5 py-2 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold uppercase tracking-wider rounded transition-colors cursor-pointer disabled:opacity-50"
              >
                Confirm Physical Receipt
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
