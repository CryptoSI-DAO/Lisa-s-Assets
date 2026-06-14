"""Lisa's Assets — FastAPI application entrypoint.

Run locally:
    cd backend
    uvicorn app.main:app --reload

Issues #1, #4.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__, db
from .config import get_settings
from .models.schemas import HealthResponse
from .routers import crowdfund, nft, newsletter, payments, projects, reports

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("lisa-assets")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise / tear down the DB connection pool around app lifetime."""
    logger.info("Starting Lisa's Assets backend v%s", __version__)
    try:
        await db.init_pool()
        logger.info("Database pool ready")
    except Exception as exc:
        # Don't crash the app — health check will surface the DB status.
        logger.error("DB pool init failed: %s", exc)
    yield
    logger.info("Shutting down — closing DB pool")
    await db.close_pool()


settings = get_settings()

app = FastAPI(
    title="Lisa's Assets API",
    description=(
        "Lisa Coefficient scoring backend for crypto projects / Bittensor "
        "subnets. Browse projects, fetch Lisa Coefficient reports, and (soon) "
        "pay to generate new analyses."
    ),
    version=__version__,
    lifespan=lifespan,
)

# CORS — allow the frontend (and local dev tools) to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to the real frontend domain in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(projects.router)
app.include_router(reports.router)
app.include_router(payments.router)
app.include_router(newsletter.router)
app.include_router(crowdfund.router)
app.include_router(nft.router)


@app.get("/health", response_model=HealthResponse, tags=["meta"])
async def health():
    """Liveness + readiness probe."""
    db_status = "unknown"
    try:
        await db.fetchval("SELECT 1")
        db_status = "ok"
    except Exception as exc:
        db_status = f"error: {exc.__class__.__name__}"
    return HealthResponse(
        status="ok",
        version=__version__,
        database=db_status,
    )


@app.get("/", tags=["meta"])
async def root():
    return {
        "name": "Lisa's Assets API",
        "version": __version__,
        "docs": "/docs",
        "health": "/health",
    }
