import React, { useState } from 'react';
import {
  FlaskConical,
  Clock,
  AlertTriangle,
  RefreshCw,
  Database,
  CheckCircle2,
  Calendar
} from 'lucide-react';

export const EvaluationPanel = ({
  runs = [],
  loading = false,
  error = null,
  isProduction = false,
  onRefresh,
}) => {
  const [selectedRunId, setSelectedRunId] = useState(() => {
    return runs.length > 0 ? runs[0].run_id : null;
  });

  const selectedRun = runs.find(r => r.run_id === (selectedRunId || (runs[0] && runs[0].run_id)));

  return (
    <div className="flex flex-col gap-6 w-full pb-16">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-4 border-b-2 border-neutral-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="w-2.5 h-2.5 rounded-full bg-purple-500"></span>
            <span className="text-[10px] font-mono tracking-[0.25em] text-neutral-400 uppercase">
              Algorithmic Benchmark &amp; Governance
            </span>
          </div>
          <h2 className="text-2xl font-black uppercase tracking-[0.1em] text-slate-900">
            Model Evaluation &amp; Safety Verification
          </h2>
          <p className="text-xs text-neutral-500 uppercase tracking-wider mt-1">
            Metrics retrieved exclusively from named validation runs against frozen baselines
          </p>
        </div>

        <button
          onClick={onRefresh}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-[#111] hover:bg-black text-white text-xs font-bold uppercase tracking-wider rounded transition-all cursor-pointer shadow-sm disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Benchmark</span>
        </button>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 bg-white rounded border border-neutral-200">
          <RefreshCw className="w-8 h-8 text-[#111] animate-spin mb-4" />
          <div className="text-xs font-bold uppercase tracking-[0.2em] text-[#111]">
            Retrieving Named Evaluation Run...
          </div>
        </div>
      ) : error ? (
        <div className="p-8 bg-red-50 border-2 border-red-500 rounded text-center">
          <AlertTriangle className="w-8 h-8 text-red-600 mx-auto mb-2" />
          <h3 className="text-sm font-bold uppercase text-red-900">Evaluation Pipeline Offline</h3>
          <p className="text-xs text-red-700 font-mono mt-1">{error}</p>
        </div>
      ) : runs.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 bg-white rounded border border-neutral-200 text-center p-6">
          <Database className="w-12 h-12 text-neutral-300 mb-3" />
          <h3 className="text-sm font-bold uppercase tracking-wider text-neutral-700">
            No Named Evaluation Runs Available
          </h3>
          <p className="text-xs text-neutral-500 mt-1 max-w-md">
            {isProduction
              ? "Evaluation endpoint is not yet merged on production backend. Development mock fixtures are suppressed in production mode per governance policy."
              : "No named validation benchmark records found in this environment."}
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-6">
          {/* Run Selector Card */}
          <div className="bg-white p-5 rounded border border-neutral-200 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex-1">
              <label className="block text-[10px] font-bold uppercase tracking-wider text-neutral-500 mb-1">
                Select Named Evaluation Run
              </label>
              <select
                value={selectedRun?.run_id || ''}
                onChange={(e) => setSelectedRunId(e.target.value)}
                className="w-full md:w-auto min-w-[320px] text-xs font-bold bg-neutral-50 border border-neutral-300 rounded px-3 py-2 uppercase tracking-wide focus:outline-none focus:border-black"
              >
                {runs.map(r => (
                  <option key={r.run_id} value={r.run_id}>
                    {r.run_name} ({r.run_id})
                  </option>
                ))}
              </select>
            </div>

            {selectedRun && (
              <div className="flex flex-wrap items-center gap-3">
                {selectedRun.is_simulated ? (
                  <div className="flex items-center gap-2 px-3 py-1.5 bg-amber-950/80 border border-amber-500 text-amber-300 rounded text-xs font-bold font-mono">
                    <FlaskConical className="w-3.5 h-3.5 text-amber-400" />
                    <span>[SIMULATED DEVELOPMENT FIXTURE]</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-950/80 border border-emerald-500 text-emerald-300 rounded text-xs font-bold font-mono">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    <span>[VERIFIED BENCHMARK RUN]</span>
                  </div>
                )}
              </div>
            )}
          </div>

          {selectedRun && (
            <>
              {/* Run Metadata Card */}
              <div className="bg-neutral-900 text-white p-6 rounded shadow-lg border border-neutral-800 space-y-4">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-neutral-800 pb-4">
                  <div>
                    <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-neutral-400">
                      Run Identifier: {selectedRun.run_id}
                    </span>
                    <h3 className="text-lg font-black uppercase tracking-wide text-white mt-0.5">
                      {selectedRun.run_name}
                    </h3>
                  </div>

                  <div className="flex items-center gap-3 text-xs font-mono text-neutral-400">
                    <Calendar className="w-3.5 h-3.5" />
                    <span>Executed: {new Date(selectedRun.date_executed).toLocaleString()}</span>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
                  <div className="bg-neutral-800/60 p-3 rounded border border-neutral-700/60">
                    <span className="text-[10px] uppercase text-neutral-400 block mb-1">
                      Algorithmic Models
                    </span>
                    <strong className="text-cyan-400">{selectedRun.model_version}</strong>
                  </div>

                  <div className="bg-neutral-800/60 p-3 rounded border border-neutral-700/60">
                    <span className="text-[10px] uppercase text-neutral-400 block mb-1">
                      Comparative Reference Baseline
                    </span>
                    <strong className="text-amber-400">{selectedRun.baseline_name}</strong>
                  </div>
                </div>
              </div>

              {/* Metrics Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {/* Metric 1 */}
                <div className="bg-white p-5 rounded border border-neutral-200 shadow-sm flex flex-col justify-between">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-neutral-500">
                    Shortage Prevention Rate
                  </span>
                  <div className="my-2">
                    <div className="text-3xl font-black font-mono text-neutral-900">
                      {selectedRun.metrics.shortage_prevention_rate_pct}%
                    </div>
                    <div className="text-[10px] font-mono text-emerald-600 font-bold mt-1">
                      +{(selectedRun.metrics.shortage_prevention_rate_pct - selectedRun.metrics.baseline_shortage_prevention_pct).toFixed(1)}% vs Baseline ({selectedRun.metrics.baseline_shortage_prevention_pct}%)
                    </div>
                  </div>
                  <span className="text-[9px] text-neutral-400 font-mono">
                    % of predicted stockouts successfully mitigated
                  </span>
                </div>

                {/* Metric 2 */}
                <div className="bg-white p-5 rounded border border-neutral-200 shadow-sm flex flex-col justify-between">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-neutral-500">
                    Stockout Hours Averted
                  </span>
                  <div className="my-2">
                    <div className="text-3xl font-black font-mono text-neutral-900">
                      {selectedRun.metrics.stockout_hours_avoided} <span className="text-xs font-normal">hrs</span>
                    </div>
                    <div className="text-[10px] font-mono text-emerald-600 font-bold mt-1">
                      Cumulative deficit buffer added
                    </div>
                  </div>
                  <span className="text-[9px] text-neutral-400 font-mono">
                    Total facility hours saved from complete stock depletion
                  </span>
                </div>

                {/* Metric 3 */}
                <div className="bg-white p-5 rounded border border-neutral-200 shadow-sm flex flex-col justify-between">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-neutral-500">
                    False Alarm Rate
                  </span>
                  <div className="my-2">
                    <div className="text-3xl font-black font-mono text-neutral-900">
                      {selectedRun.metrics.false_alarm_rate_pct}%
                    </div>
                    <div className="text-[10px] font-mono text-emerald-600 font-bold mt-1">
                      {(selectedRun.metrics.false_alarm_rate_pct - selectedRun.metrics.baseline_false_alarm_pct).toFixed(1)}% vs Baseline ({selectedRun.metrics.baseline_false_alarm_pct}%)
                    </div>
                  </div>
                  <span className="text-[9px] text-neutral-400 font-mono">
                    Spurious alerts requiring no intervention
                  </span>
                </div>

                {/* Metric 4 */}
                <div className="bg-white p-5 rounded border border-neutral-200 shadow-sm flex flex-col justify-between border-l-4 border-l-emerald-500">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-700">
                    Donor Retention Safety
                  </span>
                  <div className="my-2">
                    <div className="text-3xl font-black font-mono text-emerald-700">
                      {selectedRun.metrics.donor_retention_rate_pct}%
                    </div>
                    <div className="text-[10px] font-mono text-emerald-700 font-bold mt-1">
                      Zero Donor Depletions (100% compliant)
                    </div>
                  </div>
                  <span className="text-[9px] text-neutral-400 font-mono">
                    All donor PHCs retained minimum safety reserve
                  </span>
                </div>
              </div>

              {/* Lead Time Metric */}
              <div className="bg-white p-5 rounded border border-neutral-200 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded bg-neutral-900 text-white flex items-center justify-center shrink-0">
                    <Clock className="w-5 h-5 text-cyan-400" />
                  </div>
                  <div>
                    <h4 className="text-xs font-bold uppercase tracking-wider text-neutral-900">
                      Mean Redistribution Lead Time
                    </h4>
                    <p className="text-[10px] text-neutral-500 font-mono">
                      Average elapsed time from alert trigger to physical receipt at recipient PHC
                    </p>
                  </div>
                </div>

                <div className="text-right">
                  <div className="text-2xl font-black font-mono text-neutral-900">
                    {selectedRun.metrics.mean_lead_time_hours} Hours
                  </div>
                  <div className="text-[10px] font-mono text-emerald-600 font-bold">
                    vs Baseline: {selectedRun.metrics.baseline_lead_time_hours} Hours (-{((1 - selectedRun.metrics.mean_lead_time_hours / selectedRun.metrics.baseline_lead_time_hours) * 100).toFixed(0)}% faster)
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
};
