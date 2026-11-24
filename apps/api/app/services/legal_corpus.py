"""Configured legal-authority corpus & legal-source provider interface.

NyayaSaar never invents authorities. Legal-source search returns records only
from a configured real source (an operator-supplied JSON corpus or ingested
``legal_records`` in the database). When no real provider is configured, it
uses a clearly-labelled development fixture provider and marks every fixture
result with ``is_fixture=True`` so demo data is never mistaken for real law.

Supported configuration:
* ``LEGAL_CORPUS_PROVIDER=none`` (default) — no external corpus configured;
  ``FixtureCorpusProvider`` supplies clearly-labelled sample fixtures for UI
  exercising, while ``NullCorpusProvider`` returns empty results when strict
  non-fixture mode is requested.
* ``LEGAL_CORPUS_PROVIDER=json`` + ``LEGAL_CORPUS_PATH=/path/to/corpus.json`` —
  an operator-supplied JSON corpus.
* ``LEGAL_CORPUS_PROVIDER=database`` — searches records ingested into the
  ``legal_records`` / ``legal_record_chunks`` tables.
"""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from app.agents.schemas_extended import AuthorityResult
from app.config import Settings

logger = logging.getLogger("nyayasaar.legal_corpus")

_TOKEN = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "in", "is", "of", "on", "or", "that", "the", "this", "to", "with",
}


def _tokens(text: str) -> list[str]:
    return [
        token
        for token in _TOKEN.findall((text or "").casefold())
        if token not in _STOPWORDS
    ]


@dataclass(frozen=True, slots=True)
class LegalSourceRecord:
    """Normalised legal-source record with full provenance."""

    authority_id: str
    citation: str
    title: str
    court: str = ""
    jurisdiction: str = ""
    decision_date: str = ""
    year: str = ""
    holding_summary: str = ""
    text: str = ""
    source_url: str = ""
    source_provider: str = "none"
    page_number: int | None = None
    paragraph_number: int | None = None
    relevance_score: float = 0.0
    is_fixture: bool = False
    corpus_configured: bool = False
    metadata: dict[str, str] = field(default_factory=dict)

    def to_authority_result(self) -> AuthorityResult:
        return AuthorityResult(
            authority_id=self.authority_id,
            citation=self.citation,
            title=self.title,
            court=self.court,
            year=self.year,
            holding_summary=self.holding_summary,
            relevance_score=self.relevance_score,
            is_fixture=self.is_fixture,
            corpus_configured=self.corpus_configured,
        )


_SAMPLE_FIXTURE_RECORDS: tuple[dict[str, str], ...] = (
    {
        "authority_id": "fixture-limitation-001",
        "citation": "[SAMPLE FIXTURE — NOT A REAL CITATION] FX-LIM-001",
        "title": "[Sample Fixture] Limitation & Acknowledgment of Debt",
        "court": "Sample Civil Court (Fixture)",
        "jurisdiction": "India (Sample Fixture)",
        "decision_date": "2022-03-15",
        "year": "2022",
        "source_url": "",
        "holding_summary": (
            "Development fixture illustrating limitation-period and written "
            "acknowledgment metadata. Not real legal authority."
        ),
        "text": (
            "[SAMPLE FIXTURE — NOT REAL LEGAL AUTHORITY] Demonstrates retrieval "
            "over limitation periods, written acknowledgment of liability, "
            "breach of contract notice, and evidentiary corroboration."
        ),
    },
    {
        "authority_id": "fixture-trust-002",
        "citation": "[SAMPLE FIXTURE — NOT A REAL CITATION] FX-TRS-002",
        "title": "[Sample Fixture] Fiduciary Duty & Trust Deed Construction",
        "court": "Sample High Court (Fixture)",
        "jurisdiction": "India (Sample Fixture)",
        "decision_date": "2023-08-10",
        "year": "2023",
        "source_url": "",
        "holding_summary": (
            "Development fixture illustrating trust deed construction, trustee "
            "accountability, and succession disputes. Not real legal authority."
        ),
        "text": (
            "[SAMPLE FIXTURE — NOT REAL LEGAL AUTHORITY] Demonstrates retrieval "
            "for family trust disputes, fiduciary accounting, beneficiary "
            "rights, and documentary provenance."
        ),
    },
    {
        "authority_id": "fixture-notice-003",
        "citation": "[SAMPLE FIXTURE — NOT A REAL CITATION] FX-CON-003",
        "title": "[Sample Fixture] Termination Notice & Cure Period Compliance",
        "court": "Sample Commercial Division (Fixture)",
        "jurisdiction": "India (Sample Fixture)",
        "decision_date": "2024-01-22",
        "year": "2024",
        "source_url": "",
        "holding_summary": (
            "Development fixture illustrating contractual termination notice "
            "requirements and cure-period disputes. Not real legal authority."
        ),
        "text": (
            "[SAMPLE FIXTURE — NOT REAL LEGAL AUTHORITY] Demonstrates retrieval "
            "for termination clause compliance, cure notice delivery, and "
            "damages quantification."
        ),
    },
)


