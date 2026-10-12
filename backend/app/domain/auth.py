"""
Cryptographic authentication and role-based authorization services.
Uses PyJWT with HS256 for signed token issuance, claim verification, and scope checks.
"""

from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

security = HTTPBearer(auto_error=False)


def create_access_token(
    user_id: int,
    username: str,
    email: str,
    role: str,
    district: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a signed JWT access token with standard claims."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.jwt_access_token_expire_minutes
        )

    payload = {
        "sub": str(user_id),
        "user_id": user_id,
        "username": username,
        "email": email,
        "role": role,
        "district": district,
        "exp": int(expire.timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict:
    """Decode and validate a signed JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> dict:
    """
    FastAPI dependency to extract and authenticate the current user.
    Permits unauthenticated development fallback ONLY when explicit dev header
    or debug is configured, otherwise strictly requires valid JWT.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header with Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    # Support backward-compatibility with legacy mock token during phased rollout if in debug
    if token.startswith("jwt-supabase-") and settings.debug:
        parts = token.split("-")
        role = parts[-1] if len(parts) >= 4 else "viewer"
        uid = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else 1
        return {
            "user_id": uid,
            "username": f"user_{uid}",
            "email": f"user_{uid}@smarthealth.local",
            "role": role,
            "district": None,
        }

    return decode_access_token(token)


def require_roles(allowed_roles: list[str]):
    """FastAPI dependency factory enforcing role-based permissions."""
    def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
        user_role = current_user.get("role")
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Access forbidden: User with role '{user_role}' lacks "
                    f"required permissions (needs one of {allowed_roles})."
                ),
            )
        return current_user

    return role_checker


def verify_district_access(user: dict, target_district: Optional[str]) -> None:
    """
    Verify if a user has authority to approve or mutate actions in a given district.
    - admin: global authority across all districts.
    - manager: authority within their assigned district only.
    - viewer: no mutation authority.
    """
    role = user.get("role")
    if role == "admin":
        return

    if role == "manager":
        user_district = user.get("district")
        if user_district and target_district and user_district.lower() != target_district.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Manager authority is restricted to district '{user_district}'. "
                    f"Target district is '{target_district}'."
                ),
            )
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Role '{role}' is not authorized to perform operations in district '{target_district}'.",
    )
