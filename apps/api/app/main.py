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

from app.ai.registry import resolve_ai_config
from app.config import get_settings
from app.models.responses import ApiResponse
from app.routers import health as health_router
from app.routers import auth as auth_router
from app.routers import cases as cases_router
from app.routers import documents as documents_router
from app.routers import analysis as analysis_router
from app.routers import ai as ai_router
from app.services.analysis import WorkflowRunner, recover_stale_workflows

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

    ai_config = resolve_ai_config(settings)
    if ai_config.is_mock:
        logger.warning(
            "AI fixture mode is active (provider=%s). No AI model will be called. %s",
            ai_config.requested_provider,
            ai_config.message,
        )
    elif not ai_config.configured:
        logger.warning("No AI provider is configured. %s", ai_config.message)
    else:
        logger.info(
            "AI provider configured provider=%s model=%s",
            ai_config.provider,
            ai_config.model,
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

            required_tables = {
                "users",
                "cases",
                "case_memberships",
                "documents",
                "document_chunks",
                "workflow_runs",
            }
            missing_tables = required_tables - set(tables)
            if missing_tables:
                logger.info(
                    "Dev database is missing tables %s — creating schema via "
                    "SQLAlchemy metadata (for production use: alembic upgrade head).",
                    ", ".join(sorted(missing_tables)),
                )
                async with async_engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
        except Exception as exc:
            logger.error("Dev database schema check failed: %s", exc)

    # ------------------------------------------------------------------
    # Analysis workflow runner (in-process, bounded)
    # ------------------------------------------------------------------
    # Stage 5 runs workflows as FastAPI background tasks in the web process.
    # A durable queue/worker is a later-stage concern (see docs/decisions.md).
    try:
        from app.db.base import async_session_factory

        app.state.workflow_runner = WorkflowRunner(async_session_factory)
        recovered = await recover_stale_workflows(async_session_factory)
        if recovered:
            logger.warning(
                "Marked %d interrupted analysis workflow(s) as failed (retryable).",
                recovered,
            )
    except Exception as exc:
        logger.error(
            "Analysis workflow runner initialisation failed: %s", type(exc).__name__
        )
        app.state.workflow_runner = None

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
    # In development, accept any localhost/127.0.0.1 port so the frontend works
    # when Next.js falls back to 3001+ (a very common "Failed to fetch" cause).
    dev_origin_regex = r"^http://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$"
    cors_origin_regex = settings.cors_origin_regex or (
        None if settings.is_production else dev_origin_regex
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=cors_origin_regex,
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
    app.include_router(analysis_router.router, prefix=API_PREFIX)
    app.include_router(ai_router.router, prefix=API_PREFIX)

    # Convenience alias for probes/tools that expect /health at the root.
    @app.get("/health", include_in_schema=False)
    async def root_health():
        return await health_router.health()

    return app


# ---------------------------------------------------------------------------
# Application instance (referenced by uvicorn)
# ---------------------------------------------------------------------------

app = create_app()
