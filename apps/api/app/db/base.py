"""
NyayaSaar API — SQLAlchemy async engine and declarative base.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.config import get_settings

settings = get_settings()

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

# File-based dev fallback: accounts and cases persist across server restarts.
# (An in-memory DB was unusable — every connection got a fresh empty schema.)
DEV_SQLITE_FALLBACK_URL = "sqlite+aiosqlite:///./nyayasaar-dev.db"


def using_dev_fallback() -> bool:
    """True when no DATABASE_URL is configured and the local SQLite file is used."""
    return not bool(settings.database_url)


def _build_engine() -> AsyncEngine:
    db_url = settings.database_url or DEV_SQLITE_FALLBACK_URL
    return create_async_engine(
        db_url,
        pool_pre_ping=True,
        echo=False,
        future=True,
    )


async_engine: AsyncEngine = _build_engine()

async_session_factory: sessionmaker[AsyncSession] = sessionmaker(  # type: ignore[type-arg]
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ---------------------------------------------------------------------------
# Declarative base with timestamp mixin
# ---------------------------------------------------------------------------


class TimestampMixin:
    """Adds created_at and updated_at columns managed automatically."""

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=sa.func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=sa.func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class Base(AsyncAttrs, DeclarativeBase):
    """Project-wide SQLAlchemy declarative base."""

    type_annotation_map: dict[Any, Any] = {}
