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

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


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
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS Middleware ──────────────────────────────────────────────────────────
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
app.include_router(shortage_router, prefix="/api")



# ── Root and System Health Checks ──────────────────────────────────────────

@app.get("/", tags=["Health"])
async def root():
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
@app.get("/api/v1/health", tags=["Health"])
async def health_check():
    from app.db import check_db_health
    from fastapi.responses import JSONResponse
    
    db_report = check_db_health()
    is_healthy = db_report.get("status") == "ok"
    
    content = {
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "status": "healthy" if is_healthy else "unhealthy",
        "database": db_report,
    }
    
    if not is_healthy and settings.environment in ("production", "staging"):
        return JSONResponse(status_code=503, content=content)
    return content


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)

