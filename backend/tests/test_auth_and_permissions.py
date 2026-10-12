"""
Unit tests for authentication, JWT signing, role checking, and district authorization.
"""

from datetime import timedelta
import pytest
from fastapi import HTTPException

from app.domain.auth import (
    create_access_token,
    decode_access_token,
    require_roles,
    verify_district_access,
)


def test_token_creation_and_decoding():
    """Verify standard JWT creation and successful claim retrieval."""
    token = create_access_token(
        user_id=42,
        username="officer_raj",
        email="raj@smarthealth.local",
        role="manager",
        district="Central District",
    )

    claims = decode_access_token(token)
    assert claims["user_id"] == 42
    assert claims["username"] == "officer_raj"
    assert claims["role"] == "manager"
    assert claims["district"] == "Central District"
    assert "exp" in claims
    assert "iat" in claims


def test_expired_token_rejected():
    """Expired JWT must raise 401 Unauthorized."""
    # Token expired 10 minutes ago
    expired_token = create_access_token(
        user_id=1,
        username="admin",
        email="admin@smarthealth.local",
        role="admin",
        expires_delta=timedelta(minutes=-10),
    )

    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(expired_token)
    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


def test_tampered_token_rejected():
    """Token with invalid signature or corrupted payload must raise 401 Unauthorized."""
    token = create_access_token(
        user_id=1,
        username="admin",
        email="admin@smarthealth.local",
        role="admin",
    )
    tampered_token = token[:-5] + "XXXXX"

    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(tampered_token)
    assert exc_info.value.status_code == 401


def test_role_checker_enforces_whitelist():
    """Users lacking required roles must receive 403 Forbidden."""
    checker = require_roles(["admin", "manager"])

    admin_user = {"user_id": 1, "role": "admin"}
    manager_user = {"user_id": 2, "role": "manager"}
    viewer_user = {"user_id": 3, "role": "viewer"}

    # Allowed roles pass
    assert checker(admin_user) == admin_user
    assert checker(manager_user) == manager_user

    # Forbidden role raises 403
    with pytest.raises(HTTPException) as exc_info:
        checker(viewer_user)
    assert exc_info.value.status_code == 403


def test_district_scope_authority():
    """Managers can only mutate operations in their own assigned district."""
    admin = {"role": "admin", "district": None}
    north_manager = {"role": "manager", "district": "North District"}
    viewer = {"role": "viewer", "district": "North District"}

    # Admin can access any district
    verify_district_access(admin, "South District")
    verify_district_access(admin, "North District")

    # Manager can access own district
    verify_district_access(north_manager, "North District")
    verify_district_access(north_manager, "north district")  # Case insensitive

    # Manager cannot access other district
    with pytest.raises(HTTPException) as exc_info:
        verify_district_access(north_manager, "South District")
    assert exc_info.value.status_code == 403
    assert "restricted" in exc_info.value.detail.lower()

    # Viewer has no mutation authority
    with pytest.raises(HTTPException) as exc_info:
        verify_district_access(viewer, "North District")
    assert exc_info.value.status_code == 403
