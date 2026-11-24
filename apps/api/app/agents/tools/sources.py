"""Source-loading and source-verification tools.

Document text is untrusted. These tools only read it, bound it, and compare
quotes against it. They never interpret document text as instructions.

Stage 6 additions:
* deterministic duplicate-page suppression so the same text is not sent to the
  model twice (within a document or across documents);
* round-robin page selection so a multi-document case is not exhausted by the
  first file;
* source-quality statistics (short pages, OCR/failed documents, truncation);
* character spans for verified quotes, used by the source viewer.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.tools.injection import find_instruction_like_text
from app.db.models.document import Document, DocumentChunk

MIN_VERIFIABLE_QUOTE_CHARS = 8
MIN_USABLE_PAGE_CHARS = 80
MIN_DUPLICATE_TEXT_CHARS = 80


@dataclass(slots=True)
class SourceExcerpt:
    """A bounded, page-referenced excerpt supplied to an analyst."""

    source_id: str
    document_id: str
    document_name: str
    page_number: int
    text: str
    truncated: bool = False
    short: bool = False
    instruction_like: bool = False

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class SourceLoadResult:
    sources: list[SourceExcerpt]
    notes: list[str]
    stats: dict[str, int]


def normalize_text(text: str) -> str:
    """Whitespace- and case-normalised text for quote comparison."""
    return " ".join((text or "").split()).casefold()


def _digest(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


async def load_case_sources(
    db: AsyncSession,
    *,
    case_id: str,
    user_id: str,
    document_ids: list[str] | None = None,
    max_chars: int = 24_000,
    per_page_chars: int = 4_000,
) -> SourceLoadResult:
    """Load ready documents for an owned case into bounded page excerpts.

    Pages are selected round-robin across documents so a long first document
    cannot starve the rest of the case. Exact duplicate page text is skipped and
    reported. Every note explains an omission so the report can be honest about
    incomplete coverage.
    """
    notes: list[str] = []
    max_chars = max(1_000, max_chars)
    per_page_chars = max(500, per_page_chars)
    stats = {
        "documents_available": 0,
        "documents_analyzed": 0,
        "pages_available": 0,
        "pages_included": 0,
        "characters_included": 0,
        "duplicate_pages_skipped": 0,
        "short_pages": 0,
        "truncated_pages": 0,
        "omitted_pages": 0,
        "failed_documents": 0,
        "ocr_required_documents": 0,
        "incomplete_extraction_documents": 0,
        "instruction_like_sources": 0,
    }

    docs_result = await db.execute(
        select(Document)
        .where(Document.case_id == case_id, Document.owner_id == user_id)
        .order_by(Document.created_at.asc())
    )
    all_docs = list(docs_result.scalars().all())
    stats["documents_available"] = len(all_docs)
    if not all_docs:
        return SourceLoadResult(
            [], ["No documents are attached to this case."], stats
        )

    ready_docs = [d for d in all_docs if d.processing_status == "ready"]
    stats["failed_documents"] = sum(
        1 for d in all_docs if d.processing_status == "failed"
    )
    stats["ocr_required_documents"] = sum(
        1 for d in all_docs if d.is_ocr_required
    )
    stats["incomplete_extraction_documents"] = sum(
        1
        for d in ready_docs
        if d.extraction_completeness is not None and d.extraction_completeness < 100
    )

    skipped = len(all_docs) - len(ready_docs)
    if skipped:
        notes.append(
            f"{skipped} document(s) were skipped because text extraction is not "
            "complete (failed or OCR required)."
        )
    if stats["incomplete_extraction_documents"]:
        notes.append(
            f"{stats['incomplete_extraction_documents']} document(s) have partial "
            "text extraction; the analysis may not cover every page."
        )

    if document_ids:
        requested = set(document_ids)
        ready_docs = [d for d in ready_docs if d.id in requested]
        missing = requested - {d.id for d in ready_docs}
        if missing:
            notes.append(
                f"{len(missing)} selected document(s) were unavailable or not ready."
            )

    if not ready_docs:
        return SourceLoadResult(
            [],
            notes + ["No documents with completed text extraction were available."],
            stats,
        )

    # Load every page first so selection can be fair across documents.
    queues: dict[str, list[DocumentChunk]] = {}
    for doc in ready_docs:
        chunks_result = await db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == doc.id)
            .order_by(DocumentChunk.page_number.asc())
        )
        chunks = list(chunks_result.scalars().all())
        stats["pages_available"] += len(chunks)
        if not chunks:
            notes.append(
                f"'{doc.original_name}' has no extracted text and was skipped."
            )
            continue
        queues[doc.id] = chunks

    if not queues:
        return SourceLoadResult(
            [], notes + ["No usable extracted text was available for analysis."], stats
        )

    sources: list[SourceExcerpt] = []
    seen_pages: set[str] = set()
    remaining = max_chars
    counter = 1
    instruction_note_added = False

    while remaining > 0 and queues:
        progressed = False
        for doc_id in list(queues.keys()):
            if remaining <= 0:
                break
            queue = queues.get(doc_id)
            if not queue:
                queues.pop(doc_id, None)
                continue

            chunk = queue.pop(0)
            progressed = True
            if not queue:
                queues.pop(doc_id, None)

            text = chunk.extracted_text or ""
            normalized = normalize_text(text)
            if not normalized:
                continue

            digest = _digest(text)
            if (
                len(normalized) >= MIN_DUPLICATE_TEXT_CHARS
                and digest in seen_pages
            ):
                stats["duplicate_pages_skipped"] += 1
                continue
            seen_pages.add(digest)

            take = min(len(text), per_page_chars, remaining)
            if take <= 0:
                continue
            truncated = take < len(text)
            excerpt_text = text[:take]
            short = len(normalized) < MIN_USABLE_PAGE_CHARS
            instruction_hits = (
                find_instruction_like_text(excerpt_text) if excerpt_text else []
            )
            instruction_like = bool(instruction_hits)
            if instruction_like:
                stats["instruction_like_sources"] += 1
                if not instruction_note_added:
                    notes.append(
                        "One or more source pages contain instruction-like language. "
                        "It was treated strictly as evidence; any embedded instruction "
                        "was ignored."
                    )
                    instruction_note_added = True

            doc = next((d for d in ready_docs if d.id == doc_id), None)
            sources.append(
                SourceExcerpt(
                    source_id=f"S{counter}",
                    document_id=doc_id,
                    document_name=doc.original_name if doc else "document",
                    page_number=chunk.page_number,
                    text=excerpt_text,
                    truncated=truncated,
                    short=short,
                    instruction_like=instruction_like,
                )
            )
            counter += 1
            remaining -= len(excerpt_text)
            stats["characters_included"] += len(excerpt_text)
            if truncated:
                stats["truncated_pages"] += 1
            if short:
                stats["short_pages"] += 1

        if not progressed:
            break

    if remaining <= 0:
        notes.append(
            "Some pages were omitted because the source budget was exhausted."
        )
    if stats["duplicate_pages_skipped"]:
        notes.append(
            f"{stats['duplicate_pages_skipped']} duplicate page(s) were skipped and "
            "not sent to the model twice."
        )
    if stats["truncated_pages"]:
        notes.append(
            "One or more source excerpts were truncated to fit the analysis budget."
        )
    if stats["short_pages"]:
        notes.append(
            f"{stats['short_pages']} page(s) contain very little extracted text; "
            "they may be scans or partially extracted pages."
        )
    if not sources:
        notes.append("No usable extracted text was available for analysis.")

    stats["pages_included"] = len(sources)
    stats["documents_analyzed"] = len({s.document_id for s in sources})
    stats["omitted_pages"] = max(
        0,
        stats["pages_available"]
        - stats["pages_included"]
        - stats["duplicate_pages_skipped"],
    )
    return SourceLoadResult(sources, notes, stats)


def sources_from_state(raw: list[dict[str, object]]) -> list[SourceExcerpt]:
    """Convert serialised state sources (plain dicts) to SourceExcerpt objects."""
    return [
        SourceExcerpt(
            source_id=str(s["source_id"]),
            document_id=str(s["document_id"]),
            document_name=str(s["document_name"]),
            page_number=int(s["page_number"]),
            text=str(s.get("text", "")),
            truncated=bool(s.get("truncated", False)),
            short=bool(s.get("short", False)),
            instruction_like=bool(s.get("instruction_like", False)),
        )
        for s in raw
    ]


def _quote_pattern(quote: str) -> re.Pattern[str] | None:
    cleaned = " ".join((quote or "").split())
    if len(cleaned) < MIN_VERIFIABLE_QUOTE_CHARS:
        return None
    parts = [re.escape(part) for part in cleaned.split(" ")]
    return re.compile(r"\s+".join(parts), re.IGNORECASE)


def find_quote_span(quote: str | None, source_text: str) -> tuple[int, int] | None:
    """Locate a quote in the excerpt and return original-text offsets.

    Whitespace is normalised in the pattern, so a quote that differs only in
    spacing or case still maps to a real span. The offsets are relative to the
    supplied excerpt (the first N characters of the page).
    """
    pattern = _quote_pattern(quote or "")
    if pattern is None:
        return None
    match = pattern.search(source_text or "")
    if match is None:
        return None
    return match.start(), match.end()


def quote_in_source(quote: str | None, source_text: str) -> bool:
    """True when a model-supplied quote is a real substring of the source."""
    if not quote:
        return False
    normalized_quote = normalize_text(quote)
    if len(normalized_quote) < MIN_VERIFIABLE_QUOTE_CHARS:
        return False
    if normalized_quote in normalize_text(source_text):
        return True
    return find_quote_span(quote, source_text) is not None


def resolve_source(
    sources: list[SourceExcerpt] | list[dict[str, object]],
    source_id: str,
) -> SourceExcerpt | None:
    """Resolve an S-marker to its excerpt."""
    for source in sources:
        if isinstance(source, SourceExcerpt):
            if source.source_id == source_id:
                return source
        elif source.get("source_id") == source_id:
            return SourceExcerpt(
                source_id=str(source["source_id"]),
                document_id=str(source["document_id"]),
                document_name=str(source["document_name"]),
                page_number=int(source["page_number"]),
                text=str(source.get("text", "")),
                truncated=bool(source.get("truncated", False)),
                short=bool(source.get("short", False)),
                instruction_like=bool(source.get("instruction_like", False)),
            )
    return None
