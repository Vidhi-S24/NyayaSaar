"""Explicit tool interfaces used by agent nodes.

Tools are typed, bounded callables. They never execute arbitrary code and never
follow instructions found inside document text.
"""

from app.agents.tools.sources import (
    SourceExcerpt,
    load_case_sources,
    normalize_text,
    quote_in_source,
    resolve_source,
)

__all__ = [
    "SourceExcerpt",
    "load_case_sources",
    "normalize_text",
    "quote_in_source",
    "resolve_source",
]
