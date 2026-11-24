"""Ingestion and embedding indexing for legal records and case document chunks."""

from __future__ import annotations

import logging
import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import EmbeddingProvider
from app.db.models.case import Case
from app.db.models.document import Document, DocumentChunk
from app.db.models.legal_record import LegalRecord, LegalRecordChunk
from app.services.retrieval.chunking import chunk_text

logger = logging.getLogger("nyayasaar.retrieval.ingestion")


def _vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in vec) + "]"


async def ingest_legal_record(
    db: AsyncSession,
    *,
    owner_id: str | None,
    title: str,
    text: str,
    source_provider: str = "database",
    external_id: str | None = None,
    citation: str | None = None,
    jurisdiction: str | None = None,
    court: str | None = None,
    decision_date: str | None = None,
    year: str | None = None,
    source_url: str | None = None,
    summary: str | None = None,
    is_fixture: bool = False,
    metadata: dict[str, Any] | None = None,
    page_number: int | None = None,
    embedding_provider: EmbeddingProvider | None = None,
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
) -> LegalRecord:
    """Ingest a legal record, chunk it with provenance, and generate embeddings."""
    record = LegalRecord(
        id=str(uuid.uuid4()),
        owner_id=owner_id,
        source_provider=source_provider.strip() or "database",
        external_id=external_id,
        title=title.strip(),
        citation=citation.strip() if citation else None,
        jurisdiction=jurisdiction.strip() if jurisdiction else None,
        court=court.strip() if court else None,
        decision_date=decision_date.strip() if decision_date else None,
        year=year.strip() if year else (decision_date[:4] if decision_date else None),
        source_url=source_url.strip() if source_url else None,
        summary=summary.strip() if summary else None,
        is_fixture=is_fixture,
        metadata_json=metadata or {},
    )
    db.add(record)
    await db.flush()

    chunks = chunk_text(
        text,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        page_number=page_number,
    )
    vectors: list[list[float]] = []
    model_name: str | None = None
    dim: int | None = None
    if embedding_provider is not None and chunks:
        emb_result = await embedding_provider.embed_texts([c.text for c in chunks])
        vectors = emb_result.vectors
        model_name = emb_result.model
        dim = emb_result.dimensions

    is_pg = db.bind is not None and db.bind.dialect.name == "postgresql"
    for idx, ch in enumerate(chunks):
        vec = vectors[idx] if idx < len(vectors) else None
        row = LegalRecordChunk(
            id=str(uuid.uuid4()),
            record_id=record.id,
            chunk_index=ch.chunk_index,
            page_number=ch.page_number,
            paragraph_number=ch.paragraph_number,
            char_start=ch.char_start,
            char_end=ch.char_end,
            text=ch.text,
            char_count=len(ch.text),
            content_hash=ch.content_hash,
            embedding_json=vec,
            embedding_model=model_name if vec else None,
            embedding_dim=dim if vec else None,
            metadata_json={},
        )
        db.add(row)
        if is_pg and vec is not None:
            await db.flush()
            await db.execute(
                sa.text(
                    "UPDATE legal_record_chunks "
                    "SET embedding = CAST(:vec AS vector) WHERE id = :id"
                ),
                {"vec": _vector_literal(vec), "id": row.id},
            )

    await db.flush()
    await db.refresh(record)
    return record


async def index_case_documents(
    db: AsyncSession,
    *,
    case_id: str,
    user_id: str,
    embedding_provider: EmbeddingProvider | None,
    force: bool = False,
) -> dict[str, Any]:
    """Generate and persist embeddings for ready document chunks in an owned case."""
    case_res = await db.execute(
        select(Case).where(Case.id == case_id, Case.owner_id == user_id)
    )
    if case_res.scalar_one_or_none() is None:
        raise PermissionError("Case not found or access denied.")

    stmt = (
        select(DocumentChunk)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            Document.case_id == case_id,
            Document.owner_id == user_id,
            Document.processing_status == "ready",
        )
        .order_by(Document.created_at.asc(), DocumentChunk.page_number.asc())
    )
    chunks = list((await db.execute(stmt)).scalars().all())
    if embedding_provider is None:
        return {
            "case_id": case_id,
            "total_chunks": len(chunks),
            "indexed_chunks": 0,
            "embedding_provider": "none",
            "embedding_model": None,
            "dimensions": 0,
        }

    to_index = [
        ch
        for ch in chunks
        if force
        or not ch.embedding_json
        or ch.embedding_dim != embedding_provider.dimensions
        or ch.embedding_model != embedding_provider.model
    ]
    if not to_index:
        return {
            "case_id": case_id,
            "total_chunks": len(chunks),
            "indexed_chunks": 0,
            "embedding_provider": embedding_provider.name,
            "embedding_model": embedding_provider.model,
            "dimensions": embedding_provider.dimensions,
        }

    is_pg = db.bind is not None and db.bind.dialect.name == "postgresql"
    batch_size = 32
    indexed = 0
    for start in range(0, len(to_index), batch_size):
        batch = to_index[start : start + batch_size]
        emb = await embedding_provider.embed_texts([c.extracted_text for c in batch])
        for ch, vec in zip(batch, emb.vectors):
            ch.embedding_json = vec
            ch.embedding_model = emb.model
            ch.embedding_dim = emb.dimensions
            if is_pg:
                await db.execute(
                    sa.text(
                        "UPDATE document_chunks "
                        "SET embedding = CAST(:vec AS vector) WHERE id = :id"
                    ),
                    {"vec": _vector_literal(vec), "id": ch.id},
                )
            indexed += 1

    await db.flush()
    return {
        "case_id": case_id,
        "total_chunks": len(chunks),
        "indexed_chunks": indexed,
        "embedding_provider": embedding_provider.name,
        "embedding_model": embedding_provider.model,
        "dimensions": embedding_provider.dimensions,
    }
