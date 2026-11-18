"""add documents and document_chunks tables

Revision ID: 002
Revises: 001
Create Date: 2026-11-17 00:00:00.000000

Stage 4: Document ingestion pipeline.
Adds:
  - documents: uploaded file metadata, processing state, storage key
  - document_chunks: extracted text per page with page reference
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- documents ---
    op.create_table(
        "documents",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "case_id",
            sa.String(36),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "owner_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("original_name", sa.String(500), nullable=False),
        sa.Column("storage_key", sa.String(1000), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("processing_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("is_ocr_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("extraction_completeness", sa.Integer(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
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
        sa.UniqueConstraint("storage_key", name="uq_document_storage_key"),
    )
    op.create_index("ix_documents_case_id", "documents", ["case_id"])
    op.create_index("ix_documents_owner_id", "documents", ["owner_id"])
    op.create_index("ix_documents_processing_status", "documents", ["processing_status"])

    # --- document_chunks ---
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "document_id",
            sa.String(36),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "document_id", "page_number", name="uq_document_chunk_page"
        ),
    )
    op.create_index(
        "ix_document_chunks_document_id", "document_chunks", ["document_id"]
    )


def downgrade() -> None:
    op.drop_table("document_chunks")
    op.drop_table("documents")
