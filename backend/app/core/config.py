"""
Application-wide configuration and settings.

Reads from environment variables (loaded via ``python-dotenv``) with
safe defaults suitable for local development.
"""

import os

from dotenv import load_dotenv
from pydantic import BaseModel

# Load .env from the backend root directory
load_dotenv()


def _parse_cors_origins() -> list[str]:
    """Parse a comma-separated CORS_ORIGINS env var into a list."""
    raw = os.getenv("CORS_ORIGINS")
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    # Fallback: allow common local dev servers and production frontend deployments
    return [
        "https://smart-health-gray-theta.vercel.app",
        "https://smarthealth-production.up.railway.app",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ]


class Settings(BaseModel):
    """Global application settings loaded from environment or defaults."""

    app_name: str = os.getenv("APP_NAME", "Healthcare Supply Chain API")
    app_version: str = os.getenv("APP_VERSION", "0.1.0")
    environment: str = os.getenv("ENVIRONMENT", "development").lower()
    debug: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

    # CORS — allow the configured origins
    cors_origins: list[str] = _parse_cors_origins()

    # Database connection URL (No hardcoded credentials; defaults to empty)
    database_url: str = os.getenv("DATABASE_URL", "").strip()

    # JWT Authentication
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "smarthealth-sentinel-dev-secret-key-32chars-min")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_access_token_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))

    # Supply Chain Policy Defaults
    planning_horizon_days: int = int(os.getenv("PLANNING_HORIZON_DAYS", "30"))
    default_safety_reserve_days: int = int(os.getenv("SAFETY_RESERVE_DAYS", "7"))

    # Optional AI Explainer configuration (modular, non-authoritative)
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")

    def model_post_init(self, __context):
        # Production & Staging safeguard: fail fast if critical secrets are missing or defaults
        if self.environment in ("production", "staging"):
            if not self.database_url:
                raise RuntimeError(
                    f"Security / Startup Error: DATABASE_URL must be configured when ENVIRONMENT={self.environment}."
                )
            if self.jwt_secret_key == "smarthealth-sentinel-dev-secret-key-32chars-min":
                raise RuntimeError(
                    f"Security / Startup Error: JWT_SECRET_KEY must be overridden with a strong secret in {self.environment}."
                )


settings = Settings()
