"""API schemas for Stage 6 Case Intelligence workflows."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.agents.schemas import CaseAnalysisResult

if TYPE_CHECKING:
    from app.db.models.workflow import WorkflowRun as WorkflowRunModel

DocumentId = Annotated[str, StringConstraints(min_length=1, max_length=36)]


class CaseAnalysisRequest(BaseModel):
    """Optional analysis inputs. Empty body = analyse all ready documents."""

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
    result: CaseAnalysisResult | None = None
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
