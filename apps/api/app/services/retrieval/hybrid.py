"""Hybrid legal retrieval: PostgreSQL FTS + pgvector (or SQLite fallback) + RRF + rerank."""

from __future__ import annotations

import hashlib
import logging
import math
import re
from dataclasses import dataclass, field
from typing import Any, Literal

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.tools.injection import find_instruction_like_text
from app.ai.embeddings import EmbeddingProvider, cosine_similarity
from app.config import Settings
from app.db.models.case import Case
from app.db.models.document import Document, DocumentChunk
from app.db.models.legal_record import LegalRecord, LegalRecordChunk
from app.services.legal_corpus import get_corpus_provider

logger = logging.getLogger("nyayasaar.retrieval.hybrid")

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "in", "is", "of", "on", "or", "that", "the", "this", "to", "with",
}


def _tokens(text: str) -> list[str]:
    return [
        t
        for t in _TOKEN_RE.findall((text or "").casefold())
        if t not in _STOPWORDS and len(t) > 1
    ]


def _content_digest(text: str) -> str:
    return hashlib.sha256(" ".join((text or "").split()).encode("utf-8")).hexdigest()


@dataclass(slots=True)
class RetrievalFilters:
    case_id: str | None = None
    source_type: Literal["all", "case_document", "legal_authority"] = "all"
    jurisdiction: str | None = None
    court: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    source_provider: str | None = None


@dataclass(slots=True)
class RetrievedItem:
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
    source_provider: str = "unknown"
    lexical_score: float = 0.0
    semantic_score: float = 0.0
    hybrid_score: float = 0.0
    rerank_score: float | None = None
    is_fixture: bool = False
    has_injection_signals: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RetrievalOutput:
    query: str
    items: list[RetrievedItem]
    total_candidates: int
    deduplicated_count: int
    retrieval_method: str
    embedding_provider: str
    embedding_model: str | None
    corpus_provider: str
    corpus_configured: bool
    fixture_used: bool
    reranked: bool
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class _Candidate:
    item: RetrievedItem
    embedding: list[float] | None = None
    lexical_score: float = 0.0
    semantic_score: float = 0.0


def _bm25_scores(query: str, docs: list[str]) -> list[float]:
    """Deterministic BM25 lexical scoring over candidate texts."""
    q_tokens = _tokens(query)
    if not q_tokens or not docs:
        return [0.0] * len(docs)

    doc_tokens = [_tokens(d) for d in docs]
    n_docs = len(docs)
    avgdl = max(1.0, sum(len(dt) for dt in doc_tokens) / n_docs)
    k1 = 1.5
    b = 0.75

    df: dict[str, int] = {}
    for qt in set(q_tokens):
        df[qt] = sum(1 for dt in doc_tokens if qt in dt)

    scores: list[float] = []
    for dt in doc_tokens:
        dl = len(dt)
        if dl == 0:
            scores.append(0.0)
            continue
        tf_map: dict[str, int] = {}
        for tok in dt:
            tf_map[tok] = tf_map.get(tok, 0) + 1
        s = 0.0
        for qt in q_tokens:
            tf = tf_map.get(qt, 0)
            if tf == 0:
                continue
            idf = math.log((n_docs - df[qt] + 0.5) / (df[qt] + 0.5) + 1.0)
            denom = tf + k1 * (1.0 - b + b * (dl / avgdl))
            s += idf * ((tf * (k1 + 1.0)) / denom)
        scores.append(s)
    return scores


def combine_rrf(
    candidates: list[_Candidate],
    *,
    k: int = 60,
    w_lex: float = 0.5,
    w_sem: float = 0.5,
) -> list[_Candidate]:
    """Combine lexical and semantic rankings using Reciprocal Rank Fusion."""
    if not candidates:
        return []

    lex_ranked = sorted(
        [c for c in candidates if c.lexical_score > 0.0],
        key=lambda c: -c.lexical_score,
    )
    sem_ranked = sorted(
        [c for c in candidates if c.semantic_score > 0.0],
        key=lambda c: -c.semantic_score,
    )
    lex_rank = {id(c): idx + 1 for idx, c in enumerate(lex_ranked)}
    sem_rank = {id(c): idx + 1 for idx, c in enumerate(sem_ranked)}

    for c in candidates:
        r_lex = lex_rank.get(id(c))
        r_sem = sem_rank.get(id(c))
        score = 0.0
        if r_lex is not None:
            score += w_lex / (k + r_lex)
        if r_sem is not None:
            score += w_sem / (k + r_sem)
        c.item.lexical_score = round(c.lexical_score, 4)
        c.item.semantic_score = round(c.semantic_score, 4)
        c.item.hybrid_score = round(score, 6)

    # Filter out candidates that matched neither lexical nor semantic signals
    matched = [
        c for c in candidates if c.lexical_score > 0.0 or c.semantic_score > 0.0
    ]
    matched.sort(key=lambda c: (-c.item.hybrid_score, -c.lexical_score, -c.semantic_score))
    return matched


