import React, { useState, useMemo } from 'react';
import {
  SeverityBadge,
  StaleDataBadge,
  InsufficientHistoryBadge,
  SyntheticDemoBadge,
  DataSourceBadge
} from './Badges';
import {
  ArrowLeft,
  ShieldCheck,
  ShieldAlert,
  Truck,
  CheckCircle2,
  XCircle,
  Lock,
  Info
} from 'lucide-react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  CartesianGrid
} from 'recharts';

export const AlertDetailAndDonorReview = ({
  alert,
  user,
  onBack,
  onProposalApproved,
  onEscalateReplenishment,
}) => {
  const [selectedDonorId, setSelectedDonorId] = useState(() => {
    const firstEligible = alert?.donor_candidates?.find(c => c.eligible);
    return firstEligible ? firstEligible.donor_phc_id : null;
  });

  const [customQuantity, setCustomQuantity] = useState(() => {
    const firstEligible = alert?.donor_candidates?.find(c => c.eligible);
    return firstEligible ? firstEligible.transferable_quantity : '';
  });

  const [justificationReason, setJustificationReason] = useState('Critical stockout avoidance ahead of delivery cycle.');
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [rejectError, setRejectError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [actionError, setActionError] = useState(null);
  const [escalatedSuccess, setEscalatedSuccess] = useState(false);

  const selectedDonor = useMemo(() => {
    return alert?.donor_candidates?.find(c => c.donor_phc_id === selectedDonorId);
  }, [alert?.donor_candidates, selectedDonorId]);

  const hasSafeDonors = useMemo(() => {
    return Boolean(alert?.donor_candidates && alert.donor_candidates.some(c => c.eligible));
  }, [alert?.donor_candidates]);

  if (!alert) return null;

  const canApprove = user && (user.role === 'admin' || user.role === 'manager');

  const handleSelectDonor = (donor) => {
    if (!donor.eligible) return;
    setSelectedDonorId(donor.donor_phc_id);
    setCustomQuantity(donor.transferable_quantity);
  };

  const handleApprove = async () => {
    if (!canApprove) {
      setActionError('Permission Denied: Viewer role cannot approve transfers.');
      return;
    }
    if (!selectedDonor) {
      setActionError('Please select an eligible donor candidate first.');
      return;
    }

    setSubmitting(true);
    setActionError(null);

    try {
      // Propose and authorize transfer through API adapter
      const proposalPayload = {
        alert_id: alert.alert_id,
        from_phc_id: selectedDonor.donor_phc_id,
        from_phc_name: selectedDonor.donor_phc_name,
        to_phc_id: alert.phc_id,
        to_phc_name: alert.facility_name,
        item_id: alert.item_id,
        item_name: alert.item_name,
        unit: alert.unit,
        quantity: Number(customQuantity) || selectedDonor.transferable_quantity,
        batch_number: selectedDonor.batch_number,
        expiry_date: selectedDonor.expiry_date,
        reason: justificationReason.trim() || 'Urgent shortage mitigation',
      };

      await onProposalApproved(proposalPayload);
    } catch (err) {
      setActionError(err.message || 'Failed to submit and authorize transfer proposal.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleReject = async () => {
    if (!rejectReason.trim()) {
      setRejectError('A clear plain-language rejection reason is mandatory.');
      return;
    }

    setSubmitting(true);
    setRejectError('');

    try {
      // Create a rejected proposal record for audit trail
      const rejectionPayload = {
        alert_id: alert.alert_id,
        from_phc_id: selectedDonor ? selectedDonor.donor_phc_id : 'NO-DONOR',
        from_phc_name: selectedDonor ? selectedDonor.donor_phc_name : 'No Safe Candidate',
        to_phc_id: alert.phc_id,
        to_phc_name: alert.facility_name,
        item_id: alert.item_id,
        item_name: alert.item_name,
        unit: alert.unit,
        quantity: 0,
        reason: rejectReason.trim(),
        is_rejection: true,
      };

      await onProposalApproved(rejectionPayload);
      setRejectModalOpen(false);
    } catch (err) {
      setRejectError(err.message || 'Failed to submit rejection.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleEscalate = async () => {
    setSubmitting(true);
    setActionError(null);
    try {
      await onEscalateReplenishment({
        alert_id: alert.alert_id,
        item_name: alert.item_name,
        facility_name: alert.facility_name,
        phc_id: alert.phc_id,
        required_quantity: alert.reserve_stock * 2,
      });
      setEscalatedSuccess(true);
    } catch (err) {
      setActionError(err.message || 'Failed to escalate emergency replenishment.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 w-full pb-16">
      {/* Breadcrumb / Top Navigation */}
      <div className="flex items-center justify-between">
        <button
          onClick={onBack}
          className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-neutral-600 hover:text-black transition-colors cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>&larr; Back to Command Center</span>
        </button>

        <div className="flex items-center gap-2">
          <span className="text-[10px] text-neutral-400 uppercase font-mono">User Clearance:</span>
          <span className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded font-mono ${
            user?.role === 'admin'
              ? 'bg-indigo-50 text-indigo-700 border border-indigo-200'
              : user?.role === 'manager'
              ? 'bg-blue-50 text-blue-700 border border-blue-200'
              : 'bg-slate-100 text-slate-600 border border-slate-200'
          }`}>
            {user?.role || 'viewer'} ({user?.username || 'Guest'})
          </span>
        </div>
      </div>

      {/* Header Card */}
      <div className="bg-white p-6 rounded border border-neutral-200 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <SeverityBadge severity={alert.severity} />
            {alert.is_stale_data && <StaleDataBadge lastVerifiedAt={alert.last_verified_at} />}
            {alert.is_insufficient_history && <InsufficientHistoryBadge />}
            {alert.data_source === 'synthetic' && <SyntheticDemoBadge />}
            <DataSourceBadge source={alert.data_source} />
            <span className="text-xs font-mono text-neutral-500">
              ALERT_ID: {alert.alert_id}
            </span>
          </div>

          <h1 className="text-2xl font-black uppercase tracking-tight text-neutral-900">
            {alert.item_name}
            <span className="text-base font-normal text-neutral-500 ml-2">
              ({alert.dosage_form || 'Formulation'})
            </span>
          </h1>

          <div className="flex flex-wrap items-center gap-3 text-xs text-neutral-600 mt-1 font-mono">
            <span className="font-bold text-neutral-900">{alert.facility_name}</span>
            <span>&bull;</span>
            <span>{alert.phc_id}</span>
            <span>&bull;</span>
            <span>{alert.block}</span>
            <span>&bull;</span>
            <span>{alert.district}</span>
          </div>
        </div>

        <div className="flex items-center gap-4 border-t md:border-t-0 md:border-l border-neutral-200 pt-4 md:pt-0 md:pl-6 shrink-0">
          <div className="text-right">
            <div className="text-[10px] font-bold uppercase tracking-wider text-neutral-400">
              Stockout ETA
            </div>
            <div className={`text-xl font-black font-mono ${
              alert.severity === 'critical' ? 'text-red-600' : 'text-amber-600'
            }`}>
              {alert.hours_until_stockout !== undefined ? `${alert.hours_until_stockout} Hours` : 'Imminent'}
            </div>
            <div className="text-[10px] text-neutral-500 font-mono">
              {new Date(alert.projected_stockout_at).toLocaleString()}
            </div>
          </div>
        </div>
      </div>

      {/* Evidence Summary Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded border border-neutral-200 shadow-sm">
          <div className="text-[10px] font-bold uppercase tracking-wider text-neutral-500">
            Current Usable Stock
          </div>
          <div className="text-2xl font-black font-mono text-neutral-900 mt-1">
            {alert.usable_stock} <span className="text-xs font-normal text-neutral-500">{alert.unit}</span>
          </div>
          <div className="text-[10px] text-neutral-400 mt-1">
            Unexpired physical count
          </div>
        </div>

        <div className="bg-white p-4 rounded border border-neutral-200 shadow-sm border-l-4 border-l-amber-500">
          <div className="text-[10px] font-bold uppercase tracking-wider text-amber-700">
            Mandated Safety Reserve
          </div>
          <div className="text-2xl font-black font-mono text-neutral-900 mt-1">
            {alert.reserve_stock} <span className="text-xs font-normal text-neutral-500">{alert.unit}</span>
          </div>
          <div className="text-[10px] text-amber-600 font-bold mt-1">
            Breached {alert.usable_stock < alert.reserve_stock ? `(Deficit: -${alert.reserve_stock - alert.usable_stock})` : ''}
          </div>
        </div>

        <div className="bg-white p-4 rounded border border-neutral-200 shadow-sm">
          <div className="text-[10px] font-bold uppercase tracking-wider text-neutral-500">
            Daily Demand Rate
          </div>
          <div className="text-2xl font-black font-mono text-neutral-900 mt-1">
            {alert.avg_daily_consumption} <span className="text-xs font-normal text-neutral-500">{alert.unit}/day</span>
          </div>
          <div className="text-[10px] text-neutral-400 mt-1">
            Rolling daily burn velocity
          </div>
        </div>

        <div className="bg-white p-4 rounded border border-neutral-200 shadow-sm">
          <div className="text-[10px] font-bold uppercase tracking-wider text-neutral-500">
            Routine Resupply Date
          </div>
          <div className="text-sm font-bold text-neutral-900 mt-2 truncate">
            {alert.next_delivery_date
              ? new Date(alert.next_delivery_date).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
              : 'None Scheduled'}
          </div>
          <div className="text-[10px] text-neutral-500 mt-1 truncate">
            {alert.delivery_assumptions || 'Routine warehouse replenishment'}
          </div>
        </div>
      </div>

      {/* Plain-Language Clinical & Operational Evidence Card */}
      <div className="bg-amber-50/70 border-l-4 border-amber-500 p-5 rounded-r shadow-sm">
        <div className="flex items-start gap-3">
          <Info className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <h3 className="text-xs font-bold uppercase tracking-wider text-amber-900">
              Plain-Language Clinical Shortage Reason
            </h3>
            <p className="text-xs text-amber-950 leading-relaxed font-sans">
              {alert.plain_language_reason}
            </p>
            <div className="flex flex-wrap items-center gap-4 pt-2 text-[10px] font-mono text-amber-800">
              <span><strong>Forecast Engine:</strong> {alert.forecast_method}</span>
              <span>&bull;</span>
              <span><strong>Horizon Window:</strong> {alert.forecast_horizon_days} Days</span>
              <span>&bull;</span>
              <span><strong>Last Ingestion:</strong> {alert.last_verified_at ? new Date(alert.last_verified_at).toLocaleString() : 'N/A'}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Projected Stock Curve Chart */}
      {alert.stock_curve && alert.stock_curve.length > 0 && (
        <div className="bg-white p-6 rounded border border-neutral-200 shadow-sm flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-900">
                Projected Stock Trajectory vs Safety Reserve Threshold
              </h3>
              <p className="text-[10px] text-neutral-500 uppercase tracking-wider mt-0.5 font-mono">
                Prophet central forecast with 80% confidence interval &amp; safety floor
              </p>
            </div>
            <div className="flex items-center gap-4 text-[10px] font-mono">
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-0.5 bg-neutral-900 inline-block"></span>
                <span>Expected Stock</span>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-0.5 bg-amber-500 inline-block"></span>
                <span>Safety Reserve ({alert.reserve_stock})</span>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-0.5 bg-red-500 inline-block"></span>
                <span>Stockout Line (0)</span>
              </span>
            </div>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={alert.stock_curve} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 10, fontFamily: 'monospace' }}
                  tickFormatter={(d) => new Date(d).toLocaleDateString(undefined, { month: 'numeric', day: 'numeric' })}
                />
                <YAxis tick={{ fontSize: 10, fontFamily: 'monospace' }} />
                <Tooltip
                  content={({ active, payload, label }) => {
                    if (active && payload && payload.length) {
                      const data = payload[0].payload;
                      return (
                        <div className="bg-[#111] text-white p-3 rounded shadow-xl text-xs font-mono">
                          <div className="font-bold text-neutral-300 mb-1">{label}</div>
                          <div className="text-white">Projected: <strong>{data.projected_stock} {alert.unit}</strong></div>
                          <div className="text-neutral-400 text-[10px]">Range: {data.lower_bound} – {data.upper_bound}</div>
                          <div className="text-amber-400 text-[10px] mt-1">Safety Floor: {data.safety_reserve}</div>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <ReferenceLine y={alert.reserve_stock} stroke="#f59e0b" strokeDasharray="4 4" strokeWidth={2} />
                <ReferenceLine y={0} stroke="#ef4444" strokeWidth={2} />
                <Area
                  type="monotone"
                  dataKey="projected_stock"
                  stroke="#111111"
                  strokeWidth={2.5}
                  fill="#111111"
                  fillOpacity={0.08}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Donor Candidates Section */}
      <div className="flex flex-col gap-4">
        <div className="flex items-end justify-between border-b-2 border-neutral-800 pb-2">
          <div>
            <h3 className="text-sm font-black uppercase tracking-[0.15em] text-neutral-900">
              Safe Donor Candidates (Server Authorized Allocation)
            </h3>
            <p className="text-[10px] text-neutral-500 uppercase tracking-wider font-mono">
              Evaluated strictly by backend inventory algorithm — Zero donor reserve compromise
            </p>
          </div>
          <span className="text-[10px] font-mono text-neutral-500">
            {alert.donor_candidates ? `${alert.donor_candidates.length} Candidate(s) Evaluated` : '0 Evaluated'}
          </span>
        </div>

        {/* Clear No-Safe-Donor State */}
        {!hasSafeDonors ? (
          <div className="bg-red-50 border-2 border-red-500 p-8 rounded text-center flex flex-col items-center gap-4">
            <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center text-red-600">
              <ShieldAlert className="w-6 h-6" />
            </div>
            <div className="max-w-md">
              <h4 className="text-sm font-black uppercase tracking-wider text-red-900">
                No Safe Donor Facility Available in District
              </h4>
              <p className="text-xs text-red-700 mt-2 leading-relaxed">
                No neighboring Primary Health Centre possesses surplus above their protected safety reserve. An inter-facility transfer cannot be safely authorized without causing a secondary stockout.
              </p>
            </div>

            {escalatedSuccess ? (
              <div className="p-3 bg-emerald-100 border border-emerald-500 text-emerald-900 text-xs font-bold uppercase rounded flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                Emergency Replenishment Escalated to State Medical Depot
              </div>
            ) : (
              <button
                onClick={handleEscalate}
                disabled={submitting}
                className="flex items-center gap-2 px-6 py-3 bg-red-600 hover:bg-red-700 text-white font-bold text-xs uppercase tracking-wider rounded transition-all cursor-pointer shadow-md disabled:opacity-50"
              >
                <Truck className="w-4 h-4" />
                <span>Escalate Emergency Replenishment to Central Depot</span>
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {alert.donor_candidates.map((donor) => {
              const isSelected = selectedDonorId === donor.donor_phc_id;
              return (
                <div
                  key={donor.donor_phc_id}
                  onClick={() => handleSelectDonor(donor)}
                  className={`bg-white rounded border p-5 flex flex-col justify-between transition-all duration-200 ${
                    donor.eligible
                      ? isSelected
                        ? 'border-2 border-[#111] shadow-lg ring-2 ring-black/5 cursor-pointer bg-neutral-50/50'
                        : 'border-neutral-200 hover:border-neutral-400 shadow-sm cursor-pointer'
                      : 'border-neutral-200 bg-neutral-50/80 opacity-75 cursor-not-allowed'
                  }`}
                >
                  <div className="space-y-3">
                    {/* Header Pill */}
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-mono font-bold text-neutral-500 bg-neutral-100 px-2 py-0.5 rounded">
                        {donor.donor_phc_id} &bull; {donor.block}
                      </span>
                      {donor.eligible ? (
                        <span className="inline-flex items-center gap-1 text-[9px] font-bold text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded uppercase tracking-wider">
                          <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                          Eligible Donor
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[9px] font-bold text-red-700 bg-red-100 px-2 py-0.5 rounded uppercase tracking-wider">
                          <XCircle className="w-3 h-3 text-red-600" />
                          Ineligible
                        </span>
                      )}
                    </div>

                    <div>
                      <h4 className="text-sm font-black uppercase text-neutral-900 leading-snug">
                        {donor.donor_phc_name}
                      </h4>
                      <div className="flex items-center gap-3 text-[10px] font-mono text-neutral-500 mt-1">
                        <span>{donor.distance_km} km</span>
                        <span>&bull;</span>
                        <span>~{donor.estimated_transit_minutes} mins road transit</span>
                      </div>
                    </div>

                    {/* Quantity & Safety Cushion */}
                    <div className="p-3 bg-neutral-100/70 rounded space-y-1.5 font-mono text-xs">
                      <div className="flex justify-between">
                        <span className="text-neutral-500">Transferable Surplus:</span>
                        <strong className="text-neutral-900 font-black">
                          {donor.transferable_quantity} {alert.unit}
                        </strong>
                      </div>
                      <div className="flex justify-between text-[11px]">
                        <span className="text-neutral-500">Protected Reserve Retained:</span>
                        <span className="text-emerald-700 font-bold">
                          {donor.donor_reserve_after_transfer} {alert.unit} ({Math.round(donor.reserve_coverage_ratio_after * 100)}%)
                        </span>
                      </div>
                      <div className="flex justify-between text-[10px] text-neutral-400 pt-1 border-t border-neutral-200">
                        <span>Batch: {donor.batch_number}</span>
                        <span>Exp: {donor.expiry_date}</span>
                      </div>
                    </div>

                    {/* Ineligibility Reason Callout */}
                    {!donor.eligible && donor.ineligibility_reason && (
                      <div className="text-[10px] text-red-700 bg-red-50 p-2.5 rounded border border-red-200 leading-relaxed font-sans">
                        <strong>Rejection Reason:</strong> {donor.ineligibility_reason}
                      </div>
                    )}
                  </div>

                  {/* Radio / Selection Indicator */}
                  {donor.eligible && (
                    <div className="mt-4 pt-3 border-t border-neutral-100 flex items-center justify-between">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-neutral-600">
                        {isSelected ? '✓ Selected as Source' : 'Click to Select'}
                      </span>
                      <div className={`w-4 h-4 rounded-full border flex items-center justify-center ${
                        isSelected ? 'border-[#111] bg-[#111]' : 'border-neutral-300'
                      }`}>
                        {isSelected && <span className="w-1.5 h-1.5 rounded-full bg-white"></span>}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Action / Authorization Panel */}
      {hasSafeDonors && selectedDonor && (
        <div className="bg-white p-6 rounded border-2 border-neutral-800 shadow-xl flex flex-col gap-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-neutral-200 pb-4">
            <div>
              <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-neutral-400 font-bold">
                Coordinator Action Required
              </span>
              <h3 className="text-base font-black uppercase tracking-wider text-neutral-900 mt-0.5">
                Review &amp; Authorize Inter-PHC Stock Transfer
              </h3>
            </div>

            <div className="flex items-center gap-2 text-xs font-mono bg-neutral-100 px-3 py-1.5 rounded">
              <span className="text-neutral-500">FROM:</span>
              <strong className="text-neutral-900">{selectedDonor.donor_phc_name}</strong>
              <span className="text-neutral-400">&rarr;</span>
              <span className="text-neutral-500">TO:</span>
              <strong className="text-neutral-900">{alert.facility_name}</strong>
            </div>
          </div>

          {actionError && (
            <div className="p-3 bg-red-50 border border-red-500 text-red-700 text-xs rounded font-mono">
              {actionError}
            </div>
          )}

          {/* Transfer Proposal Fields */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-neutral-600 mb-1">
                Authorized Transfer Quantity ({alert.unit})
              </label>
              <input
                type="number"
                min="1"
                max={selectedDonor.transferable_quantity}
                value={customQuantity}
                onChange={(e) => setCustomQuantity(e.target.value)}
                className="w-full bg-neutral-50 border border-neutral-300 px-3 py-2 text-sm font-mono font-bold text-neutral-900 rounded focus:outline-none focus:border-[#111]"
              />
              <span className="text-[10px] text-neutral-500 font-mono mt-1 block">
                Max safe surplus: {selectedDonor.transferable_quantity} {alert.unit}
              </span>
            </div>

            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-neutral-600 mb-1">
                Clinical Justification / Operational Remarks
              </label>
              <input
                type="text"
                value={justificationReason}
                onChange={(e) => setJustificationReason(e.target.value)}
                placeholder="State clinical or seasonal reason..."
                className="w-full bg-neutral-50 border border-neutral-300 px-3 py-2 text-sm text-neutral-900 rounded focus:outline-none focus:border-[#111]"
              />
              <span className="text-[10px] text-neutral-500 font-mono mt-1 block">
                Logged in immutable audit ledger
              </span>
            </div>
          </div>

          {/* Permission Denied Callout for Viewers */}
          {!canApprove ? (
            <div className="p-4 bg-neutral-100 border border-neutral-300 rounded flex items-center gap-3">
              <Lock className="w-5 h-5 text-neutral-500 shrink-0" />
              <div className="text-xs text-neutral-700">
                <strong>Authorization Restricted:</strong> Your current session role is <code>viewer</code>. Approving or rejecting stock redistribution proposals requires <code>admin</code> or <code>manager</code> credentials.
              </div>
            </div>
          ) : (
            <div className="flex flex-col sm:flex-row items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setRejectModalOpen(true)}
                disabled={submitting}
                className="w-full sm:w-auto px-5 py-3 border border-red-300 text-red-700 hover:bg-red-50 text-xs font-bold uppercase tracking-wider rounded transition-colors cursor-pointer disabled:opacity-50"
              >
                Reject Proposal
              </button>

              <button
                type="button"
                onClick={handleApprove}
                disabled={submitting}
                className="w-full sm:w-auto flex items-center justify-center gap-2 px-8 py-3 bg-[#111] hover:bg-black text-white text-xs font-black uppercase tracking-[0.15em] rounded transition-all cursor-pointer shadow-lg disabled:opacity-50"
              >
                {submitting ? (
                  <span>Transmitting Proposal...</span>
                ) : (
                  <>
                    <ShieldCheck className="w-4 h-4 text-emerald-400" />
                    <span>Authorize &amp; Approve Transfer</span>
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Rejection Modal (Mandatory Reason per Contract) */}
      {rejectModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
          <div className="bg-white rounded border-2 border-neutral-900 w-full max-w-lg p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="text-sm font-black uppercase tracking-wider text-red-700 flex items-center gap-2">
                <XCircle className="w-4 h-4 text-red-600" />
                Reject Stock Redistribution Proposal
              </h3>
              <button
                onClick={() => setRejectModalOpen(false)}
                className="text-neutral-400 hover:text-black font-bold text-sm cursor-pointer"
              >
                &times;
              </button>
            </div>

            <p className="text-xs text-neutral-600">
              Per the Smart Health Sentinel protocol, rejecting a proposed transfer requires an explicit reason recorded in the district audit timeline.
            </p>

            {rejectError && (
              <div className="p-2.5 bg-red-50 text-red-700 text-xs rounded border border-red-200">
                {rejectError}
              </div>
            )}

            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-neutral-600 mb-1">
                Rejection Reason (Required)
              </label>
              <textarea
                rows={3}
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="e.g. Donor facility holds planned pediatric immunization camp; cold chain vehicle unavailable..."
                className="w-full p-2.5 text-xs bg-neutral-50 border border-neutral-300 rounded focus:outline-none focus:border-red-600"
              />
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => setRejectModalOpen(false)}
                className="px-4 py-2 text-xs font-bold uppercase text-neutral-600 hover:text-black cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleReject}
                disabled={submitting || !rejectReason.trim()}
                className="px-5 py-2 bg-red-600 hover:bg-red-700 text-white text-xs font-bold uppercase tracking-wider rounded transition-colors cursor-pointer disabled:opacity-50"
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
