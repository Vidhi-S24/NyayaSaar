"""Source-loading and source-verification tools.

Document text is untrusted. These tools only read it, bound it, and compare
quotes against it. They never interpret document text as instructions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import Document, DocumentChunk

MIN_VERIFIABLE_QUOTE_CHARS = 8


@dataclass(slots=True)
class SourceExcerpt:
    """A bounded, page-referenced excerpt supplied to the analyst."""

    source_id: str
    document_id: str
    document_name: str
    page_number: int
    text: str
    truncated: bool = False

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


async def load_case_sources(
    db: AsyncSession,
    *,
    case_id: str,
    user_id: str,
    document_ids: list[str] | None = None,
    max_chars: int = 24_000,
    per_page_chars: int = 4_000,
) -> tuple[list[SourceExcerpt], list[str]]:
    """Load ready documents for an owned case into bounded page excerpts.

    Returns ``(sources, notes)``. Notes explain omissions and truncation so the
    result can be honest about incomplete coverage.
    """
    notes: list[str] = []
    max_chars = max(1_000, max_chars)
    per_page_chars = max(500, per_page_chars)

    docs_result = await db.execute(
        select(Document)
        .where(Document.case_id == case_id, Document.owner_id == user_id)
        .order_by(Document.created_at.asc())
    )
    all_docs = list(docs_result.scalars().all())
    if not all_docs:
        return [], ["No documents are attached to this case."]

    ready_docs = [d for d in all_docs if d.processing_status == "ready"]
    skipped = len(all_docs) - len(ready_docs)
    if skipped:
        notes.append(
            f"{skipped} document(s) were skipped because text extraction is not complete."
        )

    if document_ids:
        requested = set(document_ids)
        ready_docs = [d for d in ready_docs if d.id in requested]
        missing = requested - {d.id for d in ready_docs}
        if missing:
            notes.append(
                f"{len(missing)} requested document(s) were unavailable or not ready."
            )

    if not ready_docs:
        return [], notes + ["No documents with completed text extraction were available."]

    sources: list[SourceExcerpt] = []
    remaining = max_chars
    counter = 1
    truncated_any = False

    _budget_note_added = False

    for doc in ready_docs:
        if remaining <= 0:
            notes.append("The source budget was exhausted before every document was read.")
            break

        chunks_result = await db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == doc.id)
            .order_by(DocumentChunk.page_number.asc())
        )
        chunks = list(chunks_result.scalars().all())
        if not chunks:
            notes.append(
                f"'{doc.original_name}' has no extracted text and was skipped."
            )
            continue

        for chunk in chunks:
            if remaining <= 0:
                break

            text = chunk.extracted_text or ""
            if not text.strip():
                continue

            take = min(len(text), per_page_chars, remaining)
            truncated = take < len(text)
            if truncated:
                truncated_any = True
            excerpt = text[:take]
            sources.append(
                SourceExcerpt(
                    source_id=f"S{counter}",
                    document_id=doc.id,
                    document_name=doc.original_name,
                    page_number=chunk.page_number,
                    text=excerpt,
                    truncated=truncated,
                )
            )
            counter += 1
            remaining -= len(excerpt)

        if remaining <= 0 and not _budget_note_added:
            notes.append(
                "Some pages were omitted because the source budget was exhausted."
            )
            _budget_note_added = True
            break

    if truncated_any:
        notes.append(
            "One or more source excerpts were truncated to fit the analysis budget."
        )
    if not sources:
        notes.append("No usable extracted text was available for analysis.")

    return sources, notes


def sources_from_state(raw: list[dict[str, object]]) -> list[SourceExcerpt]:
    """Convert serialised state sources (plain dicts) to SourceExcerpt objects.

    State sources are stored as JSON-serialisable dicts so they fit in the
    LangGraph checkpoint. Any node that needs typed SourceExcerpts calls this
    rather than duplicating the conversion logic.
    """
    return [
        SourceExcerpt(
            source_id=str(s["source_id"]),
            document_id=str(s["document_id"]),
            document_name=str(s["document_name"]),
            page_number=int(s["page_number"]),
            text=str(s.get("text", "")),
            truncated=bool(s.get("truncated", False)),
        )
        for s in raw
    ]


def normalize_text(text: str) -> str:
    """Whitespace- and case-normalised text for quote comparison."""
    return " ".join((text or "").split()).casefold()


def quote_in_source(quote: str | None, source_text: str) -> bool:
    """True when a model-supplied quote is a real substring of the source.

    Very short quotes are not accepted as verification: they match too easily
    and would give false confidence.
    """
    if not quote:
        return False
    normalized_quote = normalize_text(quote)
    if len(normalized_quote) < MIN_VERIFIABLE_QUOTE_CHARS:
        return False
    return normalized_quote in normalize_text(source_text)


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
            )
    return None
