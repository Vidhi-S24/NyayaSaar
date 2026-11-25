"""Typed contracts for Stage 8 — Contradiction & Gap Hunter.

Reuses Stage 6 verified source references, timeline events, verification
summaries, and source manifests. Every finding strictly separates observed
evidence (source passages) from the model's interpretation (why flagged).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.agents.schemas import (
    DraftSourceRef,
    DraftTimelineEvent,
    SourceManifestEntry,
    SourceStats,
    SupportStatus,
    VerificationSummary,
    VerifiedSourceRef,
    VerifiedTimelineEvent,
)

CONTRADICTION_WORKFLOW_VERSION = "8.0.0"
CONTRADICTION_PROMPT_VERSION = "2026-11-contradiction-v1"
CONTRADICTION_RESULT_SCHEMA_VERSION = "8.0"

FindingCategory = Literal[
    "direct_contradiction",
    "possible_inconsistency",
    "evidence_gap",
    "unsupported_claim",
]

ConflictDimension = Literal[
    "statement",
    "date",
    "amount",
    "entity",
    "account_change",
    "missing_document",
    "unsupported_assertion",
]

FindingSeverity = Literal["high", "medium", "low"]

ReviewStatus = Literal["unreviewed", "confirmed", "dismissed", "needs_review"]


class DraftContradictionFinding(BaseModel):
    finding_id: str = Field(
        default="",
        description="Short stable identifier such as F1, F2.",
    )
    category: FindingCategory = "possible_inconsistency"
    dimension: ConflictDimension = "statement"
    severity: FindingSeverity = "medium"
    title: str = Field(min_length=1)
    observed_evidence_summary: str = Field(
        min_length=1,
        description="Neutral description of what the cited passages state.",
    )
    model_interpretation: str = Field(
        min_length=1,
        description=(
            "Why this was flagged as a potential conflict, gap, or unsupported "
            "claim. Never allege dishonesty or wrongdoing."
        ),
    )
    side_a_label: str = Field(default="Source A")
    side_a_refs: list[DraftSourceRef] = Field(default_factory=list)
    side_b_label: str | None = Field(default=None)
    side_b_refs: list[DraftSourceRef] = Field(default_factory=list)
    issue_tag: str | None = Field(default=None)
    date_text: str | None = Field(default=None)

    @field_validator("side_a_refs", "side_b_refs", mode="before")
    @classmethod
    def coerce_refs_list(cls, v: Any) -> list[Any]:
        if v is None:
            return []
        return list(v)[:5] if isinstance(v, list) else []

    @field_validator("title", "observed_evidence_summary", "model_interpretation", mode="before")
    @classmethod
    def coerce_non_empty_str(cls, v: Any) -> str:
        text = str(v or "").strip()
        return text[:1500] if text else "Not specified"


class ContradictionAnalysisDraft(BaseModel):
    summary: str = Field(min_length=1)
    findings: list[DraftContradictionFinding] = Field(default_factory=list)
    timeline: list[DraftTimelineEvent] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @field_validator("findings", "timeline", "missing_information", "limitations", mode="before")
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


class VerifiedContradictionFinding(BaseModel):
    finding_id: str
    category: FindingCategory
    dimension: ConflictDimension
    severity: FindingSeverity
    title: str
    observed_evidence_summary: str
    model_interpretation: str
    side_a_label: str
    side_a_sources: list[VerifiedSourceRef] = Field(default_factory=list)
    side_b_label: str | None = None
    side_b_sources: list[VerifiedSourceRef] = Field(default_factory=list)
    support: SupportStatus
    issue_tag: str | None = None
    date_text: str | None = None
    date_sort_key: str = "9999-99-99"


class ContradictionResult(BaseModel):
    workflow_id: str
    case_id: str
    generated_at: datetime
    provider: str
    model: str
    is_mock: bool
    workflow_version: str = CONTRADICTION_WORKFLOW_VERSION
    prompt_version: str = CONTRADICTION_PROMPT_VERSION
    result_schema_version: str = CONTRADICTION_RESULT_SCHEMA_VERSION
    insufficient_sources: bool = False
    summary: str
    findings: list[VerifiedContradictionFinding] = Field(default_factory=list)
    timeline: list[VerifiedTimelineEvent] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    verification: VerificationSummary
    source_manifest: list[SourceManifestEntry] = Field(default_factory=list)
    source_stats: SourceStats
    professional_review_required: bool = True
    input_metadata: dict[str, Any] = Field(default_factory=dict)