def rerank_candidates(query: str, candidates: list[_Candidate]) -> list[_Candidate]:
    """Deterministic lightweight reranker combining RRF score with phrase/term coverage."""
    q_clean = " ".join((query or "").casefold().split())
    q_tokens = set(_tokens(query))
    if not q_tokens:
        return candidates

    for c in candidates:
        haystack = f"{c.item.title} {c.item.citation or ''} {c.item.text}".casefold()
        h_tokens = set(_tokens(haystack))
        coverage = len(q_tokens & h_tokens) / len(q_tokens)
        phrase_boost = 0.2 if q_clean and q_clean in " ".join(haystack.split()) else 0.0
        rerank = c.item.hybrid_score * 10.0 + 0.5 * coverage + phrase_boost
        c.item.rerank_score = round(rerank, 4)

    candidates.sort(
        key=lambda c: (
            -(c.item.rerank_score or 0.0),
            -c.item.hybrid_score,
        )
    )
    return candidates


async def _load_case_candidates(
    db: AsyncSession,
    *,
    user_id: str,
    case_id: str,
    max_candidates: int,
    query: str,
    query_vec: list[float] | None,
) -> list[_Candidate]:
    case_res = await db.execute(
        select(Case).where(Case.id == case_id, Case.owner_id == user_id)
    )
    case = case_res.scalar_one_or_none()
    if case is None:
        raise PermissionError("Case not found or access denied.")

    is_pg = db.bind is not None and db.bind.dialect.name == "postgresql"
    candidates: list[_Candidate] = []

    if is_pg:
        # Native PostgreSQL FTS + pgvector candidate retrieval
        q_vec_str = (
            "[" + ",".join(f"{v:.6f}" for v in query_vec) + "]"
            if query_vec
            else None
        )
        sql = """
            SELECT
                dc.id,
                dc.document_id,
                dc.page_number,
                dc.extracted_text,
                d.original_name,
                d.case_id,
                c.court,
                c.jurisdiction,
                COALESCE(ts_rank_cd(dc.search_tsv, plainto_tsquery('english', :q)), 0.0) AS lex_score,
                CASE
                    WHEN :has_vec AND dc.embedding IS NOT NULL
                    THEN GREATEST(0.0, 1.0 - (dc.embedding <=> CAST(:qvec AS vector)))
                    ELSE 0.0
                END AS sem_score
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            JOIN cases c ON c.id = d.case_id
            WHERE d.case_id = :case_id
              AND d.owner_id = :user_id
              AND d.processing_status = 'ready'
            LIMIT :max_c
        """
        rows = (
            await db.execute(
                sa.text(sql),
                {
                    "q": query,
                    "has_vec": bool(q_vec_str),
                    "qvec": q_vec_str or "[]",
                    "case_id": case_id,
                    "user_id": user_id,
                    "max_c": max_candidates,
                },
            )
        ).mappings()
        for row in rows:
            text = str(row["extracted_text"])
            item = RetrievedItem(
                result_id=str(row["id"]),
                source_type="case_document",
                source_id=str(row["document_id"]),
                document_id=str(row["document_id"]),
                case_id=str(row["case_id"]),
                title=str(row["original_name"]),
                text=text,
                page_number=int(row["page_number"]),
                jurisdiction=row["jurisdiction"],
                court=row["court"],
                source_provider="case_document",
                is_fixture=False,
                has_injection_signals=bool(find_instruction_like_text(text)),
            )
            candidates.append(
                _Candidate(
                    item=item,
                    lexical_score=float(row["lex_score"] or 0.0),
                    semantic_score=float(row["sem_score"] or 0.0),
                )
            )
        return candidates

    # Portable SQLite / ORM path
    stmt = (
        select(DocumentChunk, Document)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            Document.case_id == case_id,
            Document.owner_id == user_id,
            Document.processing_status == "ready",
        )
        .order_by(Document.created_at.asc(), DocumentChunk.page_number.asc())
        .limit(max_candidates)
    )
    rows = (await db.execute(stmt)).all()
    for chunk, doc in rows:
        text = chunk.extracted_text
        item = RetrievedItem(
            result_id=chunk.id,
            source_type="case_document",
            source_id=doc.id,
            document_id=doc.id,
            case_id=doc.case_id,
            title=doc.original_name,
            text=text,
            page_number=chunk.page_number,
            jurisdiction=case.jurisdiction,
            court=case.court,
            source_provider="case_document",
            is_fixture=False,
            has_injection_signals=bool(find_instruction_like_text(text)),
        )
        candidates.append(_Candidate(item=item, embedding=chunk.embedding_json))
    return candidates


