"""
Domain models and dataclasses for Smart Health Sentinel.
These structures represent the core business concepts, independent of HTTP/FastAPI.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional


class TransferState(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    DISPATCHED = "dispatched"
    RECEIVED = "received"
    RECONCILED = "reconciled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXCEPTION = "exception"


class AlertSeverity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class AlertType(str, Enum):
    CRITICAL_STOCK = "critical_stock"
    LOW_STOCK = "low_stock"
    EXPIRING_SOON = "expiring_soon"
    CONSUMPTION_ANOMALY = "consumption_anomaly"


@dataclass
class InventoryBatch:
    batch_number: str
    quantity: int
    expiry_date: date
    is_quarantined: bool = False
    is_damaged: bool = False


@dataclass
class UsableStockResult:
    facility_id: str
    item_id: int
    item_name: str
    unit: str
    total_physical_quantity: int
    expired_quantity: int
    reserved_quantity: int
    quarantined_quantity: int
    usable_quantity: int
    active_batches: list[InventoryBatch] = field(default_factory=list)


@dataclass
class ProjectionDailyPoint:
    date: str  # YYYY-MM-DD
    projected_demand: float
    inbound_replenishment: int
    ending_stock: float
    is_breached: bool
    is_stockout: bool


@dataclass
class StockProjectionResult:
    facility_id: str
    item_id: int
    item_name: str
    unit: str
    current_usable_stock: int
    safety_reserve: int
    planning_horizon_days: int
    days_of_supply: Optional[float]
    projected_reserve_breach_date: Optional[str]
    projected_stockout_date: Optional[str]
    severity: AlertSeverity
    reason: str
    history_quality: str  # "sufficient" | "insufficient_history" | "zero_history"
    data_source: str  # "database" | "synthetic"
    method: str  # "prophet" | "sma" | "deterministic_fallback"
    daily_curve: list[ProjectionDailyPoint] = field(default_factory=list)


@dataclass
class DonorFacilityContext:
    facility_id: str
    facility_name: str
    district: str
    latitude: float
    longitude: float
    batches: list[InventoryBatch]
    active_reservations: int = 0
    safety_reserve: int = 50
    projected_demand_over_horizon: int = 0


@dataclass
class DonorCandidate:
    facility_id: str
    facility_name: str
    district: str
    item_id: int
    item_name: str
    unit: str
    current_usable_stock: int
    protected_reserve: int
    projected_demand: int
    active_reservations: int
    donor_safe_surplus: int
    transferable_quantity: int
    eligible_batches: list[dict] = field(default_factory=list)
    distance_km: Optional[float] = None
    is_eligible: bool = False
    rejection_reason: Optional[str] = None
    rank: Optional[int] = None


@dataclass
class ProposalResult:
    recipient_facility_id: str
    recipient_facility_name: str
    item_id: int
    item_name: str
    unit: str
    recipient_deficit: int
    candidates: list[DonorCandidate]
    recommended_candidate: Optional[DonorCandidate]
    recommended_quantity: int
    has_safe_donor: bool
    escalation_action: Optional[str] = None


@dataclass
class AuditRecord:
    entity_type: str
    entity_id: str
    action: str
    actor_id: Optional[str]
    actor_role: Optional[str]
    details: dict
    timestamp: datetime = field(default_factory=datetime.utcnow)
