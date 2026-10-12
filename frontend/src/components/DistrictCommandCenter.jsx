import React, { useState, useMemo } from 'react';
import {
  SeverityBadge,
  StaleDataBadge,
  InsufficientHistoryBadge,
  SyntheticDemoBadge,
  DataSourceBadge
} from './Badges';
import {
  Search,
  Filter,
  ArrowRight,
  RefreshCw,
  Clock,
  Truck,
  AlertCircle,
  Database
} from 'lucide-react';

export const DistrictCommandCenter = ({
  alerts = [],
  loading = false,
  error = null,
  onRefresh,
  onSelectAlert,
}) => {
  const [search, setSearch] = useState('');
  const [filterSeverity, setFilterSeverity] = useState('All');
  const [filterBlock, setFilterBlock] = useState('All');
  const [filterFacility, setFilterFacility] = useState('All');
  const [filterStatus, setFilterStatus] = useState('All');

  // Extract unique blocks and facilities for dropdown filters
  const blocks = useMemo(() => {
    const set = new Set(alerts.map(a => a.block).filter(Boolean));
    return Array.from(set).sort();
  }, [alerts]);

  const facilities = useMemo(() => {
    const map = new Map();
    alerts.forEach(a => {
      if (a.phc_id && !map.has(a.phc_id)) {
        map.set(a.phc_id, a.facility_name);
      }
    });
    return Array.from(map.entries()).sort((a, b) => a[1].localeCompare(b[1]));
  }, [alerts]);

  const filteredAlerts = useMemo(() => {
    return alerts.filter(alert => {
      const q = search.toLowerCase();
      const matchesSearch =
        !search ||
        alert.facility_name.toLowerCase().includes(q) ||
        alert.item_name.toLowerCase().includes(q) ||
        alert.phc_id.toLowerCase().includes(q);

      const matchesSeverity = filterSeverity === 'All' || alert.severity === filterSeverity;
      const matchesBlock = filterBlock === 'All' || alert.block === filterBlock;
      const matchesFacility = filterFacility === 'All' || alert.phc_id === filterFacility;
      const matchesStatus = filterStatus === 'All' || alert.status === filterStatus;

      return matchesSearch && matchesSeverity && matchesBlock && matchesFacility && matchesStatus;
    });
  }, [alerts, search, filterSeverity, filterBlock, filterFacility, filterStatus]);

  const criticalCount = alerts.filter(a => a.severity === 'critical').length;
  const warningCount = alerts.filter(a => a.severity === 'warning').length;
  const syntheticCount = alerts.filter(a => a.data_source === 'synthetic').length;

  return (
    <div className="flex flex-col gap-6 w-full">
      {/* Top Banner / Triage Headline */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-4 border-b-2 border-neutral-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse"></span>
            <span className="text-[10px] font-mono tracking-[0.25em] text-neutral-400 uppercase">
              District Medical Surveillance
            </span>
          </div>
          <h2 className="text-2xl font-black uppercase tracking-[0.1em] text-slate-900">
            District Command Center
          </h2>
          <p className="text-xs text-neutral-500 uppercase tracking-wider mt-1">
            Ranked Shortage Surveillance &amp; Proactive Redistribution Gateway
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-neutral-900 border border-neutral-700 text-white rounded text-xs font-mono">
            <span className="text-neutral-400">OPEN:</span>
            <span className="font-bold text-red-400">{criticalCount} Critical</span>
            <span className="text-neutral-600">|</span>
            <span className="font-bold text-amber-400">{warningCount} Warning</span>
          </div>

          <button
            onClick={onRefresh}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-[#111] hover:bg-black text-white text-xs font-bold uppercase tracking-wider rounded transition-all cursor-pointer shadow-sm disabled:opacity-50"
            title="Refresh alerts"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Sync</span>
          </button>
        </div>
      </div>

      {/* Synthetic Demo Warning Banner if any alerts use synthetic data */}
      {syntheticCount > 0 && (
        <div className="p-3 bg-amber-950/40 border-l-4 border-amber-500 text-amber-200 text-xs flex items-center justify-between rounded-r">
          <div className="flex items-center gap-2.5">
            <SyntheticDemoBadge />
            <span>
              <strong>Surveillance Notice:</strong> {syntheticCount} alert(s) rely on synthetic/fallback ML forecasts due to sparse consumption history. These are highlighted for development testing.
            </span>
          </div>
        </div>
      )}

      {/* Filters and Search Bar */}
      <div className="bg-white p-4 rounded border border-neutral-200 shadow-sm flex flex-col md:flex-row gap-4 items-stretch md:items-center justify-between">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="w-4 h-4 text-neutral-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search facility name, code, or medicine..."
            className="w-full pl-9 pr-4 py-2 text-xs bg-neutral-50 border border-neutral-200 focus:border-[#111] rounded outline-none transition-colors"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1.5 text-xs text-neutral-500 font-bold uppercase tracking-wider">
            <Filter className="w-3.5 h-3.5" />
            <span>Filters:</span>
          </div>

          <select
            value={filterSeverity}
            onChange={(e) => setFilterSeverity(e.target.value)}
            className="text-xs bg-neutral-50 border border-neutral-200 rounded px-2.5 py-1.5 font-bold uppercase focus:outline-none focus:border-[#111]"
            aria-label="Filter by Severity"
          >
            <option value="All">All Severities</option>
            <option value="critical">Critical Only</option>
            <option value="warning">Warning Only</option>
          </select>

          <select
            value={filterBlock}
            onChange={(e) => setFilterBlock(e.target.value)}
            className="text-xs bg-neutral-50 border border-neutral-200 rounded px-2.5 py-1.5 font-bold uppercase focus:outline-none focus:border-[#111]"
            aria-label="Filter by Block"
          >
            <option value="All">All Blocks</option>
            {blocks.map(b => (
              <option key={b} value={b}>{b}</option>
            ))}
          </select>

          <select
            value={filterFacility}
            onChange={(e) => setFilterFacility(e.target.value)}
            className="text-xs bg-neutral-50 border border-neutral-200 rounded px-2.5 py-1.5 font-bold uppercase focus:outline-none focus:border-[#111]"
            aria-label="Filter by Facility"
          >
            <option value="All">All Facilities</option>
            {facilities.map(([id, name]) => (
              <option key={id} value={id}>{name} ({id})</option>
            ))}
          </select>

          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="text-xs bg-neutral-50 border border-neutral-200 rounded px-2.5 py-1.5 font-bold uppercase focus:outline-none focus:border-[#111]"
            aria-label="Filter by Status"
          >
            <option value="All">All Statuses</option>
            <option value="open">Open</option>
            <option value="proposal_pending">Proposal Pending</option>
          </select>

          {(search || filterSeverity !== 'All' || filterBlock !== 'All' || filterFacility !== 'All' || filterStatus !== 'All') && (
            <button
              onClick={() => {
                setSearch('');
                setFilterSeverity('All');
                setFilterBlock('All');
                setFilterFacility('All');
                setFilterStatus('All');
              }}
              className="text-[10px] font-bold text-neutral-500 hover:text-red-600 uppercase tracking-wider underline cursor-pointer ml-1"
            >
              Reset
            </button>
          )}
        </div>
      </div>

      {/* Main Alert List / Content */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-24 bg-white rounded border border-neutral-200">
          <RefreshCw className="w-8 h-8 text-[#111] animate-spin mb-4" />
          <div className="text-xs font-bold uppercase tracking-[0.2em] text-[#111]">
            Ranking District Shortage Alerts...
          </div>
          <p className="text-[10px] text-neutral-500 mt-1 uppercase tracking-wider font-mono">
            Evaluating reserve thresholds &amp; consumption trajectories
          </p>
        </div>
      ) : error ? (
        <div className="p-8 bg-red-50 border-2 border-red-500 rounded text-center">
          <AlertCircle className="w-10 h-10 text-red-600 mx-auto mb-3" />
          <h3 className="text-sm font-bold uppercase text-red-900 tracking-wider">
            Failed to Load District Shortage Alerts
          </h3>
          <p className="text-xs text-red-700 mt-2 font-mono max-w-xl mx-auto">
            {error}
          </p>
          <button
            onClick={onRefresh}
            className="mt-5 px-5 py-2 bg-red-600 hover:bg-red-700 text-white font-bold text-xs uppercase tracking-wider rounded transition-all cursor-pointer"
          >
            Retry Connection
          </button>
        </div>
      ) : filteredAlerts.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 bg-white rounded border border-neutral-200 text-center p-6">
          <Database className="w-12 h-12 text-neutral-300 mb-3" />
          <h3 className="text-sm font-bold uppercase tracking-wider text-neutral-700">
            No Shortage Alerts Found
          </h3>
          <p className="text-xs text-neutral-500 max-w-md mt-1">
            All primary health centres in this district are operating within prescribed safety stock thresholds, or no alerts match the active filters.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-neutral-500 flex justify-between items-center px-1">
            <span>Ranked by Urgency &amp; Hours to Complete Stockout</span>
            <span>Showing {filteredAlerts.length} of {alerts.length} Alerts</span>
          </div>

          <div className="grid grid-cols-1 gap-4">
            {filteredAlerts.map((alert) => (
              <div
                key={alert.alert_id}
                className={`bg-white rounded border transition-all duration-200 overflow-hidden shadow-sm hover:shadow-md ${
                  alert.severity === 'critical'
                    ? 'border-l-8 border-l-red-500 border-neutral-200'
                    : 'border-l-8 border-l-amber-500 border-neutral-200'
                }`}
              >
                <div className="p-5 md:p-6 flex flex-col md:flex-row md:items-center justify-between gap-6">
                  {/* Left Column: Priority Rank, Facility, Medicine */}
                  <div className="flex items-start gap-4 flex-1">
                    <div className="w-10 h-10 rounded bg-[#111] text-white flex flex-col items-center justify-center shrink-0 font-mono shadow-sm">
                      <span className="text-[8px] text-neutral-400 font-bold uppercase leading-none">RANK</span>
                      <span className="text-sm font-black leading-tight">#{alert.rank}</span>
                    </div>

                    <div className="space-y-1.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <SeverityBadge severity={alert.severity} />
                        <span className="text-xs font-bold uppercase tracking-wider text-neutral-900">
                          {alert.facility_name}
                        </span>
                        <span className="text-[10px] font-mono text-neutral-500 bg-neutral-100 px-2 py-0.5 rounded">
                          {alert.phc_id} &bull; {alert.block}
                        </span>
                        <DataSourceBadge source={alert.data_source} />
                      </div>

                      <div className="flex items-baseline gap-2">
                        <h4 className="text-base font-black uppercase tracking-wide text-neutral-900">
                          {alert.item_name}
                        </h4>
                        <span className="text-xs text-neutral-500 font-mono">
                          ({alert.dosage_form || 'Formulation'})
                        </span>
                      </div>

                      {/* Diagnostic Badges */}
                      <div className="flex flex-wrap items-center gap-2 pt-1">
                        {alert.is_stale_data && (
                          <StaleDataBadge lastVerifiedAt={alert.last_verified_at} />
                        )}
                        {alert.is_insufficient_history && (
                          <InsufficientHistoryBadge />
                        )}
                        {alert.data_source === 'synthetic' && (
                          <SyntheticDemoBadge />
                        )}
                        {alert.status === 'proposal_pending' && (
                          <span className="text-[9px] font-bold text-blue-800 bg-blue-100 px-2 py-0.5 rounded uppercase tracking-wider">
                            Proposal Pending Approval
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Middle Column: Stockout Horizon & Delivery Intel */}
                  <div className="flex flex-wrap md:flex-nowrap gap-6 items-center border-t md:border-t-0 md:border-l border-neutral-100 pt-4 md:pt-0 md:pl-6">
                    <div className="flex flex-col min-w-[130px]">
                      <span className="text-[9px] font-bold uppercase tracking-wider text-neutral-400">
                        Stockout In
                      </span>
                      <div className="flex items-baseline gap-1 mt-0.5">
                        <Clock className={`w-4 h-4 ${alert.severity === 'critical' ? 'text-red-600' : 'text-amber-600'}`} />
                        <span className={`text-lg font-black font-mono tracking-tight ${
                          alert.severity === 'critical' ? 'text-red-600' : 'text-amber-600'
                        }`}>
                          {alert.hours_until_stockout !== undefined ? `${alert.hours_until_stockout}h` : 'N/A'}
                        </span>
                      </div>
                      <span className="text-[10px] text-neutral-500 font-mono">
                        Usable: <strong>{alert.usable_stock}</strong> / Reserve: <strong>{alert.reserve_stock}</strong>
                      </span>
                    </div>

                    <div className="flex flex-col min-w-[150px]">
                      <span className="text-[9px] font-bold uppercase tracking-wider text-neutral-400">
                        Next Dependable Delivery
                      </span>
                      <div className="flex items-center gap-1.5 mt-0.5 text-xs font-bold text-neutral-800">
                        <Truck className="w-3.5 h-3.5 text-neutral-500" />
                        <span>
                          {alert.next_delivery_date
                            ? new Date(alert.next_delivery_date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
                            : 'None Scheduled'}
                        </span>
                      </div>
                      <span className="text-[10px] text-neutral-500 font-mono truncate max-w-[170px]" title={alert.last_verified_at}>
                        Verified: {alert.last_verified_at ? new Date(alert.last_verified_at).toLocaleTimeString() : 'N/A'}
                      </span>
                    </div>

                    {/* Action Button: Jump to Screen 2 */}
                    <div className="shrink-0 w-full md:w-auto">
                      <button
                        onClick={() => onSelectAlert(alert)}
                        className="w-full md:w-auto flex items-center justify-center gap-2 px-4 py-3 bg-[#111] hover:bg-black text-white text-xs font-bold uppercase tracking-[0.15em] rounded transition-all cursor-pointer shadow-sm group"
                      >
                        <span>Inspect &amp; Donors</span>
                        <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
