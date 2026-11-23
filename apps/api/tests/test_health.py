"""
NyayaSaar API tests — Health endpoint tests
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_returns_service_info(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "NyayaSaar API"
    assert "health" in data


@pytest.mark.asyncio
async def test_health_liveness(client: AsyncClient):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"
    assert "version" in body["data"]
    assert "timestamp" in body["data"]


@pytest.mark.asyncio
async def test_health_readiness(client: AsyncClient):
    response = await client.get("/api/v1/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    # Should always have services dict (may be empty or have entries)
    assert isinstance(data["services"], dict)
    # Without env vars (but with SQLite in-memory), database may be "ok" or "unavailable"
    assert data["services"]["database"]["status"] in ("ok", "unavailable", "degraded")
    # AI status is provider-agnostic and never exposes credentials
    assert data["services"]["ai"]["status"] in ("ok", "unavailable")
    assert "api_key" not in str(data).lower()
    assert "secret" not in str(data).lower()


@pytest.mark.asyncio
async def test_root_health_alias(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["success"] is True


@pytest.mark.asyncio
async def test_cors_allows_local_dev_port(client: AsyncClient):
    """Next.js often falls back to 3001+; preflight must not 400."""
    response = await client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://127.0.0.1:3001",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3001"


@pytest.mark.asyncio
async def test_openai_style_path_is_rejected(client: AsyncClient):
    """NyayaSaar is not an OpenAI-compatible server; /v1/* must stay 404."""
    response = await client.get("/v1/models")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_health_response_envelope(client: AsyncClient):
    """Ensure all fields of the response envelope are present."""
    response = await client.get("/api/v1/health")
    body = response.json()
    assert "success" in body
    assert "data" in body
    # error should be absent on success
    assert body.get("error") is None
