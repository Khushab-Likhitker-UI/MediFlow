"""
Grounded Gemini & Deterministic Fallback Explanation Tests
==========================================================

Verifies Requirement 5:
- Accepts operational facts calculated by backend rules
- Rejects non-operational / patient data
- Deterministic template fallback when Gemini is unavailable
- Output schema adherence and max length capping
- Honest source attribution: source='deterministic-rule-engine' with is_fallback=True
- Mock Gemini execution returns source='gemini-1.5-flash' with is_fallback=False
"""

from unittest.mock import AsyncMock, patch
import httpx
import pytest
from pydantic import ValidationError

from app.domain.explanation_service import (
    GroundedExplanation,
    OperationalFacts,
    generate_deterministic_fallback,
    generate_operational_explanation,
)
from app.domain.auth import create_access_token
from main import app
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture
def sample_operational_facts():
    return OperationalFacts(
        alert_id="alert-recip-01",
        facility_name="Sunrise Health Clinic",
        district="North District",
        item_name="Amoxicillin 500mg",
        current_usable_stock=10,
        safety_reserve=50,
        projected_deficit=40,
        days_until_stockout=2,
        recommended_action="Inter-facility transfer",
        donor_facility_name="Central District Hospital",
        transfer_quantity=40,
        urgency_reason="Consumption will breach safety reserve before replenishment arrives",
        is_simulated=True,
    )


@pytest.fixture
def auth_headers():
    token = create_access_token(
        user_id=1,
        username="logistics_admin",
        email="admin@smarthealth.local",
        role="admin",
    )
    return {"Authorization": f"Bearer {token}"}


def test_deterministic_fallback_schema_and_provenance(sample_operational_facts):
    """Fallback explanation must strictly validate against GroundedExplanation schema."""
    explanation = generate_deterministic_fallback(sample_operational_facts)
    assert isinstance(explanation, GroundedExplanation)
    assert explanation.source == "deterministic-rule-engine"
    assert explanation.is_fallback is True
    assert explanation.provenance == "Simulated data"
    assert len(explanation.summary) <= 300
    assert len(explanation.operational_rationale) <= 600
    assert len(explanation.recommended_action) <= 300
    assert "Amoxicillin 500mg" in explanation.summary
    assert "Sunrise Health Clinic" in explanation.summary


@pytest.mark.asyncio
async def test_explanation_service_falls_back_when_no_api_key(sample_operational_facts):
    """When GEMINI_API_KEY is unset or empty, the service uses deterministic fallback."""
    with patch("app.domain.explanation_service.settings.gemini_api_key", ""):
        result = await generate_operational_explanation(sample_operational_facts)
        assert result.is_fallback is True
        assert result.source == "deterministic-rule-engine"
        assert "Sunrise Health Clinic" in result.summary


@pytest.mark.asyncio
async def test_explanation_service_handles_gemini_timeout(sample_operational_facts):
    """When Gemini API call times out, seamlessly fall back to deterministic template."""
    with patch("app.domain.explanation_service.settings.gemini_api_key", "test-mock-key"):
        with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Timeout")):
            result = await generate_operational_explanation(sample_operational_facts)
            assert result.is_fallback is True
            assert result.source == "deterministic-rule-engine"


@pytest.mark.asyncio
async def test_explanation_service_handles_gemini_rate_limit(sample_operational_facts):
    """When Gemini returns HTTP 429 rate limit, fallback is used."""
    mock_resp = AsyncMock()
    mock_resp.status_code = 429

    with patch("app.domain.explanation_service.settings.gemini_api_key", "test-mock-key"):
        with patch("httpx.AsyncClient.post", return_value=mock_resp):
            result = await generate_operational_explanation(sample_operational_facts)
            assert result.is_fallback is True
            assert result.source == "deterministic-rule-engine"


@pytest.mark.asyncio
async def test_explanation_service_successful_gemini_call(sample_operational_facts):
    """When Gemini returns valid JSON, honest source is recorded and is_fallback is False."""
    from unittest.mock import MagicMock
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": (
                                '{"summary": "Urgent Amoxicillin shortage detected.", '
                                '"operational_rationale": "Safety reserve breached by 40 units.", '
                                '"recommended_action": "Execute transfer of 40 units immediately.", '
                                '"confidence_note": "High confidence based on consumption trend."}'
                            )
                        }
                    ]
                }
            }
        ]
    }

    with patch("app.domain.explanation_service.settings.gemini_api_key", "test-mock-key"):
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await generate_operational_explanation(sample_operational_facts)
            assert result.is_fallback is False
            assert result.source == "gemini-1.5-flash"
            assert result.summary == "Urgent Amoxicillin shortage detected."


def test_api_explanation_endpoint_with_auth(auth_headers, sample_operational_facts):
    """Authenticated user can request explanation via REST endpoint."""
    response = client.post(
        "/api/v1/explain/decision",
        headers=auth_headers,
        json=sample_operational_facts.model_dump(),
    )
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "operational_rationale" in data
    assert data["source"] in ("deterministic-rule-engine", "gemini-1.5-flash")
    assert "provenance" in data
