"""Typed contracts for Stage 9 — Precedent Explorer & Conflict Detector.

Every authority result carries is_fixture + source_provider provenance.
No legal authority, citation, holding, or judicial treatment is ever fabricated.
Pydantic field_validators coerce AI output robustly (lesson from Stage 8).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.agents.schemas import (
    DraftSourceRef,
    SourceManifestEntry,
    SourceStats,
    SupportStatus,
    VerificationSummary,
    VerifiedSourceRef,
)

PRECEDENT_WORKFLOW_VERSION = "9.0.0"
PRECEDENT_PROMPT_VERSION = "2026-11-precedent-v1"
PRECEDENT_RESULT_SCHEMA_VERSION = "9.0"

CitationRelationship = Literal[
    "cites", "cited_by", "related_issue", "potentially_conflicting"
]

ConfidenceLevel = Literal["high", "medium", "low"]


# ---------------------------------------------------------------------------
# Draft types (produced by LLM, then verified)
# ---------------------------------------------------------------------------


class DraftAuthority(BaseModel):
    """A single legal authority proposed by the analyst."""

    citation_text: str = Field(default="[citation not available]")
    title: str = Field(default="[title not available]")
    court: str = Field(default="[court not available]")
    jurisdiction: str = Field(default="[jurisdiction not available]")
    decision_date: str = Field(default="[date not available]")
    holding_summary: str = Field(default="[holding not available]")
    # Must match a source_id from the retrieved legal records (S1, S2…).
    source_id: str = Field(default="")
    source_provider: str = Field(default="[provider not available]")
    is_fixture: bool = Field(default=False)
    relevance_note: str = Field(default="")

    @field_validator(
        "citation_text", "title", "court", "jurisdiction",
        "decision_date", "holding_summary", "relevance_note",
        mode="before",
    )
    @classmethod
    def coerce_str(cls, v: Any) -> str:
        return str(v or "").strip()[:1000] or "[not available]"

    @field_validator("source_id", "source_provider", mode="before")
    @classmethod
    def coerce_short_str(cls, v: Any) -> str:
        return str(v or "").strip()[:200]


class DraftCitationPair(BaseModel):
    """A directed citation relationship between two authorities."""

    from_citation: str = Field(default="")
    to_citation: str = Field(default="")
    relationship_type: CitationRelationship = "cites"
    supporting_passage: str = Field(default="")
    source_ref: DraftSourceRef | None = Field(default=None)
    confidence: ConfidenceLevel = "medium"

    @field_validator("from_citation", "to_citation", "supporting_passage", mode="before")
    @classmethod
    def coerce_str(cls, v: Any) -> str:
        return str(v or "").strip()[:500]


class DraftConflict(BaseModel):
    """A potential reasoning conflict between two authorities."""

    title: str = Field(default="[conflict title not available]")
    interpretation_a: str = Field(default="")
    interpretation_b: str = Field(default="")
    source_a_ref: DraftSourceRef | None = Field(default=None)
    source_b_ref: DraftSourceRef | None = Field(default=None)
    # Neutral analytical note — never allege binding status.
    model_note: str = Field(
        default=(
            "These passages were flagged as potentially conflicting by the model "
            "for human review only. No binding legal determination is made."
        )
    )

    @field_validator("title", "interpretation_a", "interpretation_b", "model_note", mode="before")
    @classmethod
    def coerce_str(cls, v: Any) -> str:
        return str(v or "").strip()[:1500] or "[not available]"


class PrecedentSearchDraft(BaseModel):
    """Full draft returned by the LLM before verification."""

    authorities: list[DraftAuthority] = Field(default_factory=list)
    citation_pairs: list[DraftCitationPair] = Field(default_factory=list)
    potential_conflicts: list[DraftConflict] = Field(default_factory=list)
    summary: str = Field(default="No summary provided.")
    limitations: list[str] = Field(default_factory=list)

    @field_validator("authorities", "citation_pairs", "potential_conflicts", "limitations", mode="before")
    @classmethod
    def coerce_list(cls, v: Any) -> list[Any]:
        if v is None:
            return []
        return list(v) if isinstance(v, list) else []

    @field_validator("summary", mode="before")
    @classmethod
    def coerce_summary(cls, v: Any) -> str:
        text = str(v or "").strip()
        return text[:3000] if text else "No summary provided."


# ---------------------------------------------------------------------------
# Verified types (produced by the verifier node)
# ---------------------------------------------------------------------------


class VerifiedAuthority(BaseModel):
    """A verified legal authority with source provenance."""

    authority_id: str
    citation_text: str
    title: str
    court: str
    jurisdiction: str
    decision_date: str
    holding_summary: str
    source_id: str
    source_provider: str
    is_fixture: bool
    relevance_note: str
    verified_ref: VerifiedSourceRef | None = None
    support: SupportStatus = "unsupported"


class VerifiedCitationPair(BaseModel):
    """A verified directed citation relationship."""

    from_citation: str
    to_citation: str
    relationship_type: CitationRelationship
    supporting_passage: str
    confidence: ConfidenceLevel
    verified_ref: VerifiedSourceRef | None = None
    support: SupportStatus = "unsupported"


class VerifiedConflict(BaseModel):
    """A verified potential conflict between two authorities."""

    title: str
    interpretation_a: str
    interpretation_b: str
    source_a_verified: VerifiedSourceRef | None = None
    source_b_verified: VerifiedSourceRef | None = None
    model_note: str
    support: SupportStatus = "unsupported"


# ---------------------------------------------------------------------------
# Final result
# ---------------------------------------------------------------------------


class PrecedentResult(BaseModel):
    """Full Stage 9 Precedent Explorer result."""

    workflow_id: str
    case_id: str
    generated_at: datetime
    provider: str
    model: str
    is_mock: bool
    workflow_version: str = PRECEDENT_WORKFLOW_VERSION
    prompt_version: str = PRECEDENT_PROMPT_VERSION
    result_schema_version: str = PRECEDENT_RESULT_SCHEMA_VERSION
    corpus_configured: bool = False
    insufficient_sources: bool = False
    query_used: str = ""
    authorities: list[VerifiedAuthority] = Field(default_factory=list)
    citation_pairs: list[VerifiedCitationPair] = Field(default_factory=list)
    potential_conflicts: list[VerifiedConflict] = Field(default_factory=list)
    summary: str = ""
    limitations: list[str] = Field(default_factory=list)
    verification: VerificationSummary = Field(default_factory=VerificationSummary)
    source_manifest: list[SourceManifestEntry] = Field(default_factory=list)
    source_stats: SourceStats = Field(default_factory=SourceStats)
    professional_review_required: bool = True
    input_metadata: dict[str, Any] = Field(default_factory=dict)
