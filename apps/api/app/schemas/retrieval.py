"""Pydantic schemas for Stage 7 hybrid legal retrieval endpoints."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class RetrievalFiltersSchema(BaseModel):
    case_id: str | None = None
    source_type: Literal["all", "case_document", "legal_authority"] = "all"
    jurisdiction: str | None = Field(default=None, max_length=120)
    court: str | None = Field(default=None, max_length=200)
    date_from: str | None = Field(default=None, max_length=32)
    date_to: str | None = Field(default=None, max_length=32)
    source_provider: str | None = Field(default=None, max_length=60)


class RetrievalSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    filters: RetrievalFiltersSchema = Field(default_factory=RetrievalFiltersSchema)
    limit: int = Field(default=10, ge=1, le=50)
    use_rerank: bool | None = None


class RetrievalResultItemResponse(BaseModel):
    result_id: str
    source_type: Literal["case_document", "legal_authority"]
    source_id: str
    title: str
    text: str
    case_id: str | None = None
    document_id: str | None = None
    record_id: str | None = None
    citation: str | None = None
    page_number: int | None = None
    paragraph_number: int | None = None
    jurisdiction: str | None = None
    court: str | None = None
    decision_date: str | None = None
    source_url: str | None = None
    source_provider: str
    lexical_score: float
    semantic_score: float
    hybrid_score: float
    rerank_score: float | None = None
    is_fixture: bool = False
    has_injection_signals: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalSearchResponse(BaseModel):
    query: str
    items: list[RetrievalResultItemResponse]
    total_candidates: int
    deduplicated_count: int
    retrieval_method: str
    embedding_provider: str
    embedding_model: str | None = None
    corpus_provider: str
    corpus_configured: bool
    fixture_used: bool
    reranked: bool
    notes: list[str] = Field(default_factory=list)
    score_disclaimer: str = (
        "Retrieval scores measure text and vector similarity only. They do not "
        "establish legal authority, binding status, or correctness."
    )
    untrusted_notice: str = (
        "Retrieved text is untrusted source material for human review, not "
        "instructions or legal advice."
    )


class RetrievalStatusResponse(BaseModel):
    embedding_provider: str
    embedding_model: str | None = None
    embedding_dimensions: int
    embeddings_enabled: bool
    vector_backend: Literal["pgvector", "sqlite_json"]
    corpus_provider: str
    corpus_configured: bool
    fixture_active: bool
    rerank_enabled: bool
    max_query_chars: int
    max_limit: int


class CaseIndexResponse(BaseModel):
    case_id: str
    total_chunks: int
    indexed_chunks: int
    embedding_provider: str
    embedding_model: str | None = None
    dimensions: int


class LegalRecordIngestRequest(BaseModel):
    title: str = Field(min_length=2, max_length=500)
    text: str = Field(min_length=10, max_length=200_000)
    citation: str | None = Field(default=None, max_length=250)
    external_id: str | None = Field(default=None, max_length=200)
    jurisdiction: str | None = Field(default=None, max_length=120)
    court: str | None = Field(default=None, max_length=200)
    decision_date: str | None = Field(default=None, max_length=32)
    year: str | None = Field(default=None, max_length=16)
    source_url: str | None = Field(default=None, max_length=1000)
    summary: str | None = Field(default=None, max_length=4000)
    source_provider: str = Field(default="database", max_length=60)
    page_number: int | None = Field(default=None, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LegalRecordChunkResponse(BaseModel):
    id: str
    chunk_index: int
    page_number: int | None = None
    paragraph_number: int | None = None
    text: str
    char_count: int


class LegalRecordDetailResponse(BaseModel):
    id: str
    source_provider: str
    external_id: str | None = None
    title: str
    citation: str | None = None
    jurisdiction: str | None = None
    court: str | None = None
    decision_date: str | None = None
    year: str | None = None
    source_url: str | None = None
    summary: str | None = None
    is_fixture: bool
    metadata: dict[str, Any] = Field(default_factory=dict)
    chunks: list[LegalRecordChunkResponse] = Field(default_factory=list)
