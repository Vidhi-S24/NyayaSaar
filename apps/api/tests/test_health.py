"""
NyayaSaar API tests — Health endpoint tests
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.api.app.main import app

client = TestClient(app)


def test_root_returns_service_info():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "NyayaSaar API"
    assert "health" in data


def test_health_liveness():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"
    assert "version" in body["data"]
    assert "timestamp" in body["data"]


def test_health_readiness():
    response = client.get("/api/v1/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    # Should always have services dict (may be empty or have entries)
    assert isinstance(data["services"], dict)
    # Without env vars, services like database should be unavailable
    assert data["services"]["database"]["status"] == "unavailable"


def test_health_response_envelope():
    """Ensure all fields of the response envelope are present."""
    response = client.get("/api/v1/health")
    body = response.json()
    assert "success" in body
    assert "data" in body
    # error should be absent on success
    assert body.get("error") is None

