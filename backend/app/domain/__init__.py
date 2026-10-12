"""
Smart Health Sentinel Domain Package.
Contains pure, deterministic business logic for inventory, projections,
safe donor selection, transfer state machine, alerts, and authentication.
"""

from app.domain.models import (
    TransferState,
    AlertSeverity,
    AlertType,
    InventoryBatch,
    UsableStockResult,
    StockProjectionResult,
    ProjectionDailyPoint,
    DonorCandidate,
    DonorFacilityContext,
    ProposalResult,
    AuditRecord,
)
from app.domain.inventory import (
    calculate_usable_stock,
    validate_canonical_unit,
    are_units_compatible,
    are_formulations_compatible,
    normalize_unit,
    CANONICAL_UNITS,
    CANONICAL_DOSAGE_FORMS,
)
from app.domain.projection import project_stock
from app.domain.donor import evaluate_donor_candidates, haversine_distance
from app.domain.transfer import (
    validate_transition,
    VALID_TRANSITIONS,
    TransferDomainError,
    InvalidStateTransitionError,
    InsufficientStockError,
    IdempotencyConflictError,
)
from app.domain.alerts import generate_inventory_alerts
from app.domain.auth import (
    create_access_token,
    decode_access_token,
    get_current_user,
    require_roles,
    verify_district_access,
)

__all__ = [
    "TransferState",
    "AlertSeverity",
    "AlertType",
    "InventoryBatch",
    "UsableStockResult",
    "StockProjectionResult",
    "ProjectionDailyPoint",
    "DonorCandidate",
    "DonorFacilityContext",
    "ProposalResult",
    "AuditRecord",
    "calculate_usable_stock",
    "validate_canonical_unit",
    "are_units_compatible",
    "are_formulations_compatible",
    "normalize_unit",
    "CANONICAL_UNITS",
    "CANONICAL_DOSAGE_FORMS",
    "project_stock",
    "evaluate_donor_candidates",
    "haversine_distance",
    "validate_transition",
    "VALID_TRANSITIONS",
    "TransferDomainError",
    "InvalidStateTransitionError",
    "InsufficientStockError",
    "IdempotencyConflictError",
    "generate_inventory_alerts",
    "create_access_token",
    "decode_access_token",
    "get_current_user",
    "require_roles",
    "verify_district_access",
]