async def _load_db_legal_candidates(
    db: AsyncSession,
    *,
    filters: RetrievalFilters,
    max_candidates: int,
) -> list[_Candidate]:
    stmt = (
        select(LegalRecordChunk, LegalRecord)
        .join(LegalRecord, LegalRecord.id == LegalRecordChunk.record_id)
    )
    if filters.jurisdiction:
        stmt = stmt.where(
            LegalRecord.jurisdiction.ilike(f"%{filters.jurisdiction}%")
        )
    if filters.court:
        stmt = stmt.where(LegalRecord.court.ilike(f"%{filters.court}%"))
    if filters.date_from:
        stmt = stmt.where(LegalRecord.decision_date >= filters.date_from)
    if filters.date_to:
        stmt = stmt.where(LegalRecord.decision_date <= filters.date_to)
    if filters.source_provider:
        stmt = stmt.where(LegalRecord.source_provider == filters.source_provider)

    stmt = stmt.order_by(
        LegalRecord.created_at.desc(), LegalRecordChunk.chunk_index.asc()
    ).limit(max_candidates)
    rows = (await db.execute(stmt)).all()

    candidates: list[_Candidate] = []
    for chunk, rec in rows:
        item = RetrievedItem(
            result_id=chunk.id,
            source_type="legal_authority",
            source_id=rec.id,
            record_id=rec.id,
            title=rec.title,
            citation=rec.citation,
            text=chunk.text,
            page_number=chunk.page_number,
            paragraph_number=chunk.paragraph_number,
            jurisdiction=rec.jurisdiction,
            court=rec.court,
            decision_date=rec.decision_date,
            source_url=rec.source_url,
            source_provider=rec.source_provider,
            is_fixture=rec.is_fixture,
            has_injection_signals=bool(find_instruction_like_text(chunk.text)),
            metadata=rec.metadata_json or {},
        )
        candidates.append(_Candidate(item=item, embedding=chunk.embedding_json))
    return candidates


