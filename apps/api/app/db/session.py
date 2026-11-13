"""
NyayaSaar API — FastAPI database session dependency.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import async_session_factory


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a SQLAlchemy async session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
