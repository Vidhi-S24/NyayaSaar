"""Finding review persistence and audit trail (Stage 8).

Stores user review decisions (confirmed / dismissed / needs_review / unreviewed)
for Contradiction & Gap Hunter findings, along with an append-only audit trail
of every status/note change.
"""

from __future__ import annotations

import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class FindingReview(TimestampMixin, Base):
    __tablename__ = "finding_reviews"

    id: Mapped[str] = mapped_column(
        sa.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    workflow_id: Mapped[str] = mapped_column(
        sa.String(36),
        sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[str] = mapped_column(
        sa.String(36),
        sa.ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    finding_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    # unreviewed | confirmed | dismissed | needs_review
    status: Mapped[str] = mapped_column(
        sa.String(20),
        nullable=False,
        default="unreviewed",
        server_default="unreviewed",
    )
    reviewer_note: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    updated_by_user_id: Mapped[str] = mapped_column(
        sa.String(36),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Append-only audit trail: [{previous_status, new_status, note, user_id, user_email, at}]
    history: Mapped[list[dict[str, Any]]] = mapped_column(
        sa.JSON,
        nullable=False,
        default=list,
        server_default="[]",
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "workflow_id", "finding_id", name="uq_finding_review_workflow_finding"
        ),
    )
