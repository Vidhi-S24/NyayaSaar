"""add workflow_runs table

Revision ID: 003
Revises: 002
Create Date: 2026-11-20 00:00:00.000000

Stage 5: agent workflow persistence.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_runs",
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
        sa.Column(
            "workflow_type",
            sa.String(40),
            nullable=False,
            server_default="case_analysis",
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_step", sa.String(120), nullable=True),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("model", sa.String(160), nullable=True),
        sa.Column(
            "is_mock", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("input_payload", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("token_usage", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(60), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
    op.create_index("ix_workflow_runs_case_id", "workflow_runs", ["case_id"])
    op.create_index("ix_workflow_runs_user_id", "workflow_runs", ["user_id"])
    op.create_index(
        "ix_workflow_runs_workflow_type", "workflow_runs", ["workflow_type"]
    )
    op.create_index("ix_workflow_runs_status", "workflow_runs", ["status"])


def downgrade() -> None:
    op.drop_table("workflow_runs")
