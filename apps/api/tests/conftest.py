"""
Test conftest — in-memory SQLite async database with aiosqlite.
No real PostgreSQL required.
"""

from __future__ import annotations

import os

# Tests must be hermetic: never pick up a developer's apps/api/.env (which may
# contain a real provider key). Force the labelled fixture before app imports.
os.environ["AI_PROVIDER"] = "mock"
os.environ["AI_MODEL"] = "fixture"
os.environ["AI_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""
os.environ["AI_BASE_URL"] = ""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.ai.providers.mock import MockProvider
from app.config import get_settings
from app.db.base import Base
from app.db.session import get_async_session
from app.main import create_app
from app.services.analysis import WorkflowRunner
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
# FastAPI test app + client using test DB
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def test_app(test_engine):
    """FastAPI app wired to the test DB and a deterministic fixture provider."""
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

    # Stage 5: workflows are normally scheduled by the lifespan runner. Tests
    # wire an equivalent runner against the in-memory DB and the clearly
    # labelled fixture provider (no network calls).
    app.state.workflow_runner = WorkflowRunner(
        factory,
        provider_factory=lambda settings: MockProvider(model="fixture"),
    )
    app.state.test_session_factory = factory
    return app


@pytest_asyncio.fixture(scope="function")
async def client(test_app):
    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
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
