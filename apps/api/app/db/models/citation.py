"""CitationLink model — Stage 9 Precedent Explorer.

Records citation relationships between legal records (resolved) or raw
citation strings (unresolved). Never invents citation data; unresolved links
store the raw text as-is and are clearly labelled.
"""

from __future__ import annotations

import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class CitationLink(TimestampMixin, Base):
    """A directed citation edge between two legal records (or an unresolved raw text)."""

    __tablename__ = "citation_links"

    id: Mapped[str] = mapped_column(
        sa.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    # The legal_record from which the citation originates.
    from_record_id: Mapped[str] = mapped_column(
        sa.String(36),
        sa.ForeignKey("legal_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Resolved target record (nullable — None means unresolved).
    to_record_id: Mapped[str | None] = mapped_column(
        sa.String(36),
        sa.ForeignKey("legal_records.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Raw citation text (always populated; used when to_record_id is None).
    to_citation_text: Mapped[str] = mapped_column(sa.String(500), nullable=False)

    # cites | cited_by | related_issue | potentially_conflicting
    relationship_type: Mapped[str] = mapped_column(
        sa.String(40), nullable=False, index=True
    )

    # Verbatim passage from the source that evidences the relationship.
    source_passage: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    # Provenance: which corpus or service produced this link.
    source_provider: Mapped[str] = mapped_column(
        sa.String(60), nullable=False, default="database"
    )

    # True when to_record_id is populated and verified.
    is_resolved: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.text("false")
    )

    # high | medium | low
    confidence: Mapped[str] = mapped_column(
        sa.String(20), nullable=False, default="medium"
    )

    # Workflow run that produced this link.
    workflow_id: Mapped[str | None] = mapped_column(
        sa.String(36),
        sa.ForeignKey("workflow_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Flexible JSON metadata (e.g. model note, is_fixture).
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        sa.JSON, nullable=False, default=dict
    )

    __table_args__ = (
        sa.Index(
            "ix_citation_links_from_to",
            "from_record_id",
            "to_record_id",
        ),
    )
