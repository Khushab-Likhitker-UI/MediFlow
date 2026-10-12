"""
Operational Explanation Routes (Grounded Gemini / Deterministic Fallback).
===========================================================================

Provides server-side operational rationales for supply chain alerts and
transfer decisions without exposing AI tokens to client browsers or PWAs.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.domain.auth import get_current_user
from app.domain.explanation_service import (
    GroundedExplanation,
    OperationalFacts,
    generate_operational_explanation,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/explain", tags=["Operational Explanations"])


@router.post(
    "/decision",
    response_model=GroundedExplanation,
    summary="Generate grounded operational rationale for alert or transfer recommendation",
    response_description="Structured explanation with provenance and fallback indicators",
)
async def explain_operational_decision(
    facts: OperationalFacts,
    current_user: dict = Depends(get_current_user),
):
    """
    Accepts an operational facts object calculated by backend rules and returns
    a concise, bounded explanation for logistics staff.
    
    If Gemini/Vertex AI is unavailable or unconfigured, returns a deterministic
    rule-derived explanation with `is_fallback=True` and `source='deterministic-rule-engine'`.
    """
    try:
        explanation = await generate_operational_explanation(facts)
        return explanation
    except Exception as e:
        logger.error("Error generating explanation: %s", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate explanation.",
        )
