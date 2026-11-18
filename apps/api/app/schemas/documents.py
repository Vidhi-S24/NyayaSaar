"""
NyayaSaar API — Document Pydantic schemas.

Request/response models for the documents API.

Security:
- original_name is display-only; never used as a path or storage key.
- extracted_text is marked as UNTRUSTED in this API layer.
- Storage keys are never exposed to clients (internal implementation detail).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class DocumentCreate(BaseModel):
    """
    Internal schema for creating a document record.
    Not a request body — the router uses UploadFile directly.
    """

    original_name: str
    content_type: str
    file_size: int


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class DocumentResponse(BaseModel):
    """Full document metadata returned to the client."""

    model_config = {"from_attributes": True}

    id: str
    case_id: str
    original_name: str
    content_type: str
    file_size: int
    processing_status: str  # pending | processing | ready | failed
    page_count: int | None
    is_ocr_required: bool
    extraction_completeness: int | None
    failure_reason: str | None
    retry_count: int
    created_at: datetime
    updated_at: datetime
    processing_started_at: datetime | None
    processing_completed_at: datetime | None


class DocumentChunkResponse(BaseModel):
    """A single extracted page/chunk."""

    model_config = {"from_attributes": True}

    id: str
    document_id: str
    page_number: int
    # extracted_text: intentionally exposed for preview — treat as untrusted
    extracted_text: str
    char_count: int
    created_at: datetime


class DocumentListResponse(BaseModel):
    """Paginated list of document summaries."""

    items: list[DocumentResponse]
    total: int
    page: int
    page_size: int
    has_next: bool


class DocumentTextPreviewResponse(BaseModel):
    """Extracted text preview for the document viewer."""

    document_id: str
    total_pages: int
    chunks: list[DocumentChunkResponse]
    # True if only a subset of pages is returned
    is_partial: bool = False
