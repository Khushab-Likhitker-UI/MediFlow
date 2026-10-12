"""
Deployment, Health Checks, Middleware, and Security Configuration Tests
========================================================================

Verifies Phase 3 operational security and deployment criteria:
- Lightweight health check probe (/api/v1/health and /health)
- X-Request-ID propagation and structured logging
- Safe secret handling: database URI missing error does not expose credentials
- Authentication rejection for protected endpoints
- CORS origin restriction
"""

from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from main import app

client = TestClient(app)


def test_api_v1_health_probe():
    """Verify lightweight /api/v1/health endpoint returns expected status without leaking secrets."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "service" in data
    assert "version" in data
    # Ensure sensitive fields are never in the health probe response
    assert "database_url" not in data
    assert "secret" not in data
    assert "credentials" not in data
    assert "host" not in data


def test_health_alias_probe():
    """Verify /health alias also returns healthy 200."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_x_request_id_middleware_generated():
    """Verify requests receive an injected X-Request-ID header."""
    response = client.get("/api/v1/health")
    assert "x-request-id" in response.headers
    assert len(response.headers["x-request-id"]) > 0


def test_x_request_id_middleware_propagated():
    """Verify client-supplied X-Request-ID is preserved and propagated."""
    custom_trace_id = "trace-sentinel-test-999"
    response = client.get("/api/v1/health", headers={"x-request-id": custom_trace_id})
    assert response.headers.get("x-request-id") == custom_trace_id


def test_protected_routes_reject_unauthenticated():
    """Verify protected endpoints reject requests lacking valid Bearer token."""
    response = client.post(
        "/api/v1/explain/decision",
        json={
            "facility_name": "Clinic A",
            "district": "North",
            "item_name": "Paracetamol",
            "current_usable_stock": 5,
            "safety_reserve": 20,
            "projected_deficit": 15,
            "recommended_action": "Transfer stock",
        },
    )
    assert response.status_code == 401
    assert "missing" in response.json()["detail"].lower() or "unauthorized" in response.json()["detail"].lower()


def test_missing_database_url_raises_clean_error():
    """Verify get_pool raises ValueError with clean guidance and no secret leakage when DATABASE_URL is unset."""
    from app import db
    with patch("os.getenv", return_value=""):
        # Reset cached pool
        original_pool = db._connection_pool
        try:
            db._connection_pool = None
            with pytest.raises(ValueError) as exc_info:
                db.get_pool()
            assert "DATABASE_URL environment variable is not configured" in str(exc_info.value)
        finally:
            db._connection_pool = original_pool


def test_cors_preflight_allows_configured_origin():
    """Verify preflight requests from configured origin are permitted."""
    allowed_origin = "https://smart-health-gray-theta.vercel.app"
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": allowed_origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") == allowed_origin