class LegalCorpusProvider(ABC):
    """Interface for a configured legal-authority corpus."""

    name: str = "none"
    configured: bool = False
    is_fixture: bool = False

    @abstractmethod
    async def search(self, query: str, *, limit: int = 10) -> list[AuthorityResult]:
        """Return corpus records relevant to ``query``. Never fabricate."""

    async def search_records(
        self,
        query: str,
        *,
        limit: int = 10,
        jurisdiction: str | None = None,
        court: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[LegalSourceRecord]:
        """Search and return normalised ``LegalSourceRecord`` items."""
        return []


class NullCorpusProvider(LegalCorpusProvider):
    name = "none"
    configured = False
    is_fixture = False

    async def search(self, query: str, *, limit: int = 10) -> list[AuthorityResult]:
        return []


class FixtureCorpusProvider(LegalCorpusProvider):
    """Clearly-labelled development fixture provider.

    Used when no real legal corpus is configured so the Legal Research UI and
    retrieval pipeline can be exercised without fabricating real judgments.
    """

    name = "development_fixture"
    configured = False
    is_fixture = True

    async def search_records(
        self,
        query: str,
        *,
        limit: int = 10,
        jurisdiction: str | None = None,
        court: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[LegalSourceRecord]:
        q_tokens = set(_tokens(query))
        matches: list[LegalSourceRecord] = []
        for raw in _SAMPLE_FIXTURE_RECORDS:
            if jurisdiction and jurisdiction.casefold() not in raw["jurisdiction"].casefold():
                continue
            if court and court.casefold() not in raw["court"].casefold():
                continue
            if date_from and raw["decision_date"] < date_from:
                continue
            if date_to and raw["decision_date"] > date_to:
                continue

            haystack = " ".join(
                [raw["title"], raw["citation"], raw["holding_summary"], raw["text"]]
            )
            r_tokens = set(_tokens(haystack))
            overlap = len(q_tokens & r_tokens) if q_tokens else 1
            score = min(1.0, (overlap / max(1, len(q_tokens))) if q_tokens else 0.5)
            if q_tokens and overlap == 0:
                continue
            matches.append(
                LegalSourceRecord(
                    authority_id=raw["authority_id"],
                    citation=raw["citation"],
                    title=raw["title"],
                    court=raw["court"],
                    jurisdiction=raw["jurisdiction"],
                    decision_date=raw["decision_date"],
                    year=raw["year"],
                    holding_summary=raw["holding_summary"],
                    text=raw["text"],
                    source_url="",
                    source_provider=self.name,
                    paragraph_number=1,
                    relevance_score=round(score, 4),
                    is_fixture=True,
                    corpus_configured=False,
                )
            )
        matches.sort(key=lambda r: (-r.relevance_score, r.title))
        return matches[:limit]

    async def search(self, query: str, *, limit: int = 10) -> list[AuthorityResult]:
        records = await self.search_records(query, limit=limit)
        return [r.to_authority_result() for r in records]


class JsonCorpusProvider(LegalCorpusProvider):
    """Operator-supplied JSON corpus.

    The file must contain ``{"authorities": [...]}``. Records are returned as
    stored. Missing fields are left blank rather than inferred.
    """

    name = "json"
    configured = True
    is_fixture = False

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
                continue
            records.append(
                {
                    "authority_id": str(item.get("authority_id", "")).strip(),
                    "citation": citation,
                    "title": title,
                    "court": str(item.get("court", "")).strip(),
                    "jurisdiction": str(item.get("jurisdiction", "")).strip(),
                    "decision_date": str(item.get("decision_date", "")).strip(),
                    "year": str(item.get("year", "")).strip(),
                    "holding_summary": str(item.get("holding_summary", "")).strip(),
                    "text": str(item.get("text", "") or item.get("holding_summary", "")).strip(),
                    "url": str(item.get("url", "")).strip(),
                }
            )
        self._records = records

    async def search_records(
        self,
        query: str,
        *,
        limit: int = 10,
        jurisdiction: str | None = None,
        court: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[LegalSourceRecord]:
        query_tokens = set(_tokens(query))
        if not query_tokens:
            return []

        scored: list[tuple[float, dict[str, str]]] = []
        for record in self._records:
            if jurisdiction and jurisdiction.casefold() not in record.get("jurisdiction", "").casefold():
                continue
            if court and court.casefold() not in record.get("court", "").casefold():
                continue
            d_date = record.get("decision_date", "")
            if date_from and d_date and d_date < date_from:
                continue
            if date_to and d_date and d_date > date_to:
                continue

            haystack = " ".join(
                [
                    record.get("title", ""),
                    record.get("citation", ""),
                    record.get("court", ""),
                    record.get("jurisdiction", ""),
                    record.get("holding_summary", ""),
                    record.get("text", ""),
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
            LegalSourceRecord(
                authority_id=record.get("authority_id", ""),
                citation=record["citation"],
                title=record["title"],
                court=record.get("court", ""),
                jurisdiction=record.get("jurisdiction", ""),
                decision_date=record.get("decision_date", ""),
                year=record.get("year", ""),
                holding_summary=record.get("holding_summary", ""),
                text=record.get("text", ""),
                source_url=record.get("url", ""),
                source_provider=self.name,
                relevance_score=round(score, 4),
                is_fixture=False,
                corpus_configured=True,
            )
            for score, record in scored[:limit]
        ]

    async def search(self, query: str, *, limit: int = 10) -> list[AuthorityResult]:
        records = await self.search_records(query, limit=limit)
        return [r.to_authority_result() for r in records]


def get_corpus_provider(
    settings: Settings, *, allow_fixture: bool = False
) -> LegalCorpusProvider:
    provider = (settings.legal_corpus_provider or "none").strip().lower()
    if provider == "json" and settings.legal_corpus_path:
        corpus = JsonCorpusProvider(settings.legal_corpus_path)
        if corpus.configured:
            return corpus
        return FixtureCorpusProvider() if allow_fixture else NullCorpusProvider()
    if provider == "fixture" or (provider == "none" and allow_fixture):
        return FixtureCorpusProvider()
    return NullCorpusProvider()
