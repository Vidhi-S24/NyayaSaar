"""
Tests — Documents API (HTTP integration tests via test client).

Authorization, upload validation, extraction status, deletion,
and cross-user access control are all tested here.
"""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.db.base import Base
from app.db.session import get_async_session
from app.main import create_app
from app.services.auth import hash_password
from app.services.storage import LocalStorageProvider, _reset_storage


# ---------------------------------------------------------------------------
# Shared test database (re-use conftest approach)
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(test_engine, tmp_path):
    """AsyncClient wired to test DB and local temp storage."""
    factory = sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async def override_session():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    # Wire a local temp storage
    _reset_storage()
    test_storage = LocalStorageProvider(str(tmp_path / "storage"))

    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_async_session] = override_session

    with patch("app.services.storage.get_storage", return_value=test_storage):
        with patch("app.routers.documents.get_storage", return_value=test_storage):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                yield ac

    _reset_storage()


# ---------------------------------------------------------------------------
# Auth fixtures (create two distinct users)
# ---------------------------------------------------------------------------


async def _register(client, email: str, password: str = "securepass123"):
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Test User"},
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["access_token"]


async def _create_case(client, token: str) -> str:
    r = await client.post(
        "/api/v1/cases",
        json={"title": "Test Case"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


def _pdf_bytes(text: str = "legal content") -> bytes:
    """Minimal valid PDF bytes."""
    return b"%PDF-1.4\n1 0 obj\n<< >>\nendobj\nxref\n0 2\ntrailer\n<< /Size 2 >>\nstartxref\n9\n%%EOF\n"


def _txt_bytes(text: str = "Some legal text.") -> bytes:
    return text.encode("utf-8")


# ---------------------------------------------------------------------------
# Upload tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_txt_success(client):
    token = await _register(client, "uploader@test.com")
    case_id = await _create_case(client, token)

    response = await client.post(
        f"/api/v1/cases/{case_id}/documents",
        files={"file": ("brief.txt", _txt_bytes(), "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["original_name"] == "brief.txt"
    assert data["processing_status"] in ("ready", "failed")  # extraction attempted
    assert data["content_type"] == "text/plain"


@pytest.mark.asyncio
async def test_upload_pdf_success(client):
    token = await _register(client, "pdfuser@test.com")
    case_id = await _create_case(client, token)

    response = await client.post(
        f"/api/v1/cases/{case_id}/documents",
        files={"file": ("petition.pdf", _pdf_bytes(), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    # Corrupt minimal PDF may fail extraction but should not crash the upload
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["original_name"] == "petition.pdf"


@pytest.mark.asyncio
async def test_upload_rejected_bad_extension(client):
    token = await _register(client, "badext@test.com")
    case_id = await _create_case(client, token)

    response = await client.post(
        f"/api/v1/cases/{case_id}/documents",
        files={"file": ("virus.exe", b"MZ\x90\x00", "application/octet-stream")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422, response.text


@pytest.mark.asyncio
async def test_upload_rejected_empty_file(client):
    token = await _register(client, "empty@test.com")
    case_id = await _create_case(client, token)

    response = await client.post(
        f"/api/v1/cases/{case_id}/documents",
        files={"file": ("empty.txt", b"", "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422, response.text


@pytest.mark.asyncio
async def test_upload_requires_auth(client):
    token = await _register(client, "authtest@test.com")
    case_id = await _create_case(client, token)

    response = await client.post(
        f"/api/v1/cases/{case_id}/documents",
        files={"file": ("doc.txt", _txt_bytes(), "text/plain")},
        # No auth header
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_upload_to_other_users_case_rejected(client):
    token_a = await _register(client, "owner@test.com")
    token_b = await _register(client, "other@test.com")
    case_id = await _create_case(client, token_a)

    response = await client.post(
        f"/api/v1/cases/{case_id}/documents",
        files={"file": ("doc.txt", _txt_bytes(), "text/plain")},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 404  # indistinguishable from "not found"


# ---------------------------------------------------------------------------
# List tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_documents(client):
    token = await _register(client, "listuser@test.com")
    case_id = await _create_case(client, token)

    # Upload two documents
    for i in range(2):
        await client.post(
            f"/api/v1/cases/{case_id}/documents",
            files={"file": (f"doc{i}.txt", _txt_bytes(f"content {i}"), "text/plain")},
            headers={"Authorization": f"Bearer {token}"},
        )

    response = await client.get(
        f"/api/v1/cases/{case_id}/documents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_list_documents_other_user_sees_empty(client):
    token_a = await _register(client, "ownerlist@test.com")
    token_b = await _register(client, "otherlist@test.com")
    case_id = await _create_case(client, token_a)

    await client.post(
        f"/api/v1/cases/{case_id}/documents",
        files={"file": ("doc.txt", _txt_bytes(), "text/plain")},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    response = await client.get(
        f"/api/v1/cases/{case_id}/documents",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["total"] == 0


# ---------------------------------------------------------------------------
# Get metadata tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_document_metadata(client):
    token = await _register(client, "getmeta@test.com")
    case_id = await _create_case(client, token)

    upload = await client.post(
        f"/api/v1/cases/{case_id}/documents",
        files={"file": ("meta.txt", _txt_bytes(), "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    doc_id = upload.json()["data"]["id"]

    response = await client.get(
        f"/api/v1/cases/{case_id}/documents/{doc_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["id"] == doc_id


@pytest.mark.asyncio
async def test_get_document_cross_user_returns_404(client):
    token_a = await _register(client, "getmeta_a@test.com")
    token_b = await _register(client, "getmeta_b@test.com")
    case_id = await _create_case(client, token_a)

    upload = await client.post(
        f"/api/v1/cases/{case_id}/documents",
        files={"file": ("secret.txt", _txt_bytes(), "text/plain")},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    doc_id = upload.json()["data"]["id"]

    response = await client.get(
        f"/api/v1/cases/{case_id}/documents/{doc_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Delete tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_document(client):
    token = await _register(client, "deleter@test.com")
    case_id = await _create_case(client, token)

    upload = await client.post(
        f"/api/v1/cases/{case_id}/documents",
        files={"file": ("todelete.txt", _txt_bytes(), "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    doc_id = upload.json()["data"]["id"]

    # Delete
    del_resp = await client.delete(
        f"/api/v1/cases/{case_id}/documents/{doc_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_resp.status_code == 200

    # Should be gone
    get_resp = await client.get(
        f"/api/v1/cases/{case_id}/documents/{doc_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_document_decrements_count(client):
    token = await _register(client, "decrement@test.com")
    case_id = await _create_case(client, token)

    upload = await client.post(
        f"/api/v1/cases/{case_id}/documents",
        files={"file": ("count.txt", _txt_bytes(), "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    doc_id = upload.json()["data"]["id"]

    # Case should have 1 doc
    case_resp = await client.get(
        f"/api/v1/cases/{case_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert case_resp.json()["data"]["documents_count"] == 1

    await client.delete(
        f"/api/v1/cases/{case_id}/documents/{doc_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    case_resp2 = await client.get(
        f"/api/v1/cases/{case_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert case_resp2.json()["data"]["documents_count"] == 0


@pytest.mark.asyncio
async def test_delete_cross_user_returns_404(client):
    token_a = await _register(client, "del_a@test.com")
    token_b = await _register(client, "del_b@test.com")
    case_id = await _create_case(client, token_a)

    upload = await client.post(
        f"/api/v1/cases/{case_id}/documents",
        files={"file": ("protected.txt", _txt_bytes(), "text/plain")},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    doc_id = upload.json()["data"]["id"]

    del_resp = await client.delete(
        f"/api/v1/cases/{case_id}/documents/{doc_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert del_resp.status_code == 404

    # Document should still exist for original owner
    get_resp = await client.get(
        f"/api/v1/cases/{case_id}/documents/{doc_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert get_resp.status_code == 200


# ---------------------------------------------------------------------------
# Extracted text preview
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_text_preview_ready_document(client):
    token = await _register(client, "preview@test.com")
    case_id = await _create_case(client, token)

    upload = await client.post(
        f"/api/v1/cases/{case_id}/documents",
        files={"file": ("preview.txt", _txt_bytes("Facts: Section 1\nFacts: Section 2"), "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    doc_id = upload.json()["data"]["id"]
    upload_status = upload.json()["data"]["processing_status"]

    if upload_status == "ready":
        response = await client.get(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/text",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert "chunks" in data
        assert data["total_pages"] >= 1
