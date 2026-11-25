"""add finding_reviews table for Stage 8 contradiction review audit trail

Revision ID: 006
Revises: 005
Create Date: 2026-11-25 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "finding_reviews",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "workflow_id",
            sa.String(36),
            sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            sa.String(36),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("finding_id", sa.String(64), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="unreviewed",
        ),
        sa.Column("reviewer_note", sa.Text(), nullable=True),
        sa.Column(
            "updated_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "history",
            sa.JSON(),
            nullable=False,
            server_default="[]",
        ),
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
        sa.UniqueConstraint(
            "workflow_id", "finding_id", name="uq_finding_review_workflow_finding"
        ),
    )
    op.create_index(
        "ix_finding_reviews_workflow_id", "finding_reviews", ["workflow_id"]
    )
    op.create_index("ix_finding_reviews_case_id", "finding_reviews", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_finding_reviews_case_id", table_name="finding_reviews")
    op.drop_index("ix_finding_reviews_workflow_id", table_name="finding_reviews")
    op.drop_table("finding_reviews")
