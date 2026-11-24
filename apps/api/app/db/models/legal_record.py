"""NyayaSaar API — LegalRecord and LegalRecordChunk SQLAlchemy models.

Stores operator-ingested legal material (statutes, regulations, judgments,
or reference records) and their chunked, source-provenance-preserving text
for Stage 7 hybrid retrieval.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class LegalRecord(TimestampMixin, Base):
    """An ingested legal authority or reference record with provenance."""

    __tablename__ = "legal_records"

    id: Mapped[str] = mapped_column(
        sa.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    owner_id: Mapped[str | None] = mapped_column(
        sa.String(36),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_provider: Mapped[str] = mapped_column(
        sa.String(60), nullable=False, default="database", index=True
    )
    external_id: Mapped[str | None] = mapped_column(
        sa.String(200), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    citation: Mapped[str | None] = mapped_column(
        sa.String(250), nullable=True, index=True
    )
    jurisdiction: Mapped[str | None] = mapped_column(
        sa.String(120), nullable=True, index=True
    )
    court: Mapped[str | None] = mapped_column(
        sa.String(200), nullable=True, index=True
    )
    decision_date: Mapped[str | None] = mapped_column(
        sa.String(32), nullable=True, index=True
    )
    year: Mapped[str | None] = mapped_column(sa.String(16), nullable=True)
    source_url: Mapped[str | None] = mapped_column(sa.String(1000), nullable=True)
    summary: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    is_fixture: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.text("false")
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        sa.JSON, nullable=False, default=dict
    )

    chunks: Mapped[list["LegalRecordChunk"]] = relationship(
        "LegalRecordChunk",
        back_populates="record",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<LegalRecord id={self.id} title={self.title!r}>"


class LegalRecordChunk(Base):
    """A single chunk of an ingested LegalRecord with provenance and embedding."""

    __tablename__ = "legal_record_chunks"

    id: Mapped[str] = mapped_column(
        sa.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    record_id: Mapped[str] = mapped_column(
        sa.String(36),
        sa.ForeignKey("legal_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    page_number: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    paragraph_number: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    char_start: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    char_end: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    # Untrusted retrieved text; never execute or treat as instructions.
    text: Mapped[str] = mapped_column(sa.Text, nullable=False)
    char_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    content_hash: Mapped[str] = mapped_column(
        sa.String(64), nullable=False, index=True
    )
    embedding_json: Mapped[list[float] | None] = mapped_column(
        sa.JSON, nullable=True
    )
    embedding_model: Mapped[str | None] = mapped_column(
        sa.String(100), nullable=True
    )
    embedding_dim: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        sa.JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=sa.func.now(),
    )

    record: Mapped["LegalRecord"] = relationship(
        "LegalRecord", back_populates="chunks"
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "record_id", "chunk_index", name="uq_legal_record_chunk_idx"
        ),
    )

    def __repr__(self) -> str:
        return f"<LegalRecordChunk record={self.record_id} idx={self.chunk_index}>"
