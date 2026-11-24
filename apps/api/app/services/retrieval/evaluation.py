"""Retrieval evaluation metrics (Recall@K, MRR) for labelled test sets."""

from __future__ import annotations

from collections.abc import Sequence


def recall_at_k(
    retrieved_ids: Sequence[str],
    relevant_ids: set[str] | Sequence[str],
    k: int,
) -> float:
    """Fraction of relevant items appearing in the top-K retrieved results."""
    rel = set(relevant_ids)
    if not rel or k <= 0:
        return 0.0
    top_k = set(retrieved_ids[:k])
    return len(top_k & rel) / len(rel)


def mean_reciprocal_rank(
    ranked_lists: Sequence[Sequence[str]],
    relevant_sets: Sequence[set[str]],
) -> float:
    """Compute Mean Reciprocal Rank across queries."""
    if not ranked_lists or len(ranked_lists) != len(relevant_sets):
        return 0.0
    total = 0.0
    for retrieved, rel in zip(ranked_lists, relevant_sets):
        for idx, item_id in enumerate(retrieved, start=1):
            if item_id in rel:
                total += 1.0 / idx
                break
    return total / len(ranked_lists)
