"""
NyayaSaar API — User SQLAlchemy model.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.case import Case, CaseMembership


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        sa.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    email: Mapped[str] = mapped_column(
        sa.String(254),
        unique=True,
        index=True,
        nullable=False,
    )
    hashed_password: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(sa.Boolean, default=False, nullable=False)
    role: Mapped[str] = mapped_column(
        sa.String(20),
        default="user",
        nullable=False,
        server_default="user",
    )

    # Relationships
    cases: Mapped[list["Case"]] = relationship(
        "Case", back_populates="owner", foreign_keys="Case.owner_id"
    )
    memberships: Mapped[list["CaseMembership"]] = relationship(
        "CaseMembership", back_populates="user"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"
