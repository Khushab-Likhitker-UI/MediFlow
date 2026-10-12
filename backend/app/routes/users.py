"""
User management routes.

Provides basic CRUD for system users (admins, managers, viewers).

Security:
- Passwords are hashed with bcrypt via passlib before storage.
- Password hashes are **never** returned in any API response.
- Duplicate emails are caught via PostgreSQL UNIQUE constraint.
"""

import logging

from fastapi import APIRouter, HTTPException, Depends
from passlib.context import CryptContext

from app.models.schemas import User, UserCreate, UserLogin
from app import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["Users"])

import bcrypt
_orig_hashpw = bcrypt.hashpw
bcrypt.hashpw = lambda s, salt: _orig_hashpw(s[:72], salt) if len(s) > 72 else _orig_hashpw(s, salt)
if not hasattr(bcrypt, "__about__"):
    bcrypt.__about__ = type("About", (), {"__version__": getattr(bcrypt, "__version__", "4.0.0")})()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(password)


from app.domain.auth import create_access_token, get_current_user
from app.core.config import settings

@router.post("/login", summary="Verify user credentials and issue signed JWT")
async def login_user(login_in: UserLogin):
    """Verify user login against the users table. Returns user details & signed JWT token."""
    try:
        query = """
        SELECT id, username, email, role, password_hash, is_active
        FROM users
        WHERE LOWER(email) = LOWER(%s) OR LOWER(username) = LOWER(%s)
        """
        user = db.fetch_one(query, (login_in.email.strip(), login_in.email.strip()))
    except Exception as e:
        logger.error("Failed to query users for login: %s", e)
        raise HTTPException(status_code=500, detail="Database error during login")

    if not user or not user.get("is_active"):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    try:
        if not pwd_context.verify(login_in.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")
    except Exception as e:
        logger.warning("Password verify failed: %s", e)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Generate cryptographic JWT access token
    token = create_access_token(
        user_id=user["id"],
        username=user["username"],
        email=user["email"],
        role=user["role"],
    )

    return {
        "id": user["id"],
        "user_id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
        "token": token,
        "access_token": token,
        "token_type": "bearer",
        "expires_in_minutes": settings.jwt_access_token_expire_minutes,
    }


@router.get("/me", summary="Get current authenticated user profile")
async def get_current_user_profile(current_user: dict = Depends(get_current_user)):
    """Return the profile and claims of the currently authenticated JWT bearer."""
    return current_user


@router.get("/", response_model=list[User], summary="List all users")
async def list_users():
    """Return all users.  Password hashes are never included."""
    try:
        query = "SELECT id, username, email, role, is_active FROM users ORDER BY id"
        return db.fetch_all(query)
    except Exception as e:
        logger.error("Failed to list users: %s", e)
        raise HTTPException(status_code=500, detail="Failed to retrieve users")


@router.get("/{user_id}", response_model=User, summary="Get user by ID")
async def get_user(user_id: int):
    """Fetch a single user by ID.  Password hash is never returned."""
    try:
        query = "SELECT id, username, email, role, is_active FROM users WHERE id = %s"
        user = db.fetch_one(query, (user_id,))
    except Exception as e:
        logger.error("Failed to fetch user %d: %s", user_id, e)
        raise HTTPException(status_code=500, detail="Failed to retrieve user")

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/", response_model=User, status_code=201, summary="Register a new user")
async def create_user(user_in: UserCreate):
    """Register a new user.

    - Hashes the password with bcrypt before INSERT.
    - Returns 400 if email is already registered.
    - Never returns the password hash in the response.
    """
    hashed_password = get_password_hash(user_in.password)
    query = """
    INSERT INTO users (username, email, role, password_hash)
    VALUES (%s, %s, %s, %s)
    RETURNING id, username, email, role, is_active
    """
    try:
        user = db.fetch_one(
            query,
            (user_in.username, user_in.email, user_in.role, hashed_password),
        )
        return user
    except Exception as e:
        error_msg = str(e).lower()
        if "unique constraint" in error_msg or "duplicate key" in error_msg:
            logger.warning("Duplicate user registration attempt: %s", user_in.email)
            raise HTTPException(status_code=400, detail="Email already registered")
        logger.error("Failed to create user: %s", e)
        raise HTTPException(status_code=500, detail="Failed to create user")


@router.delete("/{user_id}", status_code=204, summary="Delete a user")
async def delete_user(user_id: int):
    """Delete a user by ID.  Returns 404 if user does not exist."""
    try:
        exist_query = "SELECT id FROM users WHERE id = %s"
        if not db.fetch_one(exist_query, (user_id,)):
            raise HTTPException(status_code=404, detail="User not found")

        delete_query = "DELETE FROM users WHERE id = %s"
        db.execute_query(delete_query, (user_id,))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete user %d: %s", user_id, e)
        raise HTTPException(status_code=500, detail="Failed to delete user")
