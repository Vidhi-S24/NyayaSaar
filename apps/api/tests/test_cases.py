"""
Cases endpoint tests.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _register_and_login(client: AsyncClient, email: str, password: str = "password123"):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}


# ---------------------------------------------------------------------------
# CRUD tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_case(client: AsyncClient, auth_headers):
    resp = await client.post(
        "/api/v1/cases",
        json={"title": "Test Case Alpha", "status": "active", "priority": "high"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["title"] == "Test Case Alpha"
    assert body["data"]["status"] == "active"
    assert body["data"]["priority"] == "high"


@pytest.mark.asyncio
async def test_get_case(client: AsyncClient, auth_headers):
    # Create
    create_resp = await client.post(
        "/api/v1/cases",
        json={"title": "Get Test Case"},
        headers=auth_headers,
    )
    case_id = create_resp.json()["data"]["id"]

    # Fetch
    resp = await client.get(f"/api/v1/cases/{case_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == case_id


@pytest.mark.asyncio
async def test_list_cases(client: AsyncClient, auth_headers):
    for i in range(3):
        await client.post(
            "/api/v1/cases",
            json={"title": f"Case {i}"},
            headers=auth_headers,
        )
    resp = await client.get("/api/v1/cases", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["total"] >= 3
    assert len(body["data"]["items"]) >= 3


@pytest.mark.asyncio
async def test_list_cases_pagination(client: AsyncClient, auth_headers):
    for i in range(5):
        await client.post(
            "/api/v1/cases",
            json={"title": f"Page Case {i}"},
            headers=auth_headers,
        )
    resp = await client.get("/api/v1/cases?page=1&page_size=2", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["items"]) == 2
    assert data["has_next"] is True


@pytest.mark.asyncio
async def test_update_case(client: AsyncClient, auth_headers):
    create_resp = await client.post(
        "/api/v1/cases",
        json={"title": "Update Me"},
        headers=auth_headers,
    )
    case_id = create_resp.json()["data"]["id"]

    resp = await client.patch(
        f"/api/v1/cases/{case_id}",
        json={"title": "Updated Title", "status": "review"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["title"] == "Updated Title"
    assert data["status"] == "review"


@pytest.mark.asyncio
async def test_delete_case(client: AsyncClient, auth_headers):
    create_resp = await client.post(
        "/api/v1/cases",
        json={"title": "Delete Me"},
        headers=auth_headers,
    )
    case_id = create_resp.json()["data"]["id"]

    del_resp = await client.delete(f"/api/v1/cases/{case_id}", headers=auth_headers)
    assert del_resp.status_code == 200

    get_resp = await client.get(f"/api/v1/cases/{case_id}", headers=auth_headers)
    assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# Authorization tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_cannot_see_other_users_case(client: AsyncClient):
    headers_a = await _register_and_login(client, "usera@example.com")
    headers_b = await _register_and_login(client, "userb@example.com")

    # User A creates a case
    create_resp = await client.post(
        "/api/v1/cases",
        json={"title": "User A's private case"},
        headers=headers_a,
    )
    case_id = create_resp.json()["data"]["id"]

    # User B cannot see it — should get 404 (not 403, to not leak existence)
    resp = await client.get(f"/api/v1/cases/{case_id}", headers=headers_b)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_user_cannot_update_other_users_case(client: AsyncClient):
    headers_a = await _register_and_login(client, "updatea@example.com")
    headers_b = await _register_and_login(client, "updateb@example.com")

    create_resp = await client.post(
        "/api/v1/cases",
        json={"title": "Owner A's case"},
        headers=headers_a,
    )
    case_id = create_resp.json()["data"]["id"]

    resp = await client.patch(
        f"/api/v1/cases/{case_id}",
        json={"title": "Hijacked"},
        headers=headers_b,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_user_cannot_delete_other_users_case(client: AsyncClient):
    headers_a = await _register_and_login(client, "dela@example.com")
    headers_b = await _register_and_login(client, "delb@example.com")

    create_resp = await client.post(
        "/api/v1/cases",
        json={"title": "Safe Case"},
        headers=headers_a,
    )
    case_id = create_resp.json()["data"]["id"]

    resp = await client.delete(f"/api/v1/cases/{case_id}", headers=headers_b)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cases_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/cases")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_search_cases(client: AsyncClient, auth_headers):
    await client.post("/api/v1/cases", json={"title": "Criminal Appeal"}, headers=auth_headers)
    await client.post("/api/v1/cases", json={"title": "Civil Dispute"}, headers=auth_headers)

    resp = await client.get("/api/v1/cases?search=Criminal", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert all("Criminal" in item["title"] for item in items)


@pytest.mark.asyncio
async def test_filter_cases_by_status(client: AsyncClient, auth_headers):
    await client.post("/api/v1/cases", json={"title": "Active 1", "status": "active"}, headers=auth_headers)
    await client.post("/api/v1/cases", json={"title": "Closed 1", "status": "closed"}, headers=auth_headers)

    resp = await client.get("/api/v1/cases?status=active", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert all(item["status"] == "active" for item in items)
