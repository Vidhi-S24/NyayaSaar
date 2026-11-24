"""Typed contracts for the Case Intelligence workflow.

The *draft* models are what the LLMs are asked to produce. The *verified* models
are what the deterministic verifier produces after checking every claim against
the source excerpts. Keeping them separate prevents model output from being
mistaken for verified analysis.

Stage 6 splits the model work across two specialist stages:

* ``CaseAnalysisDraft`` — extraction of facts, parties, entities, amounts,
  procedural history, and dated events from the supplied sources.
* ``EvidenceAnalysisDraft`` — legal issues, evidence questions, ambiguities,
  and inferences derived from the extraction.

Both stages only see bounded, source-marked excerpts. The verifier never calls
a model.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Confidence = Literal["high", "medium", "low"]
SupportStatus = Literal["supported", "partially_supported", "unsupported"]
ClaimType = Literal["fact", "legal_issue", "inference"]
EntityType = Literal[
    "person",
    "organisation",
    "court",
    "location",
    "statute_or_regulation",
    "amount",
    "date",
    "other",
]
DatePrecision = Literal["day", "month", "year", "unknown"]
TimelineSignificance = Literal["procedural", "factual", "evidential", "other"]
IssueType = Literal["substantive", "procedural", "evidential", "remedial", "other"]
UncertaintySeverity = Literal["high", "medium", "low"]

CASE_INTELLIGENCE_WORKFLOW_VERSION = "6.1.0"
CASE_INTELLIGENCE_PROMPT_VERSION = "2026-11-case-intelligence-v2"
CASE_INTELLIGENCE_RESULT_SCHEMA_VERSION = "6.1"


# ---------------------------------------------------------------------------
# Shared draft primitives
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


class DraftEntity(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    entity_type: EntityType = "other"
    role: str | None = Field(default=None, max_length=300)
    source_refs: list[DraftSourceRef] = Field(default_factory=list, max_length=4)
    confidence: Confidence = "medium"


class DraftParty(BaseModel):
    """A litigant or party named in the supplied sources."""

    name: str = Field(min_length=1, max_length=200)
    role: str | None = Field(
        default=None,
        max_length=200,
        description="Procedural role stated in the document, e.g. Petitioner.",
    )
    source_refs: list[DraftSourceRef] = Field(default_factory=list, max_length=4)
    confidence: Confidence = "medium"


class DraftAmount(BaseModel):
    description: str = Field(min_length=2, max_length=300)
    amount_text: str = Field(min_length=1, max_length=120)
    currency: str | None = Field(default=None, max_length=20)
    source_refs: list[DraftSourceRef] = Field(default_factory=list, max_length=4)
    confidence: Confidence = "medium"


class DraftProceduralEvent(BaseModel):
    stage: str = Field(min_length=2, max_length=160)
    description: str = Field(min_length=3, max_length=700)
    date_text: str | None = Field(default=None, max_length=120)
    forum: str | None = Field(default=None, max_length=200)
    source_refs: list[DraftSourceRef] = Field(default_factory=list, max_length=4)


class DraftTimelineEvent(BaseModel):
    date_text: str = Field(min_length=1, max_length=120)
    event: str = Field(min_length=3, max_length=700)
    significance: TimelineSignificance = "factual"
    source_refs: list[DraftSourceRef] = Field(default_factory=list, max_length=4)


class DraftKeyDate(BaseModel):
    date_text: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=2, max_length=200)
    source_refs: list[DraftSourceRef] = Field(default_factory=list, max_length=4)


# ---------------------------------------------------------------------------
# Stage A — Case Analyst extraction draft
# ---------------------------------------------------------------------------


class CaseAnalysisDraft(BaseModel):
    """Structured extraction requested from the Case Analyst model.

    Legal-issue fields are retained as optional for backward compatibility with
    Stage 5 fixtures and direct verifier tests. The Stage 6 Case Analyst prompt
    asks that they be left empty; the Evidence Analyst owns them.
    """

    summary: str = Field(
        min_length=10,
        max_length=2500,
        description="Neutral summary of what the supplied documents establish.",
    )
    parties: list[DraftParty] = Field(default_factory=list, max_length=10)
    entities: list[DraftEntity] = Field(default_factory=list, max_length=20)
    amounts: list[DraftAmount] = Field(default_factory=list, max_length=10)
    facts: list[DraftClaim] = Field(default_factory=list, max_length=15)
    procedural_history: list[DraftProceduralEvent] = Field(
        default_factory=list, max_length=12
    )
    key_dates: list[DraftKeyDate] = Field(default_factory=list, max_length=12)
    timeline: list[DraftTimelineEvent] = Field(default_factory=list, max_length=15)

    # Optional/legacy fields. Stage 6 keeps them so Stage 5 callers and tests
    # continue to work; the evidence analyst supplies the richer models below.
    legal_issues: list[DraftClaim] = Field(default_factory=list, max_length=10)
    inferences: list[DraftClaim] = Field(default_factory=list, max_length=8)
    unverified_hypotheses: list[str] = Field(default_factory=list, max_length=8)
    missing_information: list[str] = Field(default_factory=list, max_length=8)
    limitations: list[str] = Field(default_factory=list, max_length=6)


# ---------------------------------------------------------------------------
# Stage B — Evidence Analyst draft
# ---------------------------------------------------------------------------


class DraftLegalIssue(BaseModel):
    question: str = Field(min_length=5, max_length=500)
    why_it_matters: str = Field(min_length=5, max_length=700)
    issue_type: IssueType = "other"
    source_refs: list[DraftSourceRef] = Field(default_factory=list, max_length=4)
    confidence: Confidence = "medium"


class DraftEvidenceQuestion(BaseModel):
    question: str = Field(min_length=5, max_length=500)
    why_it_matters: str = Field(min_length=5, max_length=600)
    evidence_needed: str = Field(min_length=3, max_length=600)
    source_refs: list[DraftSourceRef] = Field(default_factory=list, max_length=4)


class DraftUncertainty(BaseModel):
    statement: str = Field(min_length=3, max_length=600)
    reason: str = Field(min_length=3, max_length=500)
    severity: UncertaintySeverity = "medium"
    source_refs: list[DraftSourceRef] = Field(default_factory=list, max_length=4)


class EvidenceAnalysisDraft(BaseModel):
    legal_issues: list[DraftLegalIssue] = Field(default_factory=list, max_length=10)
    evidence_questions: list[DraftEvidenceQuestion] = Field(
        default_factory=list, max_length=12
    )
    ambiguities: list[DraftUncertainty] = Field(default_factory=list, max_length=10)
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
    # Offsets are relative to the supplied source excerpt, not the full file.
    # They are only present when the verifier located the quote deterministically.
    span_start: int | None = None
    span_end: int | None = None


class VerifiedClaim(BaseModel):
    claim: str
    claim_type: ClaimType
    sources: list[VerifiedSourceRef] = Field(default_factory=list)
    support: SupportStatus
    confidence: Confidence = "medium"


class VerifiedEntity(BaseModel):
    name: str
    entity_type: EntityType = "other"
    role: str | None = None
    sources: list[VerifiedSourceRef] = Field(default_factory=list)
    support: SupportStatus
    confidence: Confidence = "medium"


class VerifiedParty(BaseModel):
    name: str
    role: str | None = None
    sources: list[VerifiedSourceRef] = Field(default_factory=list)
    support: SupportStatus
    confidence: Confidence = "medium"


class VerifiedAmount(BaseModel):
    description: str
    amount_text: str
    currency: str | None = None
    sources: list[VerifiedSourceRef] = Field(default_factory=list)
    support: SupportStatus
    confidence: Confidence = "medium"


class VerifiedProceduralEvent(BaseModel):
    stage: str
    description: str
    date_text: str | None = None
    date_sort_key: str = ""
    date_precision: DatePrecision = "unknown"
    date_ambiguous: bool = False
    forum: str | None = None
    sources: list[VerifiedSourceRef] = Field(default_factory=list)
    support: SupportStatus


class VerifiedTimelineEvent(BaseModel):
    date_text: str
    date_sort_key: str = ""
    date_precision: DatePrecision = "unknown"
    date_ambiguous: bool = False
    date_ambiguity_note: str | None = None
    event: str
    significance: TimelineSignificance = "factual"
    sources: list[VerifiedSourceRef] = Field(default_factory=list)
    support: SupportStatus


class VerifiedLegalIssue(BaseModel):
    question: str
    why_it_matters: str
    issue_type: IssueType = "other"
    sources: list[VerifiedSourceRef] = Field(default_factory=list)
    support: SupportStatus
    confidence: Confidence = "medium"


class VerifiedEvidenceQuestion(BaseModel):
    question: str
    why_it_matters: str
    evidence_needed: str
    sources: list[VerifiedSourceRef] = Field(default_factory=list)
    support: SupportStatus


class VerifiedUncertainty(BaseModel):
    statement: str
    reason: str
    severity: UncertaintySeverity = "medium"
    sources: list[VerifiedSourceRef] = Field(default_factory=list)
    support: SupportStatus


class VerificationCategoryCount(BaseModel):
    category: str
    total: int = 0
    supported: int = 0
    partially_supported: int = 0
    unsupported: int = 0


class VerificationSummary(BaseModel):
    total_claims: int = 0
    supported: int = 0
    partially_supported: int = 0
    unsupported: int = 0
    invalid_source_refs: int = 0
    verified_spans: int = 0
    unverified_quotes: int = 0
    retried: bool = False
    categories: list[VerificationCategoryCount] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class SourceStats(BaseModel):
    documents_available: int = 0
    documents_analyzed: int = 0
    pages_available: int = 0
    pages_included: int = 0
    characters_included: int = 0
    duplicate_pages_skipped: int = 0
    short_pages: int = 0
    truncated_pages: int = 0
    omitted_pages: int = 0
    failed_documents: int = 0
    ocr_required_documents: int = 0
    incomplete_extraction_documents: int = 0
    instruction_like_sources: int = 0


class SourceManifestEntry(BaseModel):
    source_id: str
    document_id: str
    document_name: str
    page_number: int
    truncated: bool = False
    short: bool = False


class CaseAnalysisResult(BaseModel):
    workflow_id: str
    case_id: str
    generated_at: datetime
    provider: str
    model: str
    is_mock: bool
    workflow_version: str = CASE_INTELLIGENCE_WORKFLOW_VERSION
    prompt_version: str = CASE_INTELLIGENCE_PROMPT_VERSION
    result_schema_version: str = CASE_INTELLIGENCE_RESULT_SCHEMA_VERSION
    insufficient_sources: bool = False
    summary: str
    parties: list[VerifiedParty] = Field(default_factory=list)
    entities: list[VerifiedEntity] = Field(default_factory=list)
    amounts: list[VerifiedAmount] = Field(default_factory=list)
    facts: list[VerifiedClaim] = Field(default_factory=list)
    procedural_history: list[VerifiedProceduralEvent] = Field(default_factory=list)
    legal_issues: list[VerifiedClaim] = Field(default_factory=list)
    issue_analysis: list[VerifiedLegalIssue] = Field(default_factory=list)
    evidence_questions: list[VerifiedEvidenceQuestion] = Field(default_factory=list)
    ambiguities: list[VerifiedUncertainty] = Field(default_factory=list)
    timeline: list[VerifiedTimelineEvent] = Field(default_factory=list)
    inferences: list[VerifiedClaim] = Field(default_factory=list)
    unverified_hypotheses: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    verification: VerificationSummary
    source_manifest: list[SourceManifestEntry] = Field(default_factory=list)
    source_stats: SourceStats = Field(default_factory=SourceStats)
    professional_review_required: bool = True
    input_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("parties", mode="before")
    @classmethod
    def _coerce_legacy_parties(cls, value: Any) -> Any:
        """Read pre-6.1 string-only parties as honestly unsupported records.

        Older persisted runs stored parties as bare names with no source. They
        must not disappear or be presented as verified. Coercing them keeps old
        results readable while making the missing provenance explicit.
        """
        if not value:
            return []
        coerced: list[Any] = []
        for item in value:
            if isinstance(item, str):
                coerced.append(
                    {
                        "name": item,
                        "role": None,
                        "sources": [],
                        "support": "unsupported",
                        "confidence": "low",
                    }
                )
            else:
                coerced.append(item)
        return coerced
