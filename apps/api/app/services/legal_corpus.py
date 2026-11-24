"""Configured legal-authority corpus interface.

NyayaSaar never invents authorities. The Precedent Explorer can only return
records from a corpus an operator has explicitly configured. When no corpus is
configured, the workflow returns a clearly-labelled fixture and says so.

Supported configuration:

* ``LEGAL_CORPUS_PROVIDER=none`` (default) — no corpus, fixture only.
* ``LEGAL_CORPUS_PROVIDER=json`` + ``LEGAL_CORPUS_PATH=/path/to/corpus.json`` —
  a local JSON corpus supplied by the operator. Each record is returned exactly
  as stored; nothing is generated.

A future provider (for example an authorised legal database) implements the
same ``LegalCorpusProvider`` interface.
"""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from pathlib import Path

from app.agents.schemas_extended import AuthorityResult
from app.config import Settings

logger = logging.getLogger("nyayasaar.legal_corpus")

_TOKEN = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "with",
}


def _tokens(text: str) -> list[str]:
    return [
        token
        for token in _TOKEN.findall((text or "").casefold())
        if token not in _STOPWORDS
    ]


class LegalCorpusProvider(ABC):
    """Interface for a configured legal-authority corpus."""

    name: str = "none"
    configured: bool = False

    @abstractmethod
    async def search(self, query: str, *, limit: int = 10) -> list[AuthorityResult]:
        """Return corpus records relevant to ``query``. Never fabricate."""


class NullCorpusProvider(LegalCorpusProvider):
    name = "none"
    configured = False

    async def search(self, query: str, *, limit: int = 10) -> list[AuthorityResult]:
        return []


class JsonCorpusProvider(LegalCorpusProvider):
    """Operator-supplied JSON corpus.

    The file must contain ``{"authorities": [...]}``. Records are returned as
    stored. Missing fields are left blank rather than inferred.
    """

    name = "json"
    configured = True

    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._records: list[dict[str, str]] = []
        self._load()

    def _load(self) -> None:
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning(
                "Legal corpus could not be read path=%s error=%s",
                self._path,
                type(exc).__name__,
            )
            self.configured = False
            return

        raw = payload.get("authorities") if isinstance(payload, dict) else payload
        if not isinstance(raw, list):
            logger.warning("Legal corpus has no 'authorities' list")
            self.configured = False
            return

        records: list[dict[str, str]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            citation = str(item.get("citation", "")).strip()
            title = str(item.get("title", "")).strip()
            if not citation or not title:
                # A record without a real citation and title is not usable.
                continue
            records.append(
                {
                    "authority_id": str(item.get("authority_id", "")).strip(),
                    "citation": citation,
                    "title": title,
                    "court": str(item.get("court", "")).strip(),
                    "year": str(item.get("year", "")).strip(),
                    "holding_summary": str(item.get("holding_summary", "")).strip(),
                    "url": str(item.get("url", "")).strip(),
                }
            )
        self._records = records

    async def search(self, query: str, *, limit: int = 10) -> list[AuthorityResult]:
        query_tokens = set(_tokens(query))
        if not query_tokens:
            return []

        scored: list[tuple[float, dict[str, str]]] = []
        for record in self._records:
            haystack = " ".join(
                [
                    record.get("title", ""),
                    record.get("citation", ""),
                    record.get("court", ""),
                    record.get("holding_summary", ""),
                ]
            )
            record_tokens = set(_tokens(haystack))
            if not record_tokens:
                continue
            overlap = len(query_tokens & record_tokens)
            if overlap == 0:
                continue
            score = overlap / len(query_tokens)
            scored.append((min(1.0, score), record))

        scored.sort(key=lambda item: (-item[0], item[1].get("title", "")))
        return [
            AuthorityResult(
                authority_id=record.get("authority_id", ""),
                citation=record["citation"],
                title=record["title"],
                court=record.get("court", ""),
                year=record.get("year", ""),
                holding_summary=record.get("holding_summary", ""),
                relevance_score=round(score, 4),
                is_fixture=False,
                corpus_configured=True,
            )
            for score, record in scored[:limit]
        ]


def get_corpus_provider(settings: Settings) -> LegalCorpusProvider:
    provider = (settings.legal_corpus_provider or "none").strip().lower()
    if provider == "json" and settings.legal_corpus_path:
        corpus = JsonCorpusProvider(settings.legal_corpus_path)
        if corpus.configured:
            return corpus
        return NullCorpusProvider()
    return NullCorpusProvider()
