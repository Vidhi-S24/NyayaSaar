"""Stage 10 schemas for Advocate Mode and Judge/Clerk Mode workflows.

Both modes reuse Stage 6 verified source references, verification summaries,
and source manifests. Neither mode permits fabricated legal authorities or
presents AI outputs as authoritative legal advice or judicial rulings.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.agents.schemas import (
    SourceManifestEntry,
    SourceStats,
    SupportStatus,
    VerificationSummary,
    VerifiedSourceRef,
)

# ---------------------------------------------------------------------------
# Version constants
# ---------------------------------------------------------------------------

ADVOCATE_WORKFLOW_VERSION = "10.0.0"
ADVOCATE_PROMPT_VERSION = "2026-11-advocate-v1"
ADVOCATE_RESULT_SCHEMA_VERSION = "10.0"

JUDGE_WORKFLOW_VERSION = "10.0.0"
JUDGE_PROMPT_VERSION = "2026-11-judge-v1"
JUDGE_RESULT_SCHEMA_VERSION = "10.0"


# ---------------------------------------------------------------------------
# Advocate Mode
# ---------------------------------------------------------------------------


class DraftAdvocateSourceRef(BaseModel):
    source_id: str = Field(default="", max_length=20)
    quote: str = Field(default="", max_length=240)


class DraftAdvocateArgument(BaseModel):
    argument_id: str = Field(default="", max_length=40)
    side: Literal["claimant", "respondent"] = "claimant"
    issue: str = Field(default="", max_length=300)
    claim: str = Field(default="", max_length=600)
    reasoning: str = Field(default="", max_length=900)
    tier: Literal["strong_supported", "moderate_supported", "speculative"] = (
        "moderate_supported"
    )
    strength: Literal["high", "medium", "low"] = "medium"
    supporting_sources: list[DraftAdvocateSourceRef] = Field(default_factory=list)
    opposing_sources: list[DraftAdvocateSourceRef] = Field(default_factory=list)
    authority_refs: list[str] = Field(default_factory=list)
    counterarguments: list[str] = Field(default_factory=list)
    evidentiary_gap: bool = False
    gap_description: str = Field(default="", max_length=400)

    @field_validator("side", mode="before")
    @classmethod
    def _norm_side(cls, v: Any) -> str:
        s = str(v or "claimant").strip().lower()
        return s if s in ("claimant", "respondent") else "claimant"

    @field_validator("tier", mode="before")
    @classmethod
    def _norm_tier(cls, v: Any) -> str:
        s = str(v or "moderate_supported").strip().lower()
        return s if s in ("strong_supported", "moderate_supported", "speculative") else "moderate_supported"

    @field_validator("strength", mode="before")
    @classmethod
    def _norm_strength(cls, v: Any) -> str:
        s = str(v or "medium").strip().lower()
        return s if s in ("high", "medium", "low") else "medium"


class DraftAdvocateGap(BaseModel):
    description: str = Field(default="", max_length=500)
    missing_evidence_type: Literal["document", "testimony", "expert", "authority", "other"] = "document"
    affected_claim: str = Field(default="", max_length=300)
    source_refs: list[DraftAdvocateSourceRef] = Field(default_factory=list)

    @field_validator("missing_evidence_type", mode="before")
    @classmethod
    def _norm_gap_type(cls, v: Any) -> str:
        s = str(v or "document").strip().lower()
        return s if s in ("document", "testimony", "expert", "authority", "other") else "other"


class AdvocateDraft(BaseModel):
    selected_issue: str = Field(default="", max_length=300)
    summary: str = Field(default="", max_length=2000)
    relevant_facts: list[str] = Field(default_factory=list)
    claimant_arguments: list[DraftAdvocateArgument] = Field(default_factory=list)
    respondent_arguments: list[DraftAdvocateArgument] = Field(default_factory=list)
    evidentiary_gaps: list[DraftAdvocateGap] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class VerifiedAdvocateArgument(BaseModel):
    argument_id: str
    side: Literal["claimant", "respondent"]
    issue: str = ""
    claim: str
    reasoning: str
    tier: Literal["strong_supported", "moderate_supported", "speculative"]
    strength: Literal["high", "medium", "low"]
    supporting_sources: list[VerifiedSourceRef] = Field(default_factory=list)
    opposing_sources: list[VerifiedSourceRef] = Field(default_factory=list)
    authority_refs: list[str] = Field(default_factory=list)
    counterarguments: list[str] = Field(default_factory=list)
    evidentiary_gap: bool = False
    gap_description: str = ""
    support: SupportStatus = "unsupported"


class VerifiedAdvocateGap(BaseModel):
    description: str
    missing_evidence_type: str = "document"
    affected_claim: str = ""
    source_refs: list[VerifiedSourceRef] = Field(default_factory=list)


class AdvocateResult(BaseModel):
    workflow_id: str
    case_id: str
    generated_at: datetime
    provider: str
    model: str
    is_mock: bool
    workflow_version: str = ADVOCATE_WORKFLOW_VERSION
    prompt_version: str = ADVOCATE_PROMPT_VERSION
    result_schema_version: str = ADVOCATE_RESULT_SCHEMA_VERSION
    insufficient_sources: bool = False
    preferred_side: Literal["both", "claimant", "respondent"] = "both"
    selected_issue: str = ""
    summary: str
    relevant_facts: list[str] = Field(default_factory=list)
    claimant_arguments: list[VerifiedAdvocateArgument] = Field(default_factory=list)
    respondent_arguments: list[VerifiedAdvocateArgument] = Field(default_factory=list)
    evidentiary_gaps: list[VerifiedAdvocateGap] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    verification: VerificationSummary = Field(default_factory=VerificationSummary)
    source_manifest: list[SourceManifestEntry] = Field(default_factory=list)
    source_stats: SourceStats = Field(default_factory=SourceStats)
    limitations: list[str] = Field(default_factory=list)
    professional_review_required: bool = True
    research_tool_disclaimer: str = (
        "Research tool only. This output does not constitute legal advice, "
        "does not replace qualified counsel, and must not be used to file "
        "or serve documents autonomously."
    )
    input_metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Judge / Clerk Mode
# ---------------------------------------------------------------------------

JudgeAuditStatus = Literal[
    "covered",
    "partially_covered",
    "unsupported",
    "inconsistent",
    "missing_citation",
    "unresolved",
]


class DraftJudgeAuditItem(BaseModel):
    audit_id: str = Field(default="", max_length=40)
    item: str = Field(default="", max_length=500)
    finding: str = Field(default="", max_length=800)
    status: JudgeAuditStatus = "partially_covered"
    severity: Literal["high", "medium", "low"] = "medium"
    opposing_considered: bool | None = None
    source_refs: list[DraftAdvocateSourceRef] = Field(default_factory=list)

    @field_validator("status", mode="before")
    @classmethod
    def _norm_status(cls, v: Any) -> str:
        s = str(v or "partially_covered").strip().lower()
        allowed = (
            "covered",
            "partially_covered",
            "unsupported",
            "inconsistent",
            "missing_citation",
            "unresolved",
        )
        return s if s in allowed else "partially_covered"

    @field_validator("severity", mode="before")
    @classmethod
    def _norm_severity(cls, v: Any) -> str:
        s = str(v or "medium").strip().lower()
        return s if s in ("high", "medium", "low") else "medium"


class JudgeDraft(BaseModel):
    summary: str = Field(default="", max_length=2000)
    issue_coverage: list[DraftJudgeAuditItem] = Field(default_factory=list)
    reasoning_consistency: list[DraftJudgeAuditItem] = Field(default_factory=list)
    source_support_audit: list[DraftJudgeAuditItem] = Field(default_factory=list)
    citation_integrity: list[DraftJudgeAuditItem] = Field(default_factory=list)
    opposing_consideration_audit: list[DraftJudgeAuditItem] = Field(default_factory=list)
    unresolved_questions: list[DraftJudgeAuditItem] = Field(default_factory=list)
    overall_assessment: str = Field(default="", max_length=1000)
    limitations: list[str] = Field(default_factory=list)


class VerifiedJudgeAuditItem(BaseModel):
    audit_id: str
    item: str
    finding: str
    status: JudgeAuditStatus = "partially_covered"
    severity: Literal["high", "medium", "low"] = "medium"
    opposing_considered: bool | None = None
    source_refs: list[VerifiedSourceRef] = Field(default_factory=list)
    support: SupportStatus = "unsupported"


class JudgeResult(BaseModel):
    workflow_id: str
    case_id: str
    generated_at: datetime
    provider: str
    model: str
    is_mock: bool
    workflow_version: str = JUDGE_WORKFLOW_VERSION
    prompt_version: str = JUDGE_PROMPT_VERSION
    result_schema_version: str = JUDGE_RESULT_SCHEMA_VERSION
    insufficient_sources: bool = False
    summary: str
    issue_coverage: list[VerifiedJudgeAuditItem] = Field(default_factory=list)
    reasoning_consistency: list[VerifiedJudgeAuditItem] = Field(default_factory=list)
    source_support_audit: list[VerifiedJudgeAuditItem] = Field(default_factory=list)
    citation_integrity: list[VerifiedJudgeAuditItem] = Field(default_factory=list)
    opposing_consideration_audit: list[VerifiedJudgeAuditItem] = Field(default_factory=list)
    unresolved_questions: list[VerifiedJudgeAuditItem] = Field(default_factory=list)
    overall_assessment: str = ""
    verification: VerificationSummary = Field(default_factory=VerificationSummary)
    source_manifest: list[SourceManifestEntry] = Field(default_factory=list)
    source_stats: SourceStats = Field(default_factory=SourceStats)
    limitations: list[str] = Field(default_factory=list)
    professional_review_required: bool = True
    judicial_audit_disclaimer: str = (
        "Reasoning-audit assistant only — not a simulated judicial authority, "
        "not an official court decision, and not legal advice."
    )
    input_metadata: dict[str, Any] = Field(default_factory=dict)
