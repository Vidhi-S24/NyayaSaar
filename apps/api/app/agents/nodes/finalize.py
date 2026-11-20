"""Finalize node — produces a result even when the workflow cannot analyse."""

from __future__ import annotations

from datetime import datetime, timezone

from app.agents.context import WorkflowContext
from app.agents.schemas import CaseAnalysisResult, VerificationSummary
from app.agents.state import CaseAnalysisState


def _insufficient_result(state: CaseAnalysisState) -> CaseAnalysisResult:
    notes = list(state.get("notes") or [])
    return CaseAnalysisResult(
        workflow_id=str(state.get("workflow_id", "")),
        case_id=str(state.get("case_id", "")),
        generated_at=datetime.now(timezone.utc),
        provider=str(state.get("provider_name", "none")),
        model=str(state.get("model_name", "none")),
        is_mock=bool(state.get("is_mock", False)),
        insufficient_sources=True,
        summary=(
            "No usable extracted text was available for this case, so no case "
            "analysis could be produced."
        ),
        parties=[],
        facts=[],
        legal_issues=[],
        timeline=[],
        inferences=[],
        unverified_hypotheses=[],
        missing_information=[
            "Add at least one document with completed text extraction before "
            "running the analysis."
        ],
        limitations=[
            "No analysis was generated because the source material was "
            "insufficient.",
            "AI-assisted output requires independent professional legal "
            "verification.",
        ],
        verification=VerificationSummary(notes=notes),
        source_manifest=[],
    )


def make_finalize_node(ctx: WorkflowContext):
    async def finalize(state: CaseAnalysisState) -> dict:
        await ctx.report_step("finalize", 100, "Finalising analysis")

        if state.get("status") == "failed":
            return {
                "status": "failed",
                "current_step": "failed",
                "progress": 100,
            }

        if state.get("result"):
            return {
                "status": "completed",
                "current_step": "completed",
                "progress": 100,
                "outcome": "completed",
            }

        if state.get("outcome") == "insufficient_sources":
            result = _insufficient_result(state)
            return {
                "result": result.model_dump(mode="json"),
                "status": "completed",
                "current_step": "completed",
                "progress": 100,
                "outcome": "insufficient_sources",
            }

        return {
            "status": "failed",
            "current_step": "internal_error",
            "progress": 100,
            "outcome": "internal_error",
            "errors": [
                {
                    "code": "internal_error",
                    "message": "The workflow finished without a result.",
                }
            ],
        }

    return finalize
