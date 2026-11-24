"""add case intelligence version metadata

Revision ID: 004
Revises: 003
Create Date: 2026-11-24 00:00:00.000000

Stage 6: persist the workflow, prompt, and result-schema versions used for an
analysis run so a stored report remains auditable after prompts change.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("workflow_runs") as batch_op:
        batch_op.add_column(sa.Column("workflow_version", sa.String(40), nullable=True))
        batch_op.add_column(sa.Column("prompt_version", sa.String(80), nullable=True))
        batch_op.add_column(
            sa.Column("result_schema_version", sa.String(40), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("workflow_runs") as batch_op:
        batch_op.drop_column("result_schema_version")
        batch_op.drop_column("prompt_version")
        batch_op.drop_column("workflow_version")
