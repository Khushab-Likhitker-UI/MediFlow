import React from 'react';
import { AlertOctagon, AlertTriangle, Info, Clock, Database, FlaskConical, CheckCircle2, Truck, CheckCheck, XCircle } from 'lucide-react';

/**
 * Non-color-only Severity Badge
 * Includes distinct icon and textual bracket symbol for accessibility.
 */
export const SeverityBadge = ({ severity, className = '' }) => {
  switch (severity) {
    case 'critical':
      return (
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-bold tracking-wider uppercase bg-rose-50 text-rose-800 border border-rose-300 rounded ${className}`}
          role="status"
          aria-label="Severity Critical: immediate action required"
        >
          <AlertOctagon className="w-3.5 h-3.5 text-rose-600 shrink-0" />
          <span>[!] CRITICAL</span>
        </span>
      );
    case 'warning':
      return (
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-bold tracking-wider uppercase bg-amber-50 text-amber-800 border border-amber-300 rounded ${className}`}
          role="status"
          aria-label="Severity Warning: stock breach predicted"
        >
          <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
          <span>[▲] WARNING</span>
        </span>
      );
    case 'info':
    default:
      return (
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-medium tracking-wider uppercase bg-slate-100 text-slate-700 border border-slate-300 rounded ${className}`}
          role="status"
          aria-label="Severity Info"
        >
          <Info className="w-3.5 h-3.5 text-slate-500 shrink-0" />
          <span>[i] INFO</span>
        </span>
      );
  }
};

/**
 * Stale Data Badge — Indicates data verification is older than 24 hours.
 */
export const StaleDataBadge = ({ lastVerifiedAt, className = '' }) => (
  <span
    className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-[9px] font-semibold tracking-wider uppercase bg-amber-50 text-amber-800 border border-amber-200 rounded ${className}`}
    title={`Data age exceeds 24 hours. Last verified: ${lastVerifiedAt || 'Unknown'}`}
    role="status"
  >
    <Clock className="w-3 h-3 text-amber-600 shrink-0" />
    <span>STALE DATA (&gt;24h)</span>
  </span>
);

/**
 * Insufficient History Badge — Forecast model has < minimum required data window.
 */
export const InsufficientHistoryBadge = ({ className = '' }) => (
  <span
    className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-[9px] font-semibold tracking-wider uppercase bg-slate-100 text-slate-700 border border-slate-300 rounded ${className}`}
    title="Data history is fewer than 30 records; forecast has elevated variance"
    role="status"
  >
    <AlertTriangle className="w-3 h-3 text-slate-500 shrink-0" />
    <span>INSUFFICIENT HISTORY</span>
  </span>
);

/**
 * Synthetic Demo Badge — Cannot be mistaken for real operation.
 */
export const SyntheticDemoBadge = ({ className = '' }) => (
  <span
    className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-[9px] font-semibold tracking-widest uppercase bg-slate-100 text-slate-700 border border-slate-300 rounded ${className}`}
    title="Simulated demonstration data — NOT for clinical operational dispatch"
    role="alert"
  >
    <FlaskConical className="w-3 h-3 text-slate-500 shrink-0" />
    <span>SYNTHETIC DEMO</span>
  </span>
);

/**
 * Data Source Provenance Label
 */
export const DataSourceBadge = ({ source }) => {
  if (source === 'synthetic') {
    return (
      <span className="inline-flex items-center gap-1 text-[9px] font-mono font-medium text-slate-600 bg-slate-100 border border-slate-200 px-2 py-0.5 rounded">
        <FlaskConical className="w-2.5 h-2.5 text-slate-500" />
        ML_SYNTHETIC
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-[9px] font-mono font-medium text-slate-700 bg-slate-100 border border-slate-200 px-2 py-0.5 rounded">
      <Database className="w-2.5 h-2.5 text-slate-500" />
      DATABASE
    </span>
  );
};

/**
 * Transfer Lifecycle State Badge
 */
export const TransferStatusBadge = ({ status }) => {
  switch (status) {
    case 'proposed':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-semibold tracking-wider uppercase bg-blue-50 text-blue-700 border border-blue-200 rounded">
          <Clock className="w-3 h-3 text-blue-600" />
          Proposed
        </span>
      );
    case 'approved':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-semibold tracking-wider uppercase bg-indigo-50 text-indigo-700 border border-indigo-200 rounded">
          <CheckCircle2 className="w-3 h-3 text-indigo-600" />
          Approved (Pending Dispatch)
        </span>
      );
    case 'dispatched':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-semibold tracking-wider uppercase bg-amber-50 text-amber-800 border border-amber-200 rounded">
          <Truck className="w-3 h-3 text-amber-600" />
          Dispatched (In Transit)
        </span>
      );
    case 'received':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-semibold tracking-wider uppercase bg-teal-50 text-teal-800 border border-teal-200 rounded">
          <CheckCheck className="w-3 h-3 text-teal-600" />
          Received (Verifying)
        </span>
      );
    case 'reconciled':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-semibold tracking-wider uppercase bg-emerald-50 text-emerald-800 border border-emerald-200 rounded">
          <CheckCheck className="w-3 h-3 text-emerald-600" />
          Reconciled
        </span>
      );
    case 'rejected':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-semibold tracking-wider uppercase bg-rose-50 text-rose-800 border border-rose-200 rounded">
          <XCircle className="w-3 h-3 text-rose-600" />
          Rejected
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-medium tracking-wider uppercase bg-slate-100 text-slate-600 rounded">
          {status}
        </span>
      );
  }
};
