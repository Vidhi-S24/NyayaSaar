"""
NyayaSaar API — Document SQLAlchemy model.

Stores uploaded documents and their processing state.
Extracted page chunks are stored in the document_chunks table.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.case import Case
    from app.db.models.user import User


class Document(TimestampMixin, Base):
    """Uploaded legal document within a case."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(
        sa.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    case_id: Mapped[str] = mapped_column(
        sa.String(36),
        sa.ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[str] = mapped_column(
        sa.String(36),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # --- File metadata (safe; no raw filenames in storage keys) ---
    original_name: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    # Sanitised storage key (no path traversal, no original filename)
    storage_key: Mapped[str] = mapped_column(sa.String(1000), nullable=False, unique=True)
    # Detected MIME type (not client-provided)
    content_type: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)

    # --- Processing state ---
    # pending → processing → ready | failed
    processing_status: Mapped[str] = mapped_column(
        sa.String(20),
        default="pending",
        nullable=False,
        server_default="pending",
        index=True,
    )
    page_count: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    # Whether the PDF appeared to be scanned/image-only
    is_ocr_required: Mapped[bool] = mapped_column(
        sa.Boolean, default=False, nullable=False
    )
    # Percentage of pages successfully extracted (0-100)
    extraction_completeness: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    # Human-readable failure description; never includes raw document content
    failure_reason: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    processing_started_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    processing_completed_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    # Retry counter — bounded by settings
    retry_count: Mapped[int] = mapped_column(sa.Integer, default=0, nullable=False)

    # --- Relationships ---
    case: Mapped["Case"] = relationship("Case", back_populates="documents")
    owner: Mapped["User"] = relationship("User", back_populates="documents")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk", back_populates="document", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Document id={self.id} name={self.original_name!r} status={self.processing_status}>"


class DocumentChunk(Base):
    """
    A single page or logical segment of extracted text.

    page_number is 1-indexed, stable, and matches the original document page
    so that any downstream AI claim can cite the exact source page.

    Security: extracted_text is *untrusted content* from the uploaded document.
    It must never be executed, interpolated into shell commands, or passed
    to downstream services without sanitisation.
    """

    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(
        sa.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    document_id: Mapped[str] = mapped_column(
        sa.String(36),
        sa.ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 1-indexed page number matching the source PDF/DOCX page
    page_number: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    # Raw extracted text — UNTRUSTED; treat as adversarial input (prompt injection risk)
    extracted_text: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # Approximate character count (not byte count — text is Unicode)
    char_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=sa.func.now(),
    )

    # Relationship
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")

    __table_args__ = (
        sa.UniqueConstraint("document_id", "page_number", name="uq_document_chunk_page"),
        sa.Index("ix_document_chunks_document_id", "document_id"),
    )

    def __repr__(self) -> str:
        return f"<DocumentChunk doc={self.document_id} page={self.page_number}>"
