"""API schemas for Stage 6 Case Intelligence workflows."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.agents.schemas import CaseAnalysisResult
from app.agents.schemas_contradiction import ContradictionResult, ReviewStatus
from app.agents.schemas_precedent import PrecedentResult
from app.agents.schemas_stage10 import AdvocateResult, JudgeResult

if TYPE_CHECKING:
    from app.db.models.workflow import WorkflowRun as WorkflowRunModel

DocumentId = Annotated[str, StringConstraints(min_length=1, max_length=36)]


class CaseAnalysisRequest(BaseModel):
    """Optional analysis inputs. Empty body = analyse all ready documents."""

    workflow_type: Literal[
        "case_analysis", "contradiction", "precedent", "advocate", "judge"
    ] = Field(
        default="case_analysis",
        description=(
            "Workflow to execute: case_analysis | contradiction | precedent | advocate | judge."
        ),
    )
    preferred_side: Literal["both", "claimant", "respondent"] = Field(
        default="both",
        description="Optional side focus for Advocate Mode (never suppresses contrary evidence).",
    )
    document_ids: list[DocumentId] | None = Field(
        default=None,
        max_length=50,
        description="Limit the analysis to these document IDs.",
    )
    focus: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional analyst focus. Treated as untrusted user input.",
    )

    @field_validator("focus")
    @classmethod
    def normalise_focus(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class WorkflowStepResponse(BaseModel):
    step: str
    status: str
    message: str | None = None
    at: str | None = None


class WorkflowErrorResponse(BaseModel):
    code: str
    message: str


class WorkflowRunResponse(BaseModel):
    id: str
    case_id: str
    workflow_type: str
    status: str
    progress: int
    current_step: str | None
    provider: str | None
    model: str | None
    is_mock: bool
    workflow_version: str | None = None
    prompt_version: str | None = None
    result_schema_version: str | None = None
    document_ids: list[str] = Field(default_factory=list)
    focus: str | None = None
    result: (
        CaseAnalysisResult
        | ContradictionResult
        | PrecedentResult
        | AdvocateResult
        | JudgeResult
        | dict[str, Any]
        | None
    ) = None
    steps: list[WorkflowStepResponse] = Field(default_factory=list)
    token_usage: dict[str, Any] = Field(default_factory=dict)
    error: WorkflowErrorResponse | None = None
    attempt_count: int = 0
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @classmethod
    def from_run(cls, run: WorkflowRunModel) -> WorkflowRunResponse:
        payload = run.input_payload or {}
        error = None
        if run.error_code:
            error = WorkflowErrorResponse(
                code=run.error_code,
                message=run.error_message or "The workflow failed.",
            )
        return cls(
            id=run.id,
            case_id=run.case_id,
            workflow_type=run.workflow_type,
            status=run.status,
            progress=run.progress,
            current_step=run.current_step,
            provider=run.provider,
            model=run.model,
            is_mock=run.is_mock,
            workflow_version=run.workflow_version,
            prompt_version=run.prompt_version,
            result_schema_version=run.result_schema_version,
            document_ids=payload.get("document_ids") or [],
            focus=payload.get("focus"),
            result=run.result,
            steps=run.steps or [],
            token_usage=run.token_usage or {},
            error=error,
            attempt_count=run.attempt_count,
            created_at=run.created_at,
            updated_at=run.updated_at,
            started_at=run.started_at,
            completed_at=run.completed_at,
        )


class WorkflowRunListResponse(BaseModel):
    items: list[WorkflowRunResponse]
    total: int


class AIStatusResponse(BaseModel):
    provider: str
    requested_provider: str
    model: str
    is_mock: bool
    configured: bool
    message: str


class FindingReviewRequest(BaseModel):
    status: ReviewStatus
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("note")
    @classmethod
    def clean_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class FindingReviewEventResponse(BaseModel):
    previous_status: str | None = None
    new_status: str
    note: str | None = None
    user_id: str
    user_email: str | None = None
    at: str


class FindingReviewResponse(BaseModel):
    id: str
    workflow_id: str
    case_id: str
    finding_id: str
    status: ReviewStatus
    reviewer_note: str | None = None
    updated_by_user_id: str
    updated_at: datetime
    history: list[FindingReviewEventResponse] = Field(default_factory=list)

    @classmethod
    def from_model(cls, row: Any) -> FindingReviewResponse:
        return cls(
            id=row.id,
            workflow_id=row.workflow_id,
            case_id=row.case_id,
            finding_id=row.finding_id,
            status=row.status,
            reviewer_note=row.reviewer_note,
            updated_by_user_id=row.updated_by_user_id,
            updated_at=row.updated_at,
            history=[
                FindingReviewEventResponse(**ev)
                for ev in (row.history or [])
            ],
        )


class FindingReviewListResponse(BaseModel):
    items: list[FindingReviewResponse] = Field(default_factory=list)


class CitationLinkResponse(BaseModel):
    id: str
    from_record_id: str
    to_record_id: str | None = None
    to_citation_text: str
    relationship_type: str
    source_passage: str | None = None
    source_provider: str
    is_resolved: bool
    confidence: str
    workflow_id: str | None = None
    created_at: datetime

    @classmethod
    def from_model(cls, row: Any) -> CitationLinkResponse:
        return cls(
            id=row.id,
            from_record_id=row.from_record_id,
            to_record_id=row.to_record_id,
            to_citation_text=row.to_citation_text,
            relationship_type=row.relationship_type,
            source_passage=row.source_passage,
            source_provider=row.source_provider,
            is_resolved=row.is_resolved,
            confidence=row.confidence,
            workflow_id=row.workflow_id,
            created_at=row.created_at,
        )


class CitationLinkListResponse(BaseModel):
    items: list[CitationLinkResponse]
    total: int
