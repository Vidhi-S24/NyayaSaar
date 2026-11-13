"""
Test conftest — in-memory SQLite async database with aiosqlite.
No real PostgreSQL required.
"""

from __future__ import annotations

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


# ---------------------------------------------------------------------------
# Test database (in-memory SQLite via aiosqlite)
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
async def test_session(test_engine):
    factory = sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with factory() as session:
        yield session


# ---------------------------------------------------------------------------
# FastAPI test client using test DB
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def client(test_engine):
    """AsyncClient with the FastAPI app wired to the test SQLite DB."""
    factory = sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async def override_get_session():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    # Clear settings cache to get fresh settings for tests
    get_settings.cache_clear()

    app = create_app()
    app.dependency_overrides[get_async_session] = override_get_session

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# Auth fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def registered_user(client):
    """Create and return a registered user + token."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "password": "securepass123", "full_name": "Test User"},
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    return {"token": data["access_token"], "email": "user@example.com"}


@pytest_asyncio.fixture
async def auth_headers(registered_user):
    return {"Authorization": f"Bearer {registered_user['token']}"}
