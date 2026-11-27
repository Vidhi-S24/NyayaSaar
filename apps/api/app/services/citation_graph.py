"""Optional citation graph backend for Stage 9 — Precedent Explorer.

Implements a provider-agnostic CitationGraphProvider. When Neo4j is not
configured (NEO4J_URI absent or empty), falls back gracefully to the
citation_links table in the main database. Never raises if the backend is
unavailable — returns empty results instead.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger("nyayasaar.citation_graph")


class CitationGraphProvider(ABC):
    """Abstract provider for storing and querying citation relationships."""

    @abstractmethod
    async def store_citations(self, pairs: list[dict[str, Any]]) -> int:
        """Persist citation pairs; return count stored."""

    @abstractmethod
    async def get_outgoing_citations(self, record_id: str) -> list[dict[str, Any]]:
        """Return citation links where from_record_id == record_id."""

    @abstractmethod
    async def get_incoming_citations(self, record_id: str) -> list[dict[str, Any]]:
        """Return citation links where to_record_id == record_id."""


class _NullCitationGraphProvider(CitationGraphProvider):
    """No-op provider used when neither Neo4j nor DB is available."""

    async def store_citations(self, pairs: list[dict[str, Any]]) -> int:
        return 0

    async def get_outgoing_citations(self, record_id: str) -> list[dict[str, Any]]:
        return []

    async def get_incoming_citations(self, record_id: str) -> list[dict[str, Any]]:
        return []


class Neo4jCitationGraphProvider(CitationGraphProvider):
    """Neo4j-backed citation graph. Gracefully returns empty if driver fails."""

    def __init__(self, uri: str, user: str, password: str) -> None:
        self._uri = uri
        self._user = user
        self._password = password
        self._driver: Any = None
        self._available = False
        try:
            from neo4j import AsyncGraphDatabase  # type: ignore

            self._driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
            self._available = True
            logger.info("Neo4j citation graph provider initialised uri=%s", uri)
        except Exception as exc:
            logger.warning(
                "Neo4j citation graph unavailable; falling back to null provider. reason=%s",
                exc,
            )

    async def store_citations(self, pairs: list[dict[str, Any]]) -> int:
        if not self._available or not pairs:
            return 0
        try:
            async with self._driver.session() as session:
                stored = 0
                for pair in pairs:
                    await session.run(
                        """
                        MERGE (a:LegalRecord {id: $from_id})
                        MERGE (b:LegalRecord {id: $to_id})
                        MERGE (a)-[r:CITES {relationship_type: $rel_type}]->(b)
                        SET r.confidence = $confidence,
                            r.source_provider = $provider
                        """,
                        from_id=str(pair.get("from_record_id", "")),
                        to_id=str(pair.get("to_record_id", "") or ""),
                        rel_type=str(pair.get("relationship_type", "cites")),
                        confidence=str(pair.get("confidence", "medium")),
                        provider=str(pair.get("source_provider", "precedent")),
                    )
                    stored += 1
            return stored
        except Exception as exc:
            logger.warning("Neo4j store_citations failed reason=%s", exc)
            return 0

    async def get_outgoing_citations(self, record_id: str) -> list[dict[str, Any]]:
        if not self._available:
            return []
        try:
            async with self._driver.session() as session:
                result = await session.run(
                    """
                    MATCH (a:LegalRecord {id: $id})-[r:CITES]->(b:LegalRecord)
                    RETURN b.id AS to_id, r.relationship_type AS rel, r.confidence AS conf
                    LIMIT 50
                    """,
                    id=record_id,
                )
                return [
                    {
                        "to_record_id": rec["to_id"],
                        "relationship_type": rec["rel"],
                        "confidence": rec["conf"],
                    }
                    async for rec in result
                ]
        except Exception as exc:
            logger.warning("Neo4j get_outgoing_citations failed reason=%s", exc)
            return []

    async def get_incoming_citations(self, record_id: str) -> list[dict[str, Any]]:
        if not self._available:
            return []
        try:
            async with self._driver.session() as session:
                result = await session.run(
                    """
                    MATCH (a:LegalRecord)-[r:CITES]->(b:LegalRecord {id: $id})
                    RETURN a.id AS from_id, r.relationship_type AS rel, r.confidence AS conf
                    LIMIT 50
                    """,
                    id=record_id,
                )
                return [
                    {
                        "from_record_id": rec["from_id"],
                        "relationship_type": rec["rel"],
                        "confidence": rec["conf"],
                    }
                    async for rec in result
                ]
        except Exception as exc:
            logger.warning("Neo4j get_incoming_citations failed reason=%s", exc)
            return []


class DatabaseCitationGraphProvider(CitationGraphProvider):
    """SQLAlchemy async session-based citation graph using citation_links table."""

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    async def store_citations(self, pairs: list[dict[str, Any]]) -> int:
        if not pairs:
            return 0
        stored = 0
        try:
            from sqlalchemy import select

            from app.db.models.citation import CitationLink

            async with self._session_factory() as db:
                for pair in pairs:
                    link = CitationLink(
                        from_record_id=str(pair.get("from_record_id", "")),
                        to_record_id=pair.get("to_record_id") or None,
                        to_citation_text=str(pair.get("to_citation_text", ""))[:500],
                        relationship_type=str(pair.get("relationship_type", "cites"))[:40],
                        source_passage=(str(pair.get("source_passage", "")) or None),
                        source_provider=str(pair.get("source_provider", "precedent"))[:60],
                        is_resolved=bool(pair.get("to_record_id")),
                        confidence=str(pair.get("confidence", "medium"))[:20],
                        workflow_id=pair.get("workflow_id") or None,
                        metadata_json=pair.get("metadata_json") or {},
                    )
                    db.add(link)
                    stored += 1
                await db.commit()
        except Exception as exc:
            logger.warning("DB store_citations failed reason=%s", exc)
        return stored

    async def get_outgoing_citations(self, record_id: str) -> list[dict[str, Any]]:
        try:
            from sqlalchemy import select

            from app.db.models.citation import CitationLink

            async with self._session_factory() as db:
                result = await db.execute(
                    select(CitationLink)
                    .where(CitationLink.from_record_id == record_id)
                    .limit(50)
                )
                rows = result.scalars().all()
                return [
                    {
                        "id": r.id,
                        "to_record_id": r.to_record_id,
                        "to_citation_text": r.to_citation_text,
                        "relationship_type": r.relationship_type,
                        "confidence": r.confidence,
                        "is_resolved": r.is_resolved,
                    }
                    for r in rows
                ]
        except Exception as exc:
            logger.warning("DB get_outgoing_citations failed reason=%s", exc)
            return []

    async def get_incoming_citations(self, record_id: str) -> list[dict[str, Any]]:
        try:
            from sqlalchemy import select

            from app.db.models.citation import CitationLink

            async with self._session_factory() as db:
                result = await db.execute(
                    select(CitationLink)
                    .where(CitationLink.to_record_id == record_id)
                    .limit(50)
                )
                rows = result.scalars().all()
                return [
                    {
                        "id": r.id,
                        "from_record_id": r.from_record_id,
                        "to_citation_text": r.to_citation_text,
                        "relationship_type": r.relationship_type,
                        "confidence": r.confidence,
                        "is_resolved": r.is_resolved,
                    }
                    for r in rows
                ]
        except Exception as exc:
            logger.warning("DB get_incoming_citations failed reason=%s", exc)
            return []


def get_citation_graph_provider(
    settings: Any,
    session_factory: Any | None = None,
) -> CitationGraphProvider:
    """Factory: return Neo4j provider if configured, else DB provider, else null."""
    neo4j_uri = getattr(settings, "neo4j_uri", None) or ""
    if neo4j_uri:
        return Neo4jCitationGraphProvider(
            uri=neo4j_uri,
            user=getattr(settings, "neo4j_user", "neo4j") or "neo4j",
            password=getattr(settings, "neo4j_password", "") or "",
        )
    if session_factory is not None:
        return DatabaseCitationGraphProvider(session_factory)
    logger.debug("No citation graph backend configured; using null provider.")
    return _NullCitationGraphProvider()
