"""Stage 7 hybrid legal retrieval package."""

from app.services.retrieval.chunking import TextChunk, chunk_text
from app.services.retrieval.evaluation import mean_reciprocal_rank, recall_at_k
from app.services.retrieval.hybrid import (
    RetrievedItem,
    RetrievalFilters,
    RetrievalOutput,
    hybrid_search,
)
from app.services.retrieval.ingestion import (
    index_case_documents,
    ingest_legal_record,
)

__all__ = [
    "RetrievalFilters",
    "RetrievalOutput",
    "RetrievedItem",
    "TextChunk",
    "chunk_text",
    "hybrid_search",
    "index_case_documents",
    "ingest_legal_record",
    "mean_reciprocal_rank",
    "recall_at_k",
]
