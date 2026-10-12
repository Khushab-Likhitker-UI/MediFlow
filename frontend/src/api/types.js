/**
 * Smart Health Sentinel — Frontend API Contract Types
 * Mirrors the authoritative backend API Contract (docs/implementation/API_CONTRACT.md)
 * and Domain Model (docs/implementation/DOMAIN_MODEL.md).
 */

/**
 * @typedef {'critical' | 'warning' | 'info'} AlertSeverity
 */

/**
 * @typedef {'open' | 'investigating' | 'proposal_pending' | 'resolved'} AlertStatus
 */

/**
 * @typedef {'database' | 'synthetic' | 'sensor'} DataSourceProvenance
 */

/**
 * @typedef {'proposed' | 'approved' | 'dispatched' | 'received' | 'reconciled' | 'rejected' | 'cancelled' | 'exception'} TransferStatus
 */

/**
 * @typedef {'admin' | 'manager' | 'viewer'} UserRole
 */

/**
 * Stock projection point for forecast curves
 * @typedef {Object} StockCurvePoint
 * @property {string} date - ISO Date string YYYY-MM-DD
 * @property {number} projected_stock - Central expected stock level
 * @property {number} lower_bound - 80% confidence lower bound
 * @property {number} upper_bound - 80% confidence upper bound
 * @property {number} safety_reserve - Reserve threshold at this date
 */

/**
 * Candidate donor facility for stock redistribution
 * Authoritatively calculated by backend (NOT browser).
 * @typedef {Object} DonorCandidate
 * @property {string} donor_phc_id - Source PHC ID
 * @property {string} donor_phc_name - Source facility name
 * @property {string} block - Administrative block
 * @property {number} distance_km - Distance in kilometers
 * @property {number} estimated_transit_minutes - Transit time in minutes
 * @property {number} current_stock - Current stock at donor
 * @property {number} safety_reserve - Donor's safety reserve
 * @property {number} transferable_quantity - Surplus authorized for transfer
 * @property {number} donor_reserve_after_transfer - Remaining donor stock post-transfer
 * @property {number} reserve_coverage_ratio_after - Percentage of reserve retained (e.g. 1.6 = 160%)
 * @property {string} batch_number - Specific batch
 * @property {string} expiry_date - Batch expiration date (YYYY-MM-DD)
 * @property {boolean} eligible - Whether donor can safely fulfill transfer
 * @property {string} [ineligibility_reason] - Reason if ineligible
 */

/**
 * Ranked Shortage Alert
 * @typedef {Object} ShortageAlert
 * @property {string} alert_id - Unique computed alert ID
 * @property {number} rank - Priority rank (1 = highest urgency)
 * @property {string} phc_id - Primary Health Centre identifier
 * @property {string} facility_name - Name of health facility
 * @property {string} block - Administrative block / sub-district
 * @property {string} district - District name
 * @property {number} item_id - Medicine item ID
 * @property {string} item_name - Medicine name
 * @property {string} dosage_form - Formulation (tablet, vial, sachet, etc.)
 * @property {string} unit - Measurement unit (tablets, vials, etc.)
 * @property {AlertSeverity} severity - Critical, warning, or info
 * @property {AlertStatus} status - Open, investigating, proposal_pending, resolved
 * @property {number} usable_stock - Current unexpired usable stock
 * @property {number} reserve_stock - Prescribed safety reserve threshold
 * @property {number} avg_daily_consumption - Average daily burn rate
 * @property {string} projected_stockout_at - Projected time of zero stock (ISO 8601)
 * @property {number} hours_until_stockout - Hours remaining until stock reaches 0
 * @property {string} projected_reserve_breach_at - Time when reserve is breached (ISO 8601)
 * @property {string} last_verified_at - Timestamp of last verified inventory sync
 * @property {boolean} is_stale_data - True if last verification > 24h ago
 * @property {boolean} is_insufficient_history - True if history < minimum ML window
 * @property {DataSourceProvenance} data_source - Source data provenance label
 * @property {string} [next_delivery_date] - Scheduled routine delivery date
 * @property {string} [delivery_assumptions] - Delivery notes or routing constraints
 * @property {string} forecast_method - "Prophet", "Moving Average", "Synthetic Fallback"
 * @property {number} forecast_horizon_days - Number of forecast days
 * @property {string} plain_language_reason - Plain English explanation of the shortage
 * @property {StockCurvePoint[]} stock_curve - Projected stock trajectory points
 * @property {DonorCandidate[]} donor_candidates - Evaluated donor candidates
 */

/**
 * Transfer Audit Timeline Entry
 * @typedef {Object} TransferAuditEvent
 * @property {string} event_id - Event UUID
 * @property {TransferStatus} status - State transitioned to
 * @property {string} timestamp - ISO 8601 datetime
 * @property {string} actor_name - Officer / driver / system name
 * @property {UserRole|'system'|'courier'} actor_role - Role of actor
 * @property {string} note - Action description or rejection reason
 */

/**
 * Stock Transfer Record
 * @typedef {Object} TransferRecord
 * @property {string} transfer_id - Unique transfer UUID
 * @property {string} [alert_id] - Associated alert ID if generated from triage
 * @property {string} from_phc_id - Source PHC ID
 * @property {string} from_phc_name - Source facility name
 * @property {string} to_phc_id - Destination PHC ID
 * @property {string} to_phc_name - Destination facility name
 * @property {number} item_id - Medicine item ID
 * @property {string} item_name - Medicine name
 * @property {string} unit - Measurement unit
 * @property {number} proposed_quantity - Number of units approved to transfer
 * @property {number|null} actual_received_quantity - Units verified upon receipt
 * @property {string} batch_number - Batch identifier
 * @property {string} expiry_date - Batch expiry date
 * @property {TransferStatus} status - Lifecycle status
 * @property {string} reason - Justification for transfer
 * @property {string} created_at - ISO 8601 creation timestamp
 * @property {string} updated_at - ISO 8601 last update timestamp
 * @property {string} [approved_by] - Officer who approved
 * @property {string} [dispatched_by] - Officer or courier who dispatched
 * @property {string} [vehicle_id] - Vehicle / courier tracking ID
 * @property {string} [received_by] - Officer who confirmed physical receipt
 * @property {string} [rejection_reason] - Mandatory reason if rejected
 * @property {TransferAuditEvent[]} timeline - Full immutable audit timeline
 */

/**
 * Named Evaluation Run for Model Performance
 * @typedef {Object} EvaluationRun
 * @property {string} run_id - Unique evaluation run ID
 * @property {string} run_name - Human-readable run name
 * @property {string} date_executed - ISO date string
 * @property {string} model_version - Version of ML & allocation algorithms
 * @property {string} baseline_name - Reference baseline (e.g. "Q2 2026 Historic Log")
 * @property {string} data_source - "benchmark_database" | "simulated_fixture"
 * @property {boolean} is_simulated - True if development fixture
 * @property {Object} metrics - Quantitative metrics
 * @property {number} metrics.shortage_prevention_rate_pct - % of predicted stockouts prevented
 * @property {number} metrics.baseline_shortage_prevention_pct - Baseline %
 * @property {number} metrics.stockout_hours_avoided - Total stockout hours averted
 * @property {number} metrics.false_alarm_rate_pct - % false alarms
 * @property {number} metrics.baseline_false_alarm_pct - Baseline false alarm %
 * @property {number} metrics.mean_lead_time_hours - Average redistribution completion time
 * @property {number} metrics.baseline_lead_time_hours - Baseline lead time
 * @property {number} metrics.donor_retention_rate_pct - % donor reserves protected (must be 100%)
 */

export {};
