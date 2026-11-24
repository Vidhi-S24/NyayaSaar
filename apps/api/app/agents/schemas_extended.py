"""Stage 6 extended schemas: Contradiction, Advocate, Judge, Precedent workflows.

None of these schemas permit fabricated legal authorities. Every claim must
reference a document source ID. ``professional_review_required`` is always True.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Version constants
# ---------------------------------------------------------------------------

CONTRADICTION_WORKFLOW_VERSION = "6.0.0"
CONTRADICTION_PROMPT_VERSION = "6.0.0"
CONTRADICTION_RESULT_SCHEMA_VERSION = "6.0.0"

ADVOCATE_WORKFLOW_VERSION = "6.0.0"
ADVOCATE_PROMPT_VERSION = "6.0.0"
ADVOCATE_RESULT_SCHEMA_VERSION = "6.0.0"

JUDGE_WORKFLOW_VERSION = "6.0.0"
JUDGE_PROMPT_VERSION = "6.0.0"
JUDGE_RESULT_SCHEMA_VERSION = "6.0.0"

PRECEDENT_WORKFLOW_VERSION = "6.0.0"
PRECEDENT_PROMPT_VERSION = "6.0.0"
PRECEDENT_RESULT_SCHEMA_VERSION = "6.0.0"


# ---------------------------------------------------------------------------
# Shared sub-types
# ---------------------------------------------------------------------------


class SourceRef(BaseModel):
    source_id: str = Field(description="Source marker, e.g. S1, S2")
    quote: str = Field(default="", max_length=400, description="Verbatim excerpt")
    # Resolved deterministically from the source manifest. Empty/None means the
    # marker could not be matched to a real document page.
    document_id: str = Field(default="")
    document_name: str = Field(default="")
    page_number: int | None = Field(default=None)
    quote_verified: bool = Field(
        default=False,
        description="True only when the quote was found verbatim in the cited page.",
    )


class ExtendedVerification(BaseModel):
    """Deterministic citation-resolution summary for extended workflows."""

    total_source_refs: int = 0
    verified_quotes: int = 0
    unresolved_refs: int = 0
    notes: list[str] = Field(default_factory=list)



class SeverityLevel(str):
    """high | medium | low"""


# ---------------------------------------------------------------------------
# Contradiction & Gap Hunter
# ---------------------------------------------------------------------------


class ContradictionItem(BaseModel):
    description: str = Field(max_length=600)
    document_a_ref: SourceRef
    document_b_ref: SourceRef
    conflict_type: str = Field(
        default="factual",
        description="factual | date | amount | procedural | statement",
    )
    significance: str = Field(default="medium", description="high | medium | low")


class GapItem(BaseModel):
    description: str = Field(max_length=500)
    missing_evidence_type: str = Field(
        default="document",
        description="document | testimony | expert | other",
    )
    affected_claim: str = Field(default="", max_length=300)
    source_refs: list[SourceRef] = Field(default_factory=list)


class UnsupportedAssertionItem(BaseModel):
    assertion: str = Field(max_length=500)
    reason: str = Field(max_length=400)
    source_refs: list[SourceRef] = Field(default_factory=list)


class TimelineConflictItem(BaseModel):
    description: str = Field(max_length=400)
    date_a: str = Field(default="")
    date_b: str = Field(default="")
    source_a_ref: SourceRef | None = None
    source_b_ref: SourceRef | None = None


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
    summary: str
    contradictions: list[ContradictionItem] = Field(default_factory=list)
    gaps: list[GapItem] = Field(default_factory=list)
    unsupported_assertions: list[UnsupportedAssertionItem] = Field(default_factory=list)
    timeline_conflicts: list[TimelineConflictItem] = Field(default_factory=list)
    verification: ExtendedVerification = Field(default_factory=ExtendedVerification)
    limitations: list[str] = Field(default_factory=list)
    professional_review_required: bool = True
    input_metadata: dict[str, Any] = Field(default_factory=dict)


# Draft produced by the analyst node before persisting
class ContradictionDraft(BaseModel):
    summary: str = Field(default="")
    contradictions: list[dict] = Field(default_factory=list)
    gaps: list[dict] = Field(default_factory=list)
    unsupported_assertions: list[dict] = Field(default_factory=list)
    timeline_conflicts: list[dict] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Advocate Mode
# ---------------------------------------------------------------------------


class ArgumentItem(BaseModel):
    claim: str = Field(max_length=600)
    reasoning: str = Field(max_length=600)
    strength: str = Field(default="medium", description="high | medium | low")
    supporting_sources: list[SourceRef] = Field(default_factory=list)
    opposing_sources: list[SourceRef] = Field(default_factory=list)
    evidentiary_gap: bool = False
    gap_description: str = Field(default="", max_length=300)


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
    summary: str
    claimant_arguments: list[ArgumentItem] = Field(default_factory=list)
    respondent_arguments: list[ArgumentItem] = Field(default_factory=list)
    evidentiary_gaps: list[GapItem] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    verification: ExtendedVerification = Field(default_factory=ExtendedVerification)
    limitations: list[str] = Field(default_factory=list)
    professional_review_required: bool = True
    research_tool_disclaimer: str = (
        "Research tool only. This output does not constitute legal advice, "
        "does not replace qualified counsel, and must not be used to file "
        "or serve documents autonomously."
    )
    input_metadata: dict[str, Any] = Field(default_factory=dict)


class AdvocateDraft(BaseModel):
    summary: str = Field(default="")
    claimant_arguments: list[dict] = Field(default_factory=list)
    respondent_arguments: list[dict] = Field(default_factory=list)
    evidentiary_gaps: list[dict] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Judge / Clerk Mode
# ---------------------------------------------------------------------------


class AuditItem(BaseModel):
    item: str = Field(max_length=500)
    finding: str = Field(max_length=500)
    severity: str = Field(default="medium", description="high | medium | low")
    source_refs: list[SourceRef] = Field(default_factory=list)


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
    summary: str
    issue_coverage: list[AuditItem] = Field(default_factory=list)
    reasoning_consistency: list[AuditItem] = Field(default_factory=list)
    source_support_audit: list[AuditItem] = Field(default_factory=list)
    citation_integrity: list[AuditItem] = Field(default_factory=list)
    unresolved_questions: list[AuditItem] = Field(default_factory=list)
    overall_assessment: str = ""
    verification: ExtendedVerification = Field(default_factory=ExtendedVerification)
    limitations: list[str] = Field(default_factory=list)
    professional_review_required: bool = True
    input_metadata: dict[str, Any] = Field(default_factory=dict)


class JudgeDraft(BaseModel):
    summary: str = Field(default="")
    issue_coverage: list[dict] = Field(default_factory=list)
    reasoning_consistency: list[dict] = Field(default_factory=list)
    source_support_audit: list[dict] = Field(default_factory=list)
    citation_integrity: list[dict] = Field(default_factory=list)
    unresolved_questions: list[dict] = Field(default_factory=list)
    overall_assessment: str = Field(default="")
    limitations: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Precedent Explorer (interface + clearly-labelled fixture)
# ---------------------------------------------------------------------------


class AuthorityResult(BaseModel):
    """A single legal authority result.

    ``is_fixture`` is always True when no corpus is configured. Never present
    fixture authorities as real law or real precedent.
    """

    authority_id: str = Field(default="")
    citation: str = Field(default="")
    title: str = Field(default="")
    court: str = Field(default="")
    year: str = Field(default="")
    holding_summary: str = Field(default="")
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    is_fixture: bool = True
    corpus_configured: bool = False


class PrecedentResult(BaseModel):
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
    query_used: str = ""
    authorities: list[AuthorityResult] = Field(default_factory=list)
    summary: str = ""
    verification: ExtendedVerification = Field(default_factory=ExtendedVerification)
    limitations: list[str] = Field(default_factory=list)
    professional_review_required: bool = True
    input_metadata: dict[str, Any] = Field(default_factory=dict)
