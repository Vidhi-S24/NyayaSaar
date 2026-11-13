"""initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("role", sa.String(20), nullable=False, server_default="user"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # --- cases ---
    op.create_table(
        "cases",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "owner_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("case_number", sa.String(100), nullable=True),
        sa.Column("court", sa.String(255), nullable=True),
        sa.Column("jurisdiction", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("priority", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("issues", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("documents_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_cases_owner_id", "cases", ["owner_id"])

    # --- case_memberships ---
    op.create_table(
        "case_memberships",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "case_id",
            sa.String(36),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False, server_default="viewer"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("case_id", "user_id", name="uq_case_membership"),
    )
    op.create_index("ix_case_memberships_case_id", "case_memberships", ["case_id"])
    op.create_index("ix_case_memberships_user_id", "case_memberships", ["user_id"])


def downgrade() -> None:
    op.drop_table("case_memberships")
    op.drop_table("cases")
    op.drop_table("users")
