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


@pytest.mark.asyncio
async def test_health_response_envelope(client: AsyncClient):
    """Ensure all fields of the response envelope are present."""
    response = await client.get("/api/v1/health")
    body = response.json()
    assert "success" in body
    assert "data" in body
    # error should be absent on success
    assert body.get("error") is None
