"""add citation_links table for Stage 9 Precedent Explorer

Revision ID: 007
Revises: 006
Create Date: 2026-11-26 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "citation_links",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "from_record_id",
            sa.String(36),
            sa.ForeignKey("legal_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "to_record_id",
            sa.String(36),
            sa.ForeignKey("legal_records.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("to_citation_text", sa.String(500), nullable=False),
        sa.Column("relationship_type", sa.String(40), nullable=False),
        sa.Column("source_passage", sa.Text(), nullable=True),
        sa.Column(
            "source_provider",
            sa.String(60),
            nullable=False,
            server_default="database",
        ),
        sa.Column(
            "is_resolved",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "confidence",
            sa.String(20),
            nullable=False,
            server_default="medium",
        ),
        sa.Column(
            "workflow_id",
            sa.String(36),
            sa.ForeignKey("workflow_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "metadata_json",
            sa.JSON(),
            nullable=False,
            server_default="{}",
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
    )
    op.create_index(
        "ix_citation_links_from_record_id", "citation_links", ["from_record_id"]
    )
    op.create_index(
        "ix_citation_links_to_record_id", "citation_links", ["to_record_id"]
    )
    op.create_index(
        "ix_citation_links_relationship_type", "citation_links", ["relationship_type"]
    )
    op.create_index(
        "ix_citation_links_workflow_id", "citation_links", ["workflow_id"]
    )
    op.create_index(
        "ix_citation_links_from_to",
        "citation_links",
        ["from_record_id", "to_record_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_citation_links_from_to", table_name="citation_links")
    op.drop_index("ix_citation_links_workflow_id", table_name="citation_links")
    op.drop_index("ix_citation_links_relationship_type", table_name="citation_links")
    op.drop_index("ix_citation_links_to_record_id", table_name="citation_links")
    op.drop_index("ix_citation_links_from_record_id", table_name="citation_links")
    op.drop_table("citation_links")