async def hybrid_search(
    db: AsyncSession,
    *,
    user_id: str,
    query: str,
    filters: RetrievalFilters,
    settings: Settings,
    embedding_provider: EmbeddingProvider | None,
    limit: int | None = None,
    use_rerank: bool | None = None,
) -> RetrievalOutput:
    """Execute hybrid (lexical + semantic + RRF + optional rerank) legal retrieval."""
    cleaned_query = (query or "").strip()
    if not cleaned_query:
        raise ValueError("Search query cannot be empty.")
    if len(cleaned_query) > settings.retrieval_max_query_chars:
        raise ValueError(
            f"Query exceeds maximum length of {settings.retrieval_max_query_chars} characters."
        )

    eff_limit = max(
        1,
        min(
            limit or settings.retrieval_default_limit,
            settings.retrieval_max_limit,
        ),
    )
    do_rerank = (
        settings.retrieval_rerank_enabled if use_rerank is None else use_rerank
    )

    query_vec: list[float] | None = None
    notes: list[str] = []
    if embedding_provider is not None:
        query_vec = await embedding_provider.embed_query(cleaned_query)

    candidates: list[_Candidate] = []
    is_pg = db.bind is not None and db.bind.dialect.name == "postgresql"

    # 1. Case documents (if case_id provided and source_type permits)
    if filters.case_id and filters.source_type in ("all", "case_document"):
        case_cands = await _load_case_candidates(
            db,
            user_id=user_id,
            case_id=filters.case_id,
            max_candidates=settings.retrieval_max_candidates,
            query=cleaned_query,
            query_vec=query_vec,
        )
        if filters.jurisdiction:
            case_cands = [
                c
                for c in case_cands
                if c.item.jurisdiction
                and filters.jurisdiction.casefold() in c.item.jurisdiction.casefold()
            ]
        if filters.court:
            case_cands = [
                c
                for c in case_cands
                if c.item.court
                and filters.court.casefold() in c.item.court.casefold()
            ]
        candidates.extend(case_cands)

    # 2. Ingested legal_records + configured legal-source provider
    corpus = get_corpus_provider(settings, allow_fixture=True)
    fixture_used = False
    if filters.source_type in ("all", "legal_authority"):
        db_cands = await _load_db_legal_candidates(
            db,
            filters=filters,
            max_candidates=settings.retrieval_max_candidates,
        )
        candidates.extend(db_cands)

        # Also query configured external/JSON/fixture corpus provider
        if (
            not filters.source_provider
            or filters.source_provider == corpus.name
        ):
            ext_records = await corpus.search_records(
                cleaned_query,
                limit=eff_limit * 2,
                jurisdiction=filters.jurisdiction,
                court=filters.court,
                date_from=filters.date_from,
                date_to=filters.date_to,
            )
            for rec in ext_records:
                if rec.is_fixture:
                    fixture_used = True
                item = RetrievedItem(
                    result_id=f"{rec.source_provider}:{rec.authority_id or rec.citation}",
                    source_type="legal_authority",
                    source_id=rec.authority_id or rec.citation,
                    record_id=rec.authority_id or None,
                    title=rec.title,
                    citation=rec.citation,
                    text=rec.text or rec.holding_summary,
                    page_number=rec.page_number,
                    paragraph_number=rec.paragraph_number,
                    jurisdiction=rec.jurisdiction or None,
                    court=rec.court or None,
                    decision_date=rec.decision_date or None,
                    source_url=rec.source_url or None,
                    source_provider=rec.source_provider,
                    is_fixture=rec.is_fixture,
                    has_injection_signals=bool(
                        find_instruction_like_text(rec.text or rec.holding_summary)
                    ),
                )
                candidates.append(_Candidate(item=item))

    # Score lexical & semantic signals where not already computed by PostgreSQL
    need_lex = [c for c in candidates if c.lexical_score == 0.0]
    if need_lex:
        lex_scores = _bm25_scores(
            cleaned_query,
            [f"{c.item.title} {c.item.citation or ''} {c.item.text}" for c in need_lex],
        )
        for c, sc in zip(need_lex, lex_scores):
            c.lexical_score = sc

    if query_vec is not None and embedding_provider is not None:
        # Compute missing embeddings in-memory for unindexed/external items
        need_emb = [
            c
            for c in candidates
            if c.semantic_score == 0.0 and c.embedding is None
        ]
        if need_emb:
            emb_res = await embedding_provider.embed_texts(
                [c.item.text for c in need_emb]
            )
            for c, vec in zip(need_emb, emb_res.vectors):
                c.embedding = vec

        for c in candidates:
            if c.semantic_score == 0.0 and c.embedding is not None:
                c.semantic_score = max(
                    0.0, cosine_similarity(query_vec, c.embedding)
                )

    total_candidates = len(candidates)
    fused = combine_rrf(
        candidates,
        k=settings.retrieval_rrf_k,
        w_lex=settings.retrieval_lexical_weight,
        w_sem=settings.retrieval_semantic_weight,
    )
    if do_rerank and fused:
        fused = rerank_candidates(cleaned_query, fused)

    # Deduplicate by provenance key + content digest
    seen_keys: set[tuple[Any, ...]] = set()
    seen_hashes: set[str] = set()
    final_items: list[RetrievedItem] = []
    deduped = 0

    for cand in fused:
        it = cand.item
        prov_key = (
            it.source_type,
            it.source_id,
            it.page_number,
            it.paragraph_number,
        )
        digest = _content_digest(it.text)
        if prov_key in seen_keys or digest in seen_hashes:
            deduped += 1
            continue
        seen_keys.add(prov_key)
        seen_hashes.add(digest)
        final_items.append(it)
        if len(final_items) >= eff_limit:
            break

    if fixture_used:
        notes.append(
            "No external legal corpus is configured; sample fixture authorities "
            "are clearly labelled and must not be treated as real legal authority."
        )

    method = (
        f"{'pg_fts+pgvector' if is_pg else 'bm25+cosine'}_rrf"
        + ("+rerank" if do_rerank else "")
    )
    return RetrievalOutput(
        query=cleaned_query,
        items=final_items,
        total_candidates=total_candidates,
        deduplicated_count=deduped,
        retrieval_method=method,
        embedding_provider=embedding_provider.name if embedding_provider else "none",
        embedding_model=embedding_provider.model if embedding_provider else None,
        corpus_provider=corpus.name,
        corpus_configured=corpus.configured,
        fixture_used=fixture_used,
        reranked=do_rerank and bool(final_items),
        notes=notes,
    )
