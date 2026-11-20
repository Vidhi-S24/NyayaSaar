"""
NyayaSaar API — Health router

GET /api/v1/health  — liveness check (fast, no external calls)
GET /api/v1/ready   — readiness check (verifies optional services)
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import sqlalchemy as sa
from fastapi import APIRouter

from app.config import get_settings
from app.models.responses import ApiResponse, HealthResponse, HealthServiceStatus

router = APIRouter(tags=["health"])
settings = get_settings()


async def _probe_database() -> HealthServiceStatus:
    """Do a real SELECT 1 against the configured DB."""
    if not settings.database_configured:
        return HealthServiceStatus(
            status="unavailable",
            message="DATABASE_URL not configured; required from Stage 3",
        )
    try:
        from app.db.base import async_engine

        t0 = time.monotonic()
        async with async_engine.connect() as conn:
            await conn.execute(sa.text("SELECT 1"))
        latency_ms = (time.monotonic() - t0) * 1000
        return HealthServiceStatus(status="ok", latency_ms=round(latency_ms, 2))
    except Exception as exc:
        return HealthServiceStatus(status="degraded", message=str(exc))


async def _make_health(*, include_service_checks: bool = False) -> HealthResponse:
    """Build a HealthResponse, optionally probing optional services."""

    services: dict[str, HealthServiceStatus] = {}
    overall = "ok"

    if include_service_checks:
        # Database — real ping
        db_status = await _probe_database()
        services["database"] = db_status
        if db_status.status != "ok":
            overall = "degraded"

        # Redis — configured for future background jobs, not used in Stage 5
        if settings.redis_configured:
            services["redis"] = HealthServiceStatus(
                status="degraded",
                message=(
                    "Configured but not used in Stage 5; analysis runs in-process "
                    "and Redis/Celery is deferred (D-029). Connectivity not probed."
                ),
            )
        else:
            services["redis"] = HealthServiceStatus(
                status="unavailable",
                message="REDIS_URL not configured; optional until a durable queue is added",
            )

        # Neo4j
        if settings.neo4j_configured:
            services["neo4j"] = HealthServiceStatus(
                status="degraded",
                message="Configured but not used yet; connectivity not probed",
            )
        else:
            services["neo4j"] = HealthServiceStatus(
                status="unavailable",
                message="NEO4J_URI not configured; optional for citation graph features",
            )

        # AI provider (provider-agnostic; never exposes the key)
        provider = settings.ai_provider
        if settings.ai_configured:
            services["ai"] = HealthServiceStatus(
                status="ok",
                message=(
                    f"Provider '{provider}' configured; connectivity not probed. "
                    "Fixture mode is labelled at /api/v1/ai/status."
                ),
            )
        else:
            services["ai"] = HealthServiceStatus(
                status="unavailable",
                message=(
                    f"No credentials for AI provider '{provider}'; AI features "
                    "will use the labelled development fixture (non-production) "
                    "or report unavailable in production."
                ),
            )

    return HealthResponse(
        status=overall,
        version=settings.app_version,
        env=settings.app_env,
        timestamp=datetime.now(timezone.utc).isoformat(),
        services=services,
    )


@router.get("/health", response_model=ApiResponse[HealthResponse], summary="Liveness check")
async def health() -> ApiResponse[HealthResponse]:
    """
    Liveness endpoint — returns 200 quickly without probing external services.
    Suitable for Render / load-balancer health checks.
    """
    return ApiResponse.ok(await _make_health())


@router.get(
    "/ready",
    response_model=ApiResponse[HealthResponse],
    summary="Readiness check",
)
async def ready() -> ApiResponse[HealthResponse]:
    """
    Readiness endpoint — probes configured services and reports their status.
    Returns 200 even when optional services are unavailable (they are flagged
    as ``unavailable``, not as errors, so Render does not restart the pod).
    """
    health_data = await _make_health(include_service_checks=True)
    return ApiResponse.ok(health_data)
