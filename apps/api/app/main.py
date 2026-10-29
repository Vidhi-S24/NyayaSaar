"""
NyayaSaar API — FastAPI application factory

Architecture:
  Vercel (Next.js)  →  Render (FastAPI + LangGraph)  →  PostgreSQL/pgvector
                                                      →  Google Gemini (AI)
                                                      →  Neo4j (optional)
                                                      →  Redis/Celery (optional)

All routes are versioned under /api/v1.
The root path / is a lightweight redirect/info endpoint for diagnostics.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.models.responses import ApiResponse
from app.routers import health as health_router

settings = get_settings()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("nyayasaar")


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    Startup: initialise connection pools, validate required config.
    Shutdown: gracefully close connections.
    """
    logger.info(
        "NyayaSaar API starting up — env=%s version=%s",
        settings.app_env,
        settings.app_version,
    )

    # Warn about unconfigured services so operators can spot problems early.
    if not settings.gemini_configured:
        logger.warning(
            "GEMINI_API_KEY is not set. AI features will be unavailable. "
            "Set the key in your .env file or environment."
        )
    if not settings.database_configured:
        logger.warning(
            "DATABASE_URL is not set. Database features will be unavailable "
            "until Stage 3 wires up PostgreSQL."
        )

    yield  # ← application runs here

    logger.info("NyayaSaar API shutting down.")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    app = FastAPI(
        title="NyayaSaar API",
        description=(
            "Multi-agent legal case intelligence and precedent reasoning platform. "
            "All AI outputs require professional legal verification."
        ),
        version=settings.app_version,
        lifespan=lifespan,
        # In production, hide the /docs and /redoc endpoints.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
    )

    # -------------------------------------------------------------------
    # CORS
    # -------------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -------------------------------------------------------------------
    # Global exception handlers
    # -------------------------------------------------------------------

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("Unhandled exception for %s %s", request.method, request.url)
        body = ApiResponse.fail(
            code="internal_error",
            message="An unexpected error occurred. Please try again.",
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=body.model_dump(),
        )

    # -------------------------------------------------------------------
    # Root info endpoint
    # -------------------------------------------------------------------

    @app.get("/", include_in_schema=False)
    async def root() -> dict:
        return {
            "service": "NyayaSaar API",
            "version": settings.app_version,
            "docs": "/docs" if not settings.is_production else "disabled",
            "health": "/api/v1/health",
        }

    # -------------------------------------------------------------------
    # Versioned API routers
    # -------------------------------------------------------------------
    API_PREFIX = "/api/v1"

    app.include_router(health_router.router, prefix=API_PREFIX)
    # Future stages will register additional routers here:
    # app.include_router(cases_router.router, prefix=API_PREFIX)
    # app.include_router(documents_router.router, prefix=API_PREFIX)
    # app.include_router(analysis_router.router, prefix=API_PREFIX)

    return app


# ---------------------------------------------------------------------------
# Application instance (referenced by uvicorn)
# ---------------------------------------------------------------------------

app = create_app()

