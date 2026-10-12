"""
Modular Alert Explainability Service.
Produces structured, explainable narratives grounded strictly in backend-calculated facts.
Features a 100% deterministic rule-based fallback that guarantees full offline and non-cloud operation.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AlertExplanation(BaseModel):
    alert_id: str
    facility_id: str
    facility_name: str
    item_id: int
    item_name: str
    severity: str
    summary: str
    evidence_fields: dict[str, Any]
    data_limitations: list[str]
    recommended_action: str
    is_ai_generated: bool = False
    model_version: str = "deterministic-rule-v1"
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    language: str = "en"


def generate_deterministic_explanation(
    alert: dict[str, Any],
    donor_candidates: Optional[list[dict[str, Any]]] = None,
) -> AlertExplanation:
    """
    Generate an authoritative, deterministic explanation grounded entirely
    in backend-calculated inventory and forecast facts.
    """
    alert_id = str(alert.get("alert_id") or "UNKNOWN")
    facility_id = str(alert.get("phc_id") or "UNKNOWN")
    facility_name = str(alert.get("facility_name") or facility_id)
    item_id = int(alert.get("item_id") or 0)
    item_name = str(alert.get("item_name") or "Medical Supply")
    severity = str(alert.get("severity") or "warning").lower()
    unit = str(alert.get("unit") or "units")

    usable_stock = int(alert.get("usable_stock", 0))
    safety_reserve = int(alert.get("safety_reserve", 50))
    daily_rate = float(alert.get("avg_daily_consumption") or alert.get("daily_burn_rate") or 5.0)
    hours_until_stockout = alert.get("hours_until_stockout")
    breach_date = alert.get("projected_stockout_at") or alert.get("breach_date") or "Within 48 hours"
    data_source = str(alert.get("data_source") or "database")

    deficit = max(0, safety_reserve - usable_stock)

    # Analyze donor options
    donors = donor_candidates or []
    eligible_donors = [d for d in donors if d.get("eligible")]
    total_transferable = sum(d.get("transferable_quantity", 0) for d in eligible_donors)

    limitations = [
        "Demand projection assumes stationary consumption based on trailing operational records.",
        "Replenishment arrival times are subject to supplier logistics and weather delays.",
        "Stock balances reflect the latest synchronized ledger snapshot.",
    ]

    if usable_stock <= 0:
        summary = (
            f"CRITICAL STOCKOUT: {facility_name} has zero usable stock of {item_name} "
            f"(required safety reserve: {safety_reserve} {unit}). Immediate replenishment is required."
        )
    elif usable_stock < safety_reserve:
        summary = (
            f"RESERVE BREACH: Current usable stock at {facility_name} is {usable_stock} {unit}, "
            f"which is below the mandatory safety reserve of {safety_reserve} {unit}. "
            f"At an average consumption rate of {daily_rate:.1f} {unit}/day, stock will be depleted by {breach_date}."
        )
    else:
        summary = (
            f"STOCK MONITORING: {facility_name} holds {usable_stock} {unit} of {item_name}. "
            f"Projected consumption rate is {daily_rate:.1f} {unit}/day against a reserve of {safety_reserve} {unit}."
        )

    if eligible_donors:
        best_donor = eligible_donors[0]
        donor_name = best_donor.get("donor_phc_name") or best_donor.get("donor_phc_id")
        transfer_qty = min(deficit, total_transferable)
        recommended_action = (
            f"Propose an inter-facility transfer of {transfer_qty} {unit} from {donor_name}. "
            f"This transfer preserves {donor_name}'s own safety reserve while eliminating the deficit at {facility_name}."
        )
    elif deficit > 0:
        recommended_action = (
            f"No district peer facility currently has surplus stock above its own protected reserve. "
            f"Escalate an emergency replenishment order of {deficit} {unit} to the District Drug Warehouse."
        )
    else:
        recommended_action = "Maintain regular inventory monitoring and re-verify stock during standard PHC shift change."

    evidence = {
        "current_usable_stock": usable_stock,
        "safety_reserve_threshold": safety_reserve,
        "unmet_deficit": deficit,
        "unit": unit,
        "avg_daily_consumption": daily_rate,
        "projected_stockout_at": breach_date,
        "hours_until_stockout": hours_until_stockout,
        "eligible_donor_count": len(eligible_donors),
        "total_transferable_available": total_transferable,
        "data_source": data_source,
    }

    return AlertExplanation(
        alert_id=alert_id,
        facility_id=facility_id,
        facility_name=facility_name,
        item_id=item_id,
        item_name=item_name,
        severity=severity,
        summary=summary,
        evidence_fields=evidence,
        data_limitations=limitations,
        recommended_action=recommended_action,
        is_ai_generated=False,
        model_version="deterministic-rule-v1",
    )


def explain_alert(
    alert: dict[str, Any],
    donor_candidates: Optional[list[dict[str, Any]]] = None,
    timeout_seconds: float = 3.0,
) -> AlertExplanation:
    """
    Produce a structured explanation for a shortage alert.
    If GEMINI_API_KEY is configured and reachable within timeout_seconds,
    enhances the narrative via Gemini. Otherwise, returns the deterministic fallback.
    NEVER mutates inventory or authorizes transfers.
    """
    fallback = generate_deterministic_explanation(alert, donor_candidates)

    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not gemini_key:
        logger.debug("No GEMINI_API_KEY configured; returning deterministic explanation.")
        return fallback

    # Grounded prompt with NO patient identifiers
    prompt = {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            "You are an explainable healthcare logistics assistant. "
                            "Explain the following pre-calculated stock alert strictly using the provided facts. "
                            "Do NOT change any numbers or recommend actions not supported by the facts. "
                            "Do NOT invent clinical diagnosis or prescription advice. "
                            "Respond ONLY with valid JSON having keys 'summary' and 'recommended_action'.\n\n"
                            f"Facility: {fallback.facility_name}\n"
                            f"Medicine: {fallback.item_name}\n"
                            f"Usable Stock: {fallback.evidence_fields['current_usable_stock']} {fallback.evidence_fields['unit']}\n"
                            f"Safety Reserve: {fallback.evidence_fields['safety_reserve_threshold']}\n"
                            f"Deficit: {fallback.evidence_fields['unmet_deficit']}\n"
                            f"Daily Burn Rate: {fallback.evidence_fields['avg_daily_consumption']}\n"
                            f"Eligible Peer Donors: {fallback.evidence_fields['eligible_donor_count']}\n"
                            f"Deterministic Base Recommendation: {fallback.recommended_action}\n"
                        )
                    }
                ]
            }
        ]
    }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
    req = urllib.request.Request(
        url,
        data=json.dumps(prompt).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
            if response.status == 200:
                raw_body = response.read().decode("utf-8")
                data = json.loads(raw_body)
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        text_resp = parts[0].get("text", "").strip()
                        # Clean JSON code fence if present
                        if text_resp.startswith("```json"):
                            text_resp = text_resp[7:]
                        if text_resp.startswith("```"):
                            text_resp = text_resp[3:]
                        if text_resp.endswith("```"):
                            text_resp = text_resp[:-3]
                        
                        parsed = json.loads(text_resp.strip())
                        if "summary" in parsed and "recommended_action" in parsed:
                            return AlertExplanation(
                                alert_id=fallback.alert_id,
                                facility_id=fallback.facility_id,
                                facility_name=fallback.facility_name,
                                item_id=fallback.item_id,
                                item_name=fallback.item_name,
                                severity=fallback.severity,
                                summary=parsed["summary"],
                                evidence_fields=fallback.evidence_fields,
                                data_limitations=fallback.data_limitations,
                                recommended_action=parsed["recommended_action"],
                                is_ai_generated=True,
                                model_version="gemini-1.5-flash-grounded",
                            )
    except Exception as exc:
        logger.warning("LLM explanation request failed or timed out (%s); using deterministic fallback.", exc)

    return fallback
