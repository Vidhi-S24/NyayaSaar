"""Hybrid legal retrieval & legal-source endpoints (Stage 7)."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.base import ProviderError, ProviderNotConfiguredError
from app.ai.embeddings import get_embedding_provider
from app.config import get_settings
from app.db.models.legal_record import LegalRecord
from app.db.models.user import User
from app.db.session import get_async_session
from app.models.responses import ApiResponse
from app.schemas.retrieval import (
    CaseIndexResponse,
    LegalRecordChunkResponse,
    LegalRecordDetailResponse,
    LegalRecordIngestRequest,
    RetrievalResultItemResponse,
    RetrievalSearchRequest,
    RetrievalSearchResponse,
    RetrievalStatusResponse,
)
from app.services.auth import get_current_user
from app.services.legal_corpus import get_corpus_provider
from app.services.retrieval import (
    RetrievalFilters,
    hybrid_search,
    index_case_documents,
    ingest_legal_record,
)

logger = logging.getLogger("nyayasaar.routers.retrieval")

router = APIRouter(
    prefix="/retrieval",
    tags=["retrieval"],
)


def _safe_embedding_provider(settings):
    try:
        return get_embedding_provider(settings)
    except ProviderNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=exc.message,
        )


@router.get("/status", response_model=ApiResponse[RetrievalStatusResponse])
async def retrieval_status(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> ApiResponse[RetrievalStatusResponse]:
    """Return safe retrieval & legal-source configuration status (never keys)."""
    settings = get_settings()
    try:
        emb = get_embedding_provider(settings)
    except ProviderNotConfiguredError:
        emb = None

    corpus = get_corpus_provider(settings, allow_fixture=True)
    is_pg = db.bind is not None and db.bind.dialect.name == "postgresql"

    return ApiResponse.ok(
        RetrievalStatusResponse(
            embedding_provider=emb.name if emb else "none",
            embedding_model=emb.model if emb else None,
            embedding_dimensions=settings.retrieval_embedding_dim,
            embeddings_enabled=emb is not None,
            vector_backend="pgvector" if is_pg else "sqlite_json",
            corpus_provider=corpus.name,
            corpus_configured=corpus.configured,
            fixture_active=not corpus.configured,
            rerank_enabled=settings.retrieval_rerank_enabled,
            max_query_chars=settings.retrieval_max_query_chars,
            max_limit=settings.retrieval_max_limit,
        )
    )


@router.post("/search", response_model=ApiResponse[RetrievalSearchResponse])
async def search_retrieval(
    body: RetrievalSearchRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> ApiResponse[RetrievalSearchResponse]:
    """Run hybrid (lexical + semantic + RRF) retrieval across permitted sources."""
    settings = get_settings()
    emb = _safe_embedding_provider(settings)

    filters = RetrievalFilters(
        case_id=body.filters.case_id,
        source_type=body.filters.source_type,
        jurisdiction=body.filters.jurisdiction,
        court=body.filters.court,
        date_from=body.filters.date_from,
        date_to=body.filters.date_to,
        source_provider=body.filters.source_provider,
    )

    try:
        output = await hybrid_search(
            db,
            user_id=current_user.id,
            query=body.query,
            filters=filters,
            settings=settings,
            embedding_provider=emb,
            limit=body.limit,
            use_rerank=body.use_rerank,
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found.",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except ProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=exc.message,
        )

    return ApiResponse.ok(
        RetrievalSearchResponse(
            query=output.query,
            items=[
                RetrievalResultItemResponse(
                    result_id=item.result_id,
                    source_type=item.source_type,
                    source_id=item.source_id,
                    title=item.title,
                    text=item.text,
                    case_id=item.case_id,
                    document_id=item.document_id,
                    record_id=item.record_id,
                    citation=item.citation,
                    page_number=item.page_number,
                    paragraph_number=item.paragraph_number,
                    jurisdiction=item.jurisdiction,
                    court=item.court,
                    decision_date=item.decision_date,
                    source_url=item.source_url,
                    source_provider=item.source_provider,
                    lexical_score=item.lexical_score,
                    semantic_score=item.semantic_score,
                    hybrid_score=item.hybrid_score,
                    rerank_score=item.rerank_score,
                    is_fixture=item.is_fixture,
                    has_injection_signals=item.has_injection_signals,
                    metadata=item.metadata,
                )
                for item in output.items
            ],
            total_candidates=output.total_candidates,
            deduplicated_count=output.deduplicated_count,
            retrieval_method=output.retrieval_method,
            embedding_provider=output.embedding_provider,
            embedding_model=output.embedding_model,
            corpus_provider=output.corpus_provider,
            corpus_configured=output.corpus_configured,
            fixture_used=output.fixture_used,
            reranked=output.reranked,
            notes=output.notes,
        )
    )


@router.post(
    "/cases/{case_id}/index",
    response_model=ApiResponse[CaseIndexResponse],
)
async def index_case(
    case_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
    force: bool = False,
) -> ApiResponse[CaseIndexResponse]:
    """Generate and persist embeddings for ready document chunks in an owned case."""
    settings = get_settings()
    emb = _safe_embedding_provider(settings)
    try:
        stats = await index_case_documents(
            db,
            case_id=case_id,
            user_id=current_user.id,
            embedding_provider=emb,
            force=force,
        )
        await db.commit()
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Case not found."
        )
    except ProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.message
        )

    return ApiResponse.ok(CaseIndexResponse(**stats))


@router.post(
    "/records",
    response_model=ApiResponse[LegalRecordDetailResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_legal_record(
    body: LegalRecordIngestRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> ApiResponse[LegalRecordDetailResponse]:
    """Ingest operator-supplied legal material with chunking, provenance, and embeddings."""
    settings = get_settings()
    emb = _safe_embedding_provider(settings)
    try:
        record = await ingest_legal_record(
            db,
            owner_id=current_user.id,
            title=body.title,
            text=body.text,
            source_provider=body.source_provider,
            external_id=body.external_id,
            citation=body.citation,
            jurisdiction=body.jurisdiction,
            court=body.court,
            decision_date=body.decision_date,
            year=body.year,
            source_url=body.source_url,
            summary=body.summary,
            metadata=body.metadata,
            page_number=body.page_number,
            embedding_provider=emb,
        )
        await db.commit()
    except ProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.message
        )

    loaded = (
        await db.execute(
            select(LegalRecord)
            .options(selectinload(LegalRecord.chunks))
            .where(LegalRecord.id == record.id)
        )
    ).scalar_one()
    return ApiResponse.ok(_record_to_detail(loaded))


@router.get(
    "/records/{record_id}",
    response_model=ApiResponse[LegalRecordDetailResponse],
)
async def get_legal_record(
    record_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> ApiResponse[LegalRecordDetailResponse]:
    """Inspect a stored legal record and its chunks."""
    record = (
        await db.execute(
            select(LegalRecord)
            .options(selectinload(LegalRecord.chunks))
            .where(LegalRecord.id == record_id)
        )
    ).scalar_one_or_none()
    if record is None or (
        record.owner_id is not None and record.owner_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Legal record not found.",
        )
    return ApiResponse.ok(_record_to_detail(record))


def _record_to_detail(record: LegalRecord) -> LegalRecordDetailResponse:
    return LegalRecordDetailResponse(
        id=record.id,
        source_provider=record.source_provider,
        external_id=record.external_id,
        title=record.title,
        citation=record.citation,
        jurisdiction=record.jurisdiction,
        court=record.court,
        decision_date=record.decision_date,
        year=record.year,
        source_url=record.source_url,
        summary=record.summary,
        is_fixture=record.is_fixture,
        metadata=record.metadata_json or {},
        chunks=[
            LegalRecordChunkResponse(
                id=c.id,
                chunk_index=c.chunk_index,
                page_number=c.page_number,
                paragraph_number=c.paragraph_number,
                text=c.text,
                char_count=c.char_count,
            )
            for c in sorted(record.chunks, key=lambda x: x.chunk_index)
        ],
    )
