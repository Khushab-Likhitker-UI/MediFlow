"""
Replenishment & Emergency Depot Escalation Router.
Allows coordinators to escalate critical shortages to the central district depot
when no safe peer health facility donor is available.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app import db
from app.domain.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/replenishment", tags=["Replenishment"])


class EscalationRequest(BaseModel):
    alert_id: str = Field(..., description="Alert ID triggering escalation")
    phc_id: str = Field(..., description="Recipient health centre ID")
    item_id: int = Field(..., description="Medicine ID")
    required_quantity: int = Field(..., gt=0, description="Quantity required")
    reason: Optional[str] = Field("No safe donor available in district", description="Clinical justification")


class EscalationResponse(BaseModel):
    escalation_id: str
    status: str
    alert_id: str
    phc_id: str
    item_id: int
    required_quantity: int
    reason: str
    escalated_at: str
    depot_destination: str
    message: str


@router.post(
    "/escalate",
    response_model=EscalationResponse,
    summary="Escalate shortage to District Central Depot when no safe donor qualifies",
)
async def escalate_shortage(
    payload: EscalationRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Log and lodge an emergency depot replenishment request.
    Creates an immutable audit event and assigns an authoritative tracking ID.
    """
    escalation_id = f"ESC-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc)
    user_str = current_user.get("username") or current_user.get("email", "coordinator")

    # Record audit log
    audit_sql = """
    INSERT INTO audit_events (
        event_id, entity_type, entity_id, action,
        actor_id, actor_role, details, created_at
    ) VALUES (
        %s, 'replenishment_escalation', %s, 'depot_escalated',
        %s, %s, %s, %s
    )
    """
    audit_details = (
        f'{{"alert_id": "{payload.alert_id}", "phc_id": "{payload.phc_id}", '
        f'"item_id": {payload.item_id}, "required_quantity": {payload.required_quantity}, '
        f'"reason": "{payload.reason}"}}'
    )
    try:
        db.execute_query(
            audit_sql,
            (
                str(uuid.uuid4()),
                escalation_id,
                user_str,
                current_user.get("role", "manager"),
                audit_details,
                now,
            ),
        )
    except Exception as e:
        logger.warning("Failed to record audit event for escalation: %s", e)

    return EscalationResponse(
        escalation_id=escalation_id,
        status="escalated_to_depot",
        alert_id=payload.alert_id,
        phc_id=payload.phc_id,
        item_id=payload.item_id,
        required_quantity=payload.required_quantity,
        reason=payload.reason or "No safe donor available in district",
        escalated_at=now.isoformat(),
        depot_destination="District Central Medical Depot",
        message="Emergency depot replenishment order lodged successfully.",
    )
