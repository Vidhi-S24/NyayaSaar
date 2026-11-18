"""
NyayaSaar API — Document service (business logic layer).

All authorization is enforced here — not just in routers.
Every operation requires case ownership to be verified before proceeding.

Security:
- Extracted text is never logged (may contain sensitive legal content).
- Failure reasons are sanitised before storage (no raw exception messages).
- Storage keys are always generated server-side from UUIDs.
- File bytes are discarded from memory immediately after storage and extraction.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import Document, DocumentChunk
from app.db.models.case import Case
from app.schemas.documents import DocumentCreate
from app.services.extraction import ExtractionResult, extract_document
from app.services.storage import StorageProvider, make_storage_key

logger = logging.getLogger("nyayasaar.documents")

# Maximum retry attempts before marking as permanently failed
MAX_RETRY_ATTEMPTS = 3


# ---------------------------------------------------------------------------
# Authorization helper
# ---------------------------------------------------------------------------


async def _get_owned_case(
    db: AsyncSession, case_id: str, user_id: str
) -> Case | None:
    """
    Return the case if the user owns it, else None.
    Intentionally indistinguishable from "not found" to prevent leakage.
    """
    result = await db.execute(
        select(Case).where(Case.id == case_id, Case.owner_id == user_id)
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Create / upload
# ---------------------------------------------------------------------------


async def create_document(
    db: AsyncSession,
    *,
    case_id: str,
    user_id: str,
    original_name: str,
    content_type: str,  # detected, not client-supplied
    extension: str,
    file_bytes: bytes,
    storage: StorageProvider,
    max_docs_per_case: int = 100,
) -> Document:
    """
    Persist document metadata and store the raw file.
    Returns the Document object in 'pending' state.
    Extraction is performed synchronously in process_document().
    """
    # Authorization
    case = await _get_owned_case(db, case_id, user_id)
    if case is None:
        raise PermissionError("Case not found or access denied.")

    # Document count guard
    count_result = await db.execute(
        select(func.count()).select_from(
            select(Document).where(Document.case_id == case_id).subquery()
        )
    )
    count = count_result.scalar_one()
    if count >= max_docs_per_case:
        raise ValueError(
            f"This case already has {count} documents (limit: {max_docs_per_case})."
        )

    document_id = str(uuid.uuid4())
    storage_key = make_storage_key(case_id, document_id, extension)

    # Store file bytes — do this before the DB record so we can clean up on failure
    try:
        storage.save(storage_key, file_bytes, content_type)
    except Exception as exc:
        # Do not log file content; log a sanitised message
        logger.error(
            "Storage.save failed for document %s in case %s: %s",
            document_id, case_id, type(exc).__name__,
        )
        raise RuntimeError("Could not save the uploaded file. Please try again.") from exc

    doc = Document(
        id=document_id,
        case_id=case_id,
        owner_id=user_id,
        original_name=original_name[:500],  # truncate; name is display-only
        storage_key=storage_key,
        content_type=content_type,
        file_size=len(file_bytes),
        processing_status="pending",
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)

    # Increment the case document count
    case.documents_count = (case.documents_count or 0) + 1
    await db.flush()

    logger.info(
        "Document created: id=%s case=%s size=%d content_type=%s",
        document_id, case_id, len(file_bytes), content_type,
    )
    return doc


# ---------------------------------------------------------------------------
# Extraction / processing
# ---------------------------------------------------------------------------


async def process_document(
    db: AsyncSession,
    *,
    document: Document,
    file_bytes: bytes,
) -> Document:
    """
    Extract text from file_bytes and persist chunks.

    Sets processing_status to 'ready' on success, 'failed' on unrecoverable error.
    Partial extraction (e.g. scanned PDF) results in status 'ready' with
    is_ocr_required=True and a failure_reason describing the gap.

    Security: extracted text is never logged.
    """
    # Mark as in-progress
    document.processing_status = "processing"
    document.processing_started_at = datetime.now(timezone.utc)
    document.retry_count = (document.retry_count or 0) + 1
    await db.flush()

    try:
        result: ExtractionResult = extract_document(file_bytes, document.content_type)
    except Exception as exc:
        # Extraction raised unexpectedly; sanitise before storing
        logger.error(
            "Extraction raised unexpectedly for document %s: %s",
            document.id, type(exc).__name__,
        )
        await _mark_failed(
            db, document, "An unexpected error occurred during text extraction."
        )
        return document

    if not result.pages and not result.is_ocr_required:
        await _mark_failed(
            db,
            document,
            result.failure_reason or "No text could be extracted from the document.",
        )
        return document

    # Persist chunks (upsert by page_number; delete existing to handle retries cleanly)
    await _clear_chunks(db, document.id)
    for page in result.pages:
        chunk = DocumentChunk(
            id=str(uuid.uuid4()),
            document_id=document.id,
            page_number=page.page_number,
            extracted_text=page.text,
            char_count=page.char_count,
        )
        db.add(chunk)

    # Update document metadata
    document.page_count = result.total_page_count
    document.is_ocr_required = result.is_ocr_required
    document.extraction_completeness = result.completeness_pct
    document.failure_reason = result.failure_reason  # None if fully successful
    document.processing_completed_at = datetime.now(timezone.utc)

    # Mark ready even for partial extraction (OCR flagged) so the UI can proceed
    document.processing_status = "ready"
    await db.flush()

    logger.info(
        "Document processed: id=%s pages=%d/%d ocr=%s complete=%s%%",
        document.id,
        len(result.pages),
        result.total_page_count,
        result.is_ocr_required,
        result.completeness_pct,
    )
    return document


async def _mark_failed(
    db: AsyncSession, document: Document, reason: str
) -> None:
    document.processing_status = "failed"
    document.failure_reason = reason[:2000]  # Bounded
    document.processing_completed_at = datetime.now(timezone.utc)
    await db.flush()


async def _clear_chunks(db: AsyncSession, document_id: str) -> None:
    """Remove existing chunks before re-extraction (for safe retries)."""
    result = await db.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == document_id)
    )
    for chunk in result.scalars():
        await db.delete(chunk)
    await db.flush()


# ---------------------------------------------------------------------------
# Retry
# ---------------------------------------------------------------------------


async def retry_document(
    db: AsyncSession,
    *,
    document_id: str,
    user_id: str,
    storage: StorageProvider,
) -> Document | None:
    """
    Retry extraction for a failed document.
    Returns the updated Document, or None if not found/unauthorised.
    Bounded by MAX_RETRY_ATTEMPTS.
    """
    doc = await get_document(db, document_id=document_id, user_id=user_id)
    if doc is None:
        return None
    if doc.processing_status not in ("failed", "pending"):
        raise ValueError(
            f"Document is in state '{doc.processing_status}'; only 'failed' or 'pending' documents can be retried."
        )
    if (doc.retry_count or 0) >= MAX_RETRY_ATTEMPTS:
        raise ValueError(
            f"Document has reached the maximum retry limit ({MAX_RETRY_ATTEMPTS}). "
            "Please re-upload the file."
        )

    try:
        file_bytes = storage.load(doc.storage_key)
    except FileNotFoundError:
        await _mark_failed(db, doc, "Stored file not found; please re-upload.")
        return doc

    return await process_document(db, document=doc, file_bytes=file_bytes)


# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------


async def get_document(
    db: AsyncSession, *, document_id: str, user_id: str
) -> Document | None:
    """Return document if user is the owner; else None."""
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.owner_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def list_documents(
    db: AsyncSession,
    *,
    case_id: str,
    user_id: str,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Document], int]:
    """
    List documents for a case the user owns.
    Returns (documents, total_count).
    """
    # Verify case ownership
    case = await _get_owned_case(db, case_id, user_id)
    if case is None:
        return [], 0

    base_q = select(Document).where(Document.case_id == case_id)
    count_q = select(func.count()).select_from(base_q.subquery())
    total_result = await db.execute(count_q)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    rows_q = base_q.order_by(Document.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(rows_q)
    docs = list(result.scalars().all())
    return docs, total


async def get_document_chunks(
    db: AsyncSession,
    *,
    document_id: str,
    user_id: str,
    page_number: int | None = None,
) -> list[DocumentChunk]:
    """
    Return extracted chunks for a document the user owns.
    Optionally filtered to a single page.
    """
    doc = await get_document(db, document_id=document_id, user_id=user_id)
    if doc is None:
        return []

    q = select(DocumentChunk).where(DocumentChunk.document_id == document_id)
    if page_number is not None:
        q = q.where(DocumentChunk.page_number == page_number)
    q = q.order_by(DocumentChunk.page_number)
    result = await db.execute(q)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


async def delete_document(
    db: AsyncSession,
    *,
    document_id: str,
    user_id: str,
    storage: StorageProvider,
) -> bool:
    """
    Delete document metadata, all chunks, and stored file content.
    Returns True if deleted, False if not found/unauthorised.

    Storage deletion is best-effort: a storage failure is logged but does not
    prevent DB record removal (the orphan can be cleaned up by an admin tool).
    """
    doc = await get_document(db, document_id=document_id, user_id=user_id)
    if doc is None:
        return False

    case_id = doc.case_id
    storage_key = doc.storage_key

    # Delete DB record (cascades to chunks via FK)
    await db.delete(doc)
    await db.flush()

    # Update case document count
    case_result = await db.execute(
        select(Case).where(Case.id == case_id)
    )
    case = case_result.scalar_one_or_none()
    if case is not None:
        case.documents_count = max(0, (case.documents_count or 1) - 1)
        await db.flush()

    # Remove stored file (best-effort — log but don't raise)
    try:
        storage.delete(storage_key)
    except Exception as exc:
        logger.warning(
            "Storage.delete failed for key %r: %s — orphan may remain",
            storage_key,
            type(exc).__name__,
        )

    logger.info("Document deleted: id=%s case=%s", document_id, case_id)
    return True
