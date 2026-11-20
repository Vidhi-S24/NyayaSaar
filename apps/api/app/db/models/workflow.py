"""Workflow run persistence.

Workflow status, progress, steps, and results are stored in PostgreSQL (or the
SQLite development fallback) so the frontend can poll and so a completed run
survives a process restart. In-process LangGraph checkpoints are separate.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.case import Case
    from app.db.models.user import User


class WorkflowRun(TimestampMixin, Base):
    __tablename__ = "workflow_runs"

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
    user_id: Mapped[str] = mapped_column(
        sa.String(36),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workflow_type: Mapped[str] = mapped_column(
        sa.String(40),
        nullable=False,
        default="case_analysis",
        server_default="case_analysis",
        index=True,
    )

    # queued | running | completed | failed
    status: Mapped[str] = mapped_column(
        sa.String(20),
        nullable=False,
        default="queued",
        server_default="queued",
        index=True,
    )
    progress: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, default=0, server_default="0"
    )
    current_step: Mapped[str | None] = mapped_column(sa.String(120), nullable=True)

    # Safe provider metadata (never the API key)
    provider: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    model: Mapped[str | None] = mapped_column(sa.String(160), nullable=True)
    is_mock: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.text("false")
    )

    # Input and output
    input_payload: Mapped[dict[str, Any]] = mapped_column(
        sa.JSON, nullable=False, default=dict, server_default="{}"
    )
    result: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON, nullable=True)
    steps: Mapped[list[dict[str, Any]]] = mapped_column(
        sa.JSON, nullable=False, default=list, server_default="[]"
    )
    token_usage: Mapped[dict[str, Any]] = mapped_column(
        sa.JSON, nullable=False, default=dict, server_default="{}"
    )

    # Failure state (sanitised; never includes prompts or document text)
    error_code: Mapped[str | None] = mapped_column(sa.String(60), nullable=True)
    error_message: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    attempt_count: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, default=0, server_default="0"
    )
    started_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    case: Mapped["Case"] = relationship("Case")
    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return (
            f"<WorkflowRun id={self.id} type={self.workflow_type} "
            f"status={self.status} progress={self.progress}>"
        )
