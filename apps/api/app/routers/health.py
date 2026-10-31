"""
NyayaSaar API — Health router

GET /api/v1/health  — liveness check (fast, no external calls)
GET /api/v1/ready   — readiness check (verifies optional services)
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from fastapi import APIRouter

from apps.api.app.config import get_settings
from apps.api.app.models.responses import ApiResponse, HealthResponse, HealthServiceStatus

router = APIRouter(tags=["health"])
settings = get_settings()


def _make_health(*, include_service_checks: bool = False) -> HealthResponse:
    """Build a HealthResponse, optionally probing optional services."""

    services: dict[str, HealthServiceStatus] = {}
    overall = "ok"

    if include_service_checks:
        # Database
        if settings.database_configured:
            # Actual probe will be added in Stage 3 when SQLAlchemy is wired.
            services["database"] = HealthServiceStatus(
                status="ok", message="Connection pool not yet initialised (Stage 1)"
            )
        else:
            services["database"] = HealthServiceStatus(
                status="unavailable",
                message="DATABASE_URL not configured; required from Stage 3",
            )
            overall = "degraded"

        # Redis
        if settings.redis_configured:
            services["redis"] = HealthServiceStatus(
                status="ok", message="Not yet probed (background jobs staged)"
            )
        else:
            services["redis"] = HealthServiceStatus(
                status="unavailable",
                message="REDIS_URL not configured; optional until background jobs are needed",
            )

        # Neo4j
        if settings.neo4j_configured:
            services["neo4j"] = HealthServiceStatus(
                status="ok", message="Not yet probed (citation graph staged)"
            )
        else:
            services["neo4j"] = HealthServiceStatus(
                status="unavailable",
                message="NEO4J_URI not configured; optional for citation graph features",
            )

        # Gemini
        if settings.gemini_configured:
            services["gemini"] = HealthServiceStatus(
                status="ok", message="API key present; connectivity not probed"
            )
        else:
            services["gemini"] = HealthServiceStatus(
                status="unavailable",
                message="GEMINI_API_KEY not configured; required for AI features",
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
    return ApiResponse.ok(_make_health())


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
    health_data = _make_health(include_service_checks=True)
    return ApiResponse.ok(health_data)

