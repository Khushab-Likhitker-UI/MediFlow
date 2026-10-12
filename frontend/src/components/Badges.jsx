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
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-black tracking-wider uppercase bg-red-950/80 text-red-200 border border-red-500/80 rounded ${className}`}
          role="status"
          aria-label="Severity Critical: immediate action required"
        >
          <AlertOctagon className="w-3.5 h-3.5 text-red-400 shrink-0 animate-pulse" />
          <span>[!] CRITICAL</span>
        </span>
      );
    case 'warning':
      return (
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-bold tracking-wider uppercase bg-amber-950/80 text-amber-200 border border-amber-500/80 rounded ${className}`}
          role="status"
          aria-label="Severity Warning: stock breach predicted"
        >
          <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
          <span>[▲] WARNING</span>
        </span>
      );
    case 'info':
    default:
      return (
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-bold tracking-wider uppercase bg-neutral-800 text-neutral-300 border border-neutral-600 rounded ${className}`}
          role="status"
          aria-label="Severity Info"
        >
          <Info className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
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
    className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-[9px] font-bold tracking-wider uppercase bg-yellow-950/90 text-yellow-300 border border-yellow-500 rounded shadow-sm ${className}`}
    title={`Data age exceeds 24 hours. Last verified: ${lastVerifiedAt || 'Unknown'}`}
    role="status"
  >
    <Clock className="w-3 h-3 text-yellow-400 shrink-0" />
    <span>STALE DATA (&gt;24h)</span>
  </span>
);

/**
 * Insufficient History Badge — Forecast model has < minimum required data window.
 */
export const InsufficientHistoryBadge = ({ className = '' }) => (
  <span
    className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-[9px] font-bold tracking-wider uppercase bg-purple-950/90 text-purple-200 border border-purple-500 rounded shadow-sm ${className}`}
    title="Data history is fewer than 30 records; forecast has elevated variance"
    role="status"
  >
    <AlertTriangle className="w-3 h-3 text-purple-400 shrink-0" />
    <span>INSUFFICIENT HISTORY</span>
  </span>
);

/**
 * Synthetic Demo Badge — Cannot be mistaken for real operation.
 */
export const SyntheticDemoBadge = ({ className = '' }) => (
  <span
    className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-[9px] font-extrabold tracking-widest uppercase bg-amber-500 text-black border-2 border-amber-300 rounded shadow-[0_0_10px_rgba(245,158,11,0.4)] animate-pulse ${className}`}
    title="Simulated demonstration data — NOT for clinical operational dispatch"
    role="alert"
  >
    <FlaskConical className="w-3 h-3 text-black shrink-0" />
    <span>SYNTHETIC DEMO</span>
  </span>
);

/**
 * Data Source Provenance Label
 */
export const DataSourceBadge = ({ source }) => {
  if (source === 'synthetic') {
    return (
      <span className="inline-flex items-center gap-1 text-[9px] font-mono font-bold text-amber-400 bg-amber-950/60 border border-amber-600/60 px-2 py-0.5 rounded">
        <FlaskConical className="w-2.5 h-2.5" />
        ML_SYNTHETIC
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-[9px] font-mono font-bold text-emerald-400 bg-emerald-950/60 border border-emerald-600/60 px-2 py-0.5 rounded">
      <Database className="w-2.5 h-2.5" />
      SUPABASE_DB
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
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-bold tracking-wider uppercase bg-blue-950 text-blue-300 border border-blue-500 rounded">
          <Clock className="w-3 h-3 text-blue-400" />
          Proposed
        </span>
      );
    case 'approved':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-bold tracking-wider uppercase bg-indigo-950 text-indigo-300 border border-indigo-500 rounded">
          <CheckCircle2 className="w-3 h-3 text-indigo-400" />
          Approved (Pending Dispatch)
        </span>
      );
    case 'dispatched':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-bold tracking-wider uppercase bg-amber-950 text-amber-300 border border-amber-500 rounded">
          <Truck className="w-3 h-3 text-amber-400 animate-bounce" />
          Dispatched (In Transit)
        </span>
      );
    case 'received':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-bold tracking-wider uppercase bg-teal-950 text-teal-300 border border-teal-500 rounded">
          <CheckCheck className="w-3 h-3 text-teal-400" />
          Received (Verifying)
        </span>
      );
    case 'reconciled':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-bold tracking-wider uppercase bg-emerald-950 text-emerald-300 border border-emerald-500 rounded">
          <CheckCheck className="w-3 h-3 text-emerald-400" />
          Reconciled
        </span>
      );
    case 'rejected':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-bold tracking-wider uppercase bg-red-950 text-red-300 border border-red-500 rounded">
          <XCircle className="w-3 h-3 text-red-400" />
          Rejected
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-bold tracking-wider uppercase bg-neutral-800 text-neutral-400 rounded">
          {status}
        </span>
      );
  }
};
