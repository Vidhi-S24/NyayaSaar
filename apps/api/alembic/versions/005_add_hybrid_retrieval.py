"""add hybrid retrieval tables, pgvector, and full-text search

Revision ID: 005
Revises: 004
Create Date: 2026-11-25 00:00:00.000000

Stage 7: Hybrid Legal Retrieval.
Adds:
  - legal_records & legal_record_chunks tables with provenance & metadata
  - embedding_json, embedding_model, embedding_dim on document_chunks
  - On PostgreSQL: enables pgvector extension, adds vector(256) and
    generated tsvector columns + GIN and HNSW indexes.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Extend document_chunks with portable embedding metadata
    with op.batch_alter_table("document_chunks") as batch_op:
        batch_op.add_column(sa.Column("embedding_json", sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column("embedding_model", sa.String(100), nullable=True)
        )
        batch_op.add_column(sa.Column("embedding_dim", sa.Integer(), nullable=True))

    # --- legal_records ---
    op.create_table(
        "legal_records",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "owner_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source_provider",
            sa.String(60),
            nullable=False,
            server_default="database",
        ),
        sa.Column("external_id", sa.String(200), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("citation", sa.String(250), nullable=True),
        sa.Column("jurisdiction", sa.String(120), nullable=True),
        sa.Column("court", sa.String(200), nullable=True),
        sa.Column("decision_date", sa.String(32), nullable=True),
        sa.Column("year", sa.String(16), nullable=True),
        sa.Column("source_url", sa.String(1000), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "is_fixture",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
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
    op.create_index("ix_legal_records_owner_id", "legal_records", ["owner_id"])
    op.create_index(
        "ix_legal_records_source_provider", "legal_records", ["source_provider"]
    )
    op.create_index(
        "ix_legal_records_jurisdiction", "legal_records", ["jurisdiction"]
    )
    op.create_index("ix_legal_records_court", "legal_records", ["court"])
    op.create_index(
        "ix_legal_records_decision_date", "legal_records", ["decision_date"]
    )
    op.create_index("ix_legal_records_citation", "legal_records", ["citation"])

    # --- legal_record_chunks ---
    op.create_table(
        "legal_record_chunks",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "record_id",
            sa.String(36),
            sa.ForeignKey("legal_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("paragraph_number", sa.Integer(), nullable=True),
        sa.Column("char_start", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("char_end", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("embedding_json", sa.JSON(), nullable=True),
        sa.Column("embedding_model", sa.String(100), nullable=True),
        sa.Column("embedding_dim", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "record_id", "chunk_index", name="uq_legal_record_chunk_idx"
        ),
    )
    op.create_index(
        "ix_legal_record_chunks_record_id", "legal_record_chunks", ["record_id"]
    )
    op.create_index(
        "ix_legal_record_chunks_content_hash",
        "legal_record_chunks",
        ["content_hash"],
    )

    if is_postgres:
        # pgvector column + HNSW index + tsvector GIN index on both chunk tables
        op.execute(
            "ALTER TABLE document_chunks "
            "ADD COLUMN IF NOT EXISTS embedding vector(256)"
        )
        op.execute(
            "ALTER TABLE document_chunks "
            "ADD COLUMN IF NOT EXISTS search_tsv tsvector "
            "GENERATED ALWAYS AS (to_tsvector('english', coalesce(extracted_text, ''))) STORED"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_document_chunks_tsv "
            "ON document_chunks USING gin (search_tsv)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw "
            "ON document_chunks USING hnsw (embedding vector_cosine_ops)"
        )

        op.execute(
            "ALTER TABLE legal_record_chunks "
            "ADD COLUMN IF NOT EXISTS embedding vector(256)"
        )
        op.execute(
            "ALTER TABLE legal_record_chunks "
            "ADD COLUMN IF NOT EXISTS search_tsv tsvector "
            "GENERATED ALWAYS AS (to_tsvector('english', coalesce(text, ''))) STORED"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_legal_record_chunks_tsv "
            "ON legal_record_chunks USING gin (search_tsv)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_legal_record_chunks_embedding_hnsw "
            "ON legal_record_chunks USING hnsw (embedding vector_cosine_ops)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw")
        op.execute("DROP INDEX IF EXISTS ix_document_chunks_tsv")
        op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS search_tsv")
        op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding")

    op.drop_table("legal_record_chunks")
    op.drop_table("legal_records")

    with op.batch_alter_table("document_chunks") as batch_op:
        batch_op.drop_column("embedding_dim")
        batch_op.drop_column("embedding_model")
        batch_op.drop_column("embedding_json")
