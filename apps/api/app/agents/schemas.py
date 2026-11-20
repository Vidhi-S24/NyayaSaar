"""Typed contracts for the Case Intelligence workflow.

The *draft* models are what the LLM is asked to produce. The *verified* models
are what the deterministic verifier produces after checking every claim against
the source excerpts. Keeping them separate prevents model output from being
mistaken for verified analysis.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["high", "medium", "low"]
SupportStatus = Literal["supported", "partially_supported", "unsupported"]
ClaimType = Literal["fact", "legal_issue", "inference"]


# ---------------------------------------------------------------------------
# LLM draft
# ---------------------------------------------------------------------------


class DraftSourceRef(BaseModel):
    """A reference to a supplied source marker (S1, S2, ...)."""

    source_id: str = Field(
        min_length=2,
        max_length=20,
        description="Source marker from the prompt, e.g. S1.",
    )
    quote: str | None = Field(
        default=None,
        max_length=400,
        description="Short verbatim excerpt supporting the claim, if available.",
    )


class DraftClaim(BaseModel):
    claim: str = Field(min_length=3, max_length=700)
    source_refs: list[DraftSourceRef] = Field(default_factory=list, max_length=4)
    confidence: Confidence = "medium"


class DraftTimelineEvent(BaseModel):
    date_text: str = Field(min_length=1, max_length=120)
    event: str = Field(min_length=3, max_length=700)
    source_refs: list[DraftSourceRef] = Field(default_factory=list, max_length=4)


class CaseAnalysisDraft(BaseModel):
    """The only structured output requested from the Case Analyst model."""

    summary: str = Field(
        min_length=10,
        max_length=2500,
        description="Neutral summary of what the supplied documents establish.",
    )
    parties: list[str] = Field(default_factory=list, max_length=10)
    facts: list[DraftClaim] = Field(default_factory=list, max_length=15)
    legal_issues: list[DraftClaim] = Field(default_factory=list, max_length=10)
    timeline: list[DraftTimelineEvent] = Field(default_factory=list, max_length=15)
    inferences: list[DraftClaim] = Field(default_factory=list, max_length=8)
    unverified_hypotheses: list[str] = Field(default_factory=list, max_length=8)
    missing_information: list[str] = Field(default_factory=list, max_length=8)
    limitations: list[str] = Field(default_factory=list, max_length=6)


# ---------------------------------------------------------------------------
# Verified result
# ---------------------------------------------------------------------------


class VerifiedSourceRef(BaseModel):
    source_id: str
    document_id: str
    document_name: str
    page_number: int
    quote: str | None = None
    quote_verified: bool = False


class VerifiedClaim(BaseModel):
    claim: str
    claim_type: ClaimType
    sources: list[VerifiedSourceRef] = Field(default_factory=list)
    support: SupportStatus
    confidence: Confidence = "medium"


class VerifiedTimelineEvent(BaseModel):
    date_text: str
    event: str
    sources: list[VerifiedSourceRef] = Field(default_factory=list)
    support: SupportStatus


class VerificationSummary(BaseModel):
    total_claims: int = 0
    supported: int = 0
    partially_supported: int = 0
    unsupported: int = 0
    invalid_source_refs: int = 0
    retried: bool = False
    notes: list[str] = Field(default_factory=list)


class SourceManifestEntry(BaseModel):
    source_id: str
    document_id: str
    document_name: str
    page_number: int
    truncated: bool = False


class CaseAnalysisResult(BaseModel):
    workflow_id: str
    case_id: str
    generated_at: datetime
    provider: str
    model: str
    is_mock: bool
    insufficient_sources: bool = False
    summary: str
    parties: list[str] = Field(default_factory=list)
    facts: list[VerifiedClaim] = Field(default_factory=list)
    legal_issues: list[VerifiedClaim] = Field(default_factory=list)
    timeline: list[VerifiedTimelineEvent] = Field(default_factory=list)
    inferences: list[VerifiedClaim] = Field(default_factory=list)
    unverified_hypotheses: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    verification: VerificationSummary
    source_manifest: list[SourceManifestEntry] = Field(default_factory=list)
