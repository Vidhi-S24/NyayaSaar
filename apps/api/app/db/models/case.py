"""
NyayaSaar API — Case and CaseMembership SQLAlchemy models.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.user import User


class Case(TimestampMixin, Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(
        sa.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    owner_id: Mapped[str] = mapped_column(
        sa.String(36),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    case_number: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    court: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    jurisdiction: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        sa.String(20),
        default="active",
        nullable=False,
        server_default="active",
    )
    priority: Mapped[str] = mapped_column(
        sa.String(20),
        default="medium",
        nullable=False,
        server_default="medium",
    )
    summary: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    # JSON type works with both SQLite (as text) and PostgreSQL (as JSON)
    tags: Mapped[list] = mapped_column(sa.JSON, default=list, nullable=False, server_default="[]")
    issues: Mapped[list] = mapped_column(sa.JSON, default=list, nullable=False, server_default="[]")
    documents_count: Mapped[int] = mapped_column(sa.Integer, default=0, nullable=False)

    # Relationships
    owner: Mapped["User"] = relationship(
        "User", back_populates="cases", foreign_keys=[owner_id]
    )
    memberships: Mapped[list["CaseMembership"]] = relationship(
        "CaseMembership", back_populates="case", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Case id={self.id} title={self.title!r}>"


class CaseMembership(Base):
    __tablename__ = "case_memberships"

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
    role: Mapped[str] = mapped_column(
        sa.String(20),
        default="viewer",
        nullable=False,
        server_default="viewer",
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=sa.func.now(),
    )

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="memberships")
    user: Mapped["User"] = relationship("User", back_populates="memberships")

    __table_args__ = (
        sa.UniqueConstraint("case_id", "user_id", name="uq_case_membership"),
    )

    def __repr__(self) -> str:
        return f"<CaseMembership case={self.case_id} user={self.user_id} role={self.role}>"
