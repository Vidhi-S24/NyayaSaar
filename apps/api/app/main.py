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
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.models.responses import ApiResponse
from app.routers import health as health_router
from app.routers import auth as auth_router
from app.routers import cases as cases_router
from app.routers import documents as documents_router

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

    if not settings.gemini_configured:
        logger.warning(
            "GEMINI_API_KEY is not set. AI features will be unavailable. "
            "Set the key in your .env file or environment."
        )

    # Initialise the DB engine / connection pool if DATABASE_URL is set
    if settings.database_configured:
        try:
            from app.db.base import async_engine
            import sqlalchemy as sa

            async with async_engine.connect() as conn:
                await conn.execute(sa.text("SELECT 1"))
            logger.info("Database connection pool initialised.")
        except Exception as exc:
            logger.error("Database connection failed: %s", exc)
    else:
        logger.warning(
            "DATABASE_URL is not set — using the local development fallback "
            "(SQLite file ./nyayasaar-dev.db). Fine for development; "
            "configure PostgreSQL for production."
        )
        try:
            from sqlalchemy import inspect

            from app.db.base import Base, async_engine

            def _get_table_names(sync_conn):
                return inspect(sync_conn).get_table_names()

            async with async_engine.connect() as conn:
                tables = await conn.run_sync(_get_table_names)

            if "users" not in tables:
                logger.info(
                    "Empty dev database — creating schema via SQLAlchemy metadata "
                    "(for production use: alembic upgrade head)."
                )
                async with async_engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
        except Exception as exc:
            logger.error("Dev database schema check failed: %s", exc)

    yield  # ← application runs here

    # Dispose the engine on shutdown
    if settings.database_configured:
        try:
            from app.db.base import async_engine
            await async_engine.dispose()
        except Exception:
            pass

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
    # X-Request-ID middleware
    # -------------------------------------------------------------------

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

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
    app.include_router(auth_router.router, prefix=API_PREFIX)
    app.include_router(cases_router.router, prefix=API_PREFIX)
    app.include_router(documents_router.router, prefix=API_PREFIX)

    return app


# ---------------------------------------------------------------------------
# Application instance (referenced by uvicorn)
# ---------------------------------------------------------------------------

app = create_app()
