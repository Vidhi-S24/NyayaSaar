"""
NyayaSaar API — Documents router.

Endpoints:
  POST   /api/v1/cases/{case_id}/documents           Upload a document
  GET    /api/v1/cases/{case_id}/documents           List documents for a case
  GET    /api/v1/cases/{case_id}/documents/{doc_id}  Document metadata
  GET    /api/v1/cases/{case_id}/documents/{doc_id}/text   Extracted text preview
  POST   /api/v1/cases/{case_id}/documents/{doc_id}/retry  Retry failed extraction
  DELETE /api/v1/cases/{case_id}/documents/{doc_id}  Delete document

Authorization: every endpoint enforces case ownership server-side.

Security:
- File bytes are read once; discarded from local scope after storage/extraction.
- Extraction happens synchronously for now (D-020: justified below).
- Extracted text is never logged at INFO level; failures are sanitised.
- File size is validated before reading all bytes into memory.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models.user import User
from app.db.session import get_async_session
from app.models.responses import ApiResponse
from app.schemas.documents import (
    DocumentChunkResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentTextPreviewResponse,
)
from app.services.auth import get_current_user
from app.services import documents as doc_service
from app.services.extraction import validate_upload
from app.services.storage import get_storage

logger = logging.getLogger("nyayasaar.routers.documents")

router = APIRouter(
    prefix="/cases/{case_id}/documents",
    tags=["documents"],
)

settings = get_settings()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MAX_UPLOAD_BYTES = settings.max_upload_size_mb * 1024 * 1024


async def _read_upload_bounded(upload: UploadFile) -> bytes:
    """
    Read upload bytes with a size guard.
    Raises HTTPException 413 if the stream exceeds the limit.
    Reading in chunks avoids buffering an unlimited stream.
    """
    limit = _MAX_UPLOAD_BYTES
    buf = bytearray()
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > limit:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    f"File exceeds the maximum allowed size of "
                    f"{settings.max_upload_size_mb} MB."
                ),
            )
    return bytes(buf)


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


@router.post("", response_model=ApiResponse[DocumentResponse], status_code=201)
async def upload_document(
    case_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
    file: UploadFile = File(...),
) -> ApiResponse[DocumentResponse]:
    """
    Upload a PDF or DOCX document to a case.

    1. Validate extension, size, and magic bytes.
    2. Store the raw file via the storage provider.
    3. Persist document metadata (status=pending).
    4. Extract text synchronously (see D-020) and update status (ready/failed).

    Returns document metadata with the final processing status.
    """
    storage = get_storage()

    # Read bytes with size guard
    try:
        file_bytes = await _read_upload_bounded(file)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Failed to read upload stream: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not read the uploaded file.",
        )

    original_name = file.filename or "untitled"

    # Validate (extension + magic bytes; rejects client MIME type)
    try:
        extension, detected_mime = validate_upload(
            original_name, file_bytes, _MAX_UPLOAD_BYTES
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    # Create document record and store file
    try:
        doc = await doc_service.create_document(
            db,
            case_id=case_id,
            user_id=current_user.id,
            original_name=original_name,
            content_type=detected_mime,
            extension=extension,
            file_bytes=file_bytes,
            storage=storage,
            max_docs_per_case=settings.max_documents_per_case,
        )
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    # Extract text synchronously (D-020: document sizes are bounded; extraction
    # typically completes in <5s for the supported types at 50 MB limit)
    try:
        doc = await doc_service.process_document(
            db,
            document=doc,
            file_bytes=file_bytes,
        )
    except Exception as exc:
        logger.error(
            "process_document raised unexpectedly for %s: %s",
            doc.id, type(exc).__name__,
        )
        # Document remains in DB in 'failed' state; don't re-raise
    finally:
        # Discard bytes from local scope immediately
        del file_bytes

    return ApiResponse.ok(DocumentResponse.model_validate(doc))


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@router.get("", response_model=ApiResponse[DocumentListResponse])
async def list_documents(
    case_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> ApiResponse[DocumentListResponse]:
    """List all documents for a case the user owns."""
    docs, total = await doc_service.list_documents(
        db,
        case_id=case_id,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
    )
    return ApiResponse.ok(
        DocumentListResponse(
            items=[DocumentResponse.model_validate(d) for d in docs],
            total=total,
            page=page,
            page_size=page_size,
            has_next=(page * page_size) < total,
        )
    )


# ---------------------------------------------------------------------------
# Get metadata
# ---------------------------------------------------------------------------


@router.get("/{document_id}", response_model=ApiResponse[DocumentResponse])
async def get_document(
    case_id: str,
    document_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> ApiResponse[DocumentResponse]:
    """Get document metadata (no extracted text)."""
    doc = await doc_service.get_document(
        db, document_id=document_id, user_id=current_user.id
    )
    if doc is None or doc.case_id != case_id:
        raise HTTPException(status_code=404, detail="Document not found.")
    return ApiResponse.ok(DocumentResponse.model_validate(doc))


# ---------------------------------------------------------------------------
# Extracted text preview
# ---------------------------------------------------------------------------


@router.get("/{document_id}/text", response_model=ApiResponse[DocumentTextPreviewResponse])
async def get_document_text(
    case_id: str,
    document_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
    page: int | None = Query(default=None, ge=1, description="Filter to a specific page"),
    max_pages: int = Query(default=10, ge=1, le=50),
) -> ApiResponse[DocumentTextPreviewResponse]:
    """
    Return extracted text chunks for the document viewer.

    Pass ?page=N to view a specific page.
    Without a page parameter, returns the first max_pages pages.
    """
    doc = await doc_service.get_document(
        db, document_id=document_id, user_id=current_user.id
    )
    if doc is None or doc.case_id != case_id:
        raise HTTPException(status_code=404, detail="Document not found.")

    if doc.processing_status == "pending":
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail="Document is queued for processing.",
        )
    if doc.processing_status == "processing":
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail="Document is still being processed.",
        )
    if doc.processing_status == "failed" and not doc.page_count:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=doc.failure_reason or "Text extraction failed for this document.",
        )

    chunks = await doc_service.get_document_chunks(
        db,
        document_id=document_id,
        user_id=current_user.id,
        page_number=page,
    )

    # Apply max_pages cap when returning all pages
    is_partial = False
    if page is None and len(chunks) > max_pages:
        chunks = chunks[:max_pages]
        is_partial = True

    return ApiResponse.ok(
        DocumentTextPreviewResponse(
            document_id=document_id,
            total_pages=doc.page_count or 0,
            chunks=[DocumentChunkResponse.model_validate(c) for c in chunks],
            is_partial=is_partial,
        )
    )


# ---------------------------------------------------------------------------
# Retry extraction
# ---------------------------------------------------------------------------


@router.post(
    "/{document_id}/retry",
    response_model=ApiResponse[DocumentResponse],
)
async def retry_document(
    case_id: str,
    document_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> ApiResponse[DocumentResponse]:
    """
    Retry text extraction for a failed or pending document.
    Bounded by MAX_RETRY_ATTEMPTS (3).
    """
    storage = get_storage()
    try:
        doc = await doc_service.retry_document(
            db,
            document_id=document_id,
            user_id=current_user.id,
            storage=storage,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if doc.case_id != case_id:
        raise HTTPException(status_code=404, detail="Document not found.")
    return ApiResponse.ok(DocumentResponse.model_validate(doc))


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@router.delete("/{document_id}", response_model=ApiResponse[None])
async def delete_document(
    case_id: str,
    document_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> ApiResponse[None]:
    """
    Permanently delete a document and all its extracted text.
    Removes the stored file from the storage backend.
    """
    storage = get_storage()
    deleted = await doc_service.delete_document(
        db,
        document_id=document_id,
        user_id=current_user.id,
        storage=storage,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found.")
    return ApiResponse.ok(None)
