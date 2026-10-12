"""
Healthcare Supply Chain Management API
=======================================

Entry point for the FastAPI application.
Run with:  uvicorn main:app --reload
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routes import (
    alerts,
    evaluations,
    explanations,
    facility,
    inventory,
    predictions,
    replenishment,
    stock_movements,
    transfers,
    users,
)
from app.routes.predictions import shortage_router

from app.db import close_pool
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


# ── Structured Logging & Request ID Middleware ──────────────────────────────

class SafeStructuredLoggingMiddleware(BaseHTTPMiddleware):
    """
    Operational visibility middleware:
    - Injects and propagates X-Request-ID for distributed trace correlation.
    - Emits structured operational log entries with latency and status code.
    - Explicitly safeguards privacy: NEVER logs request body, authorization
      headers, secrets, or patient identifiable information.
    """
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = req_id
        start_time = time.perf_counter()

        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        response.headers["x-request-id"] = req_id

        # Safe operational logging (no PHI, no credentials)
        logger.info(
            "request_completed method=%s path=%s status=%s duration_ms=%.2f request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            req_id,
        )
        return response


# ── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown lifecycle events.

    On shutdown the PostgreSQL connection pool is closed so every
    connection is returned cleanly.
    """
    logger.info(
        "Starting %s v%s (debug=%s)",
        settings.app_name,
        settings.app_version,
        settings.debug,
    )
    yield
    logger.info("Shutting down — closing database connection pool")
    close_pool()


# ── Application ──────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Backend API for Smart Health Sentinel supply-chain & demand forecasting system. "
        "Provides inventory CRUD, transfer state machine, shortage alerts, Prophet forecasting, "
        "and offline PWA synchronization."
    ),
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# ── Middleware ───────────────────────────────────────────────────────────────

app.add_middleware(SafeStructuredLoggingMiddleware)

# ADR-004: Restrict to explicit origins list from environment / config
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────

app.include_router(inventory.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(predictions.router, prefix="/api/v1")
app.include_router(facility.router, prefix="/api/v1")
app.include_router(transfers.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(stock_movements.router, prefix="/api/v1")
app.include_router(evaluations.router, prefix="/api/v1")
app.include_router(replenishment.router, prefix="/api/v1")
app.include_router(explanations.router, prefix="/api/v1")
app.include_router(shortage_router, prefix="/api")


# ── Health Probes ────────────────────────────────────────────────────────────

@app.get("/api/v1/health", tags=["Health"])
@app.get("/health", tags=["Health"])
async def api_health():
    """Lightweight operational health probe for Cloud Run and uptime monitors.
    
    Exposes only high-level status; never exposes secrets, database URLs,
    or internal topology diagnostics.
    """
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
    }


@app.get("/", tags=["Health"])
async def root():
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "running",
    }


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)

