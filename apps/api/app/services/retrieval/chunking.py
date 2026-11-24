"""Deterministic text chunking with provenance metadata."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TextChunk:
    chunk_index: int
    page_number: int | None
    paragraph_number: int | None
    char_start: int
    char_end: int
    text: str
    content_hash: str


def _sha256(text: str) -> str:
    return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()


def chunk_text(
    text: str,
    *,
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
    page_number: int | None = None,
) -> list[TextChunk]:
    """Split ``text`` into bounded chunks while preserving offsets and paragraph numbers."""
    cleaned = (text or "").strip()
    if not cleaned:
        return []

    chunk_size = max(100, chunk_size)
    chunk_overlap = max(0, min(chunk_overlap, chunk_size // 2))

    # Split on paragraph boundaries first so paragraph numbers remain meaningful.
    paragraphs = [p.strip() for p in cleaned.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [cleaned]

    chunks: list[TextChunk] = []
    cursor = 0
    chunk_idx = 0

    for para_idx, para in enumerate(paragraphs, start=1):
        start_in_doc = cleaned.find(para, cursor)
        if start_in_doc == -1:
            start_in_doc = cursor
        if len(para) <= chunk_size:
            end_in_doc = start_in_doc + len(para)
            chunks.append(
                TextChunk(
                    chunk_index=chunk_idx,
                    page_number=page_number,
                    paragraph_number=para_idx,
                    char_start=start_in_doc,
                    char_end=end_in_doc,
                    text=para,
                    content_hash=_sha256(para),
                )
            )
            chunk_idx += 1
            cursor = end_in_doc
            continue

        offset = 0
        step = max(1, chunk_size - chunk_overlap)
        while offset < len(para):
            piece = para[offset : offset + chunk_size].strip()
            if piece:
                abs_start = start_in_doc + offset
                abs_end = abs_start + len(piece)
                chunks.append(
                    TextChunk(
                        chunk_index=chunk_idx,
                        page_number=page_number,
                        paragraph_number=para_idx,
                        char_start=abs_start,
                        char_end=abs_end,
                        text=piece,
                        content_hash=_sha256(piece),
                    )
                )
                chunk_idx += 1
            if offset + chunk_size >= len(para):
                break
            offset += step
        cursor = start_in_doc + len(para)

    return chunks
