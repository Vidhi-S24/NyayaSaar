"""LangGraph workflows for Stage 10 — Advocate Mode and Judge/Clerk Mode.

Both workflows share the bounded Stage 6–9 topology:
    START -> orchestrator --(insufficient sources)--> finalize -> END
                 |
                 +--> analyst -> verifier --(needs revision)--> analyst
                                    |
                                    +--> finalize -> END
"""

from __future__ import annotations

from datetime import datetime, timezone

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.context import WorkflowContext
from app.agents.graph import ormsgpack  # noqa: F401 - ensures Windows shim is loaded
from app.agents.nodes.advocate_analyst import make_advocate_analyst_node
from app.agents.nodes.judge_analyst import make_judge_analyst_node
from app.agents.nodes.orchestrator import make_orchestrator_node
from app.agents.nodes.stage10_verifier import (
    ADVOCATE_REQUIRED_LIMITATIONS,
    JUDGE_REQUIRED_LIMITATIONS,
    make_advocate_verifier_node,
    make_judge_verifier_node,
)
from app.agents.schemas import SourceStats, VerificationSummary
from app.agents.schemas_stage10 import (
    ADVOCATE_PROMPT_VERSION,
    ADVOCATE_RESULT_SCHEMA_VERSION,
    ADVOCATE_WORKFLOW_VERSION,
    JUDGE_PROMPT_VERSION,
    JUDGE_RESULT_SCHEMA_VERSION,
    JUDGE_WORKFLOW_VERSION,
    AdvocateResult,
    JudgeResult,
)
from app.agents.state import CaseAnalysisState


def _insufficient_advocate_result(state: CaseAnalysisState) -> AdvocateResult:
    notes = list(state.get("notes") or [])
    stats = SourceStats(**(state.get("source_stats") or {}))
    return AdvocateResult(
        workflow_id=str(state.get("workflow_id", "")),
        case_id=str(state.get("case_id", "")),
        generated_at=datetime.now(timezone.utc),
        provider=str(state.get("provider_name", "none")),
        model=str(state.get("model_name", "none")),
        is_mock=bool(state.get("is_mock", False)),
        workflow_version=ADVOCATE_WORKFLOW_VERSION,
        prompt_version=ADVOCATE_PROMPT_VERSION,
        result_schema_version=ADVOCATE_RESULT_SCHEMA_VERSION,
        insufficient_sources=True,
        summary=(
            "No usable extracted text was available for the selected documents, "
            "so no Advocate Mode argument analysis could be performed."
        ),
        limitations=[
            "Upload and complete text extraction for at least one document before running Advocate Mode.",
            *ADVOCATE_REQUIRED_LIMITATIONS,
        ],
        verification=VerificationSummary(notes=notes),
        source_manifest=[],
        source_stats=stats,
        professional_review_required=True,
        input_metadata={
            "source_count": len(state.get("sources") or []),
            "documents_analyzed": int(stats.documents_analyzed),
        },
    )


def _insufficient_judge_result(state: CaseAnalysisState) -> JudgeResult:
    notes = list(state.get("notes") or [])
    stats = SourceStats(**(state.get("source_stats") or {}))
    return JudgeResult(
        workflow_id=str(state.get("workflow_id", "")),
        case_id=str(state.get("case_id", "")),
        generated_at=datetime.now(timezone.utc),
        provider=str(state.get("provider_name", "none")),
        model=str(state.get("model_name", "none")),
        is_mock=bool(state.get("is_mock", False)),
        workflow_version=JUDGE_WORKFLOW_VERSION,
        prompt_version=JUDGE_PROMPT_VERSION,
        result_schema_version=JUDGE_RESULT_SCHEMA_VERSION,
        insufficient_sources=True,
        summary=(
            "No usable extracted text was available for the selected documents, "
            "so no Judge/Clerk reasoning audit could be performed."
        ),
        limitations=[
            "Upload and complete text extraction for at least one document before running Judge/Clerk Mode.",
            *JUDGE_REQUIRED_LIMITATIONS,
        ],
        verification=VerificationSummary(notes=notes),
        source_manifest=[],
        source_stats=stats,
        professional_review_required=True,
        input_metadata={
            "source_count": len(state.get("sources") or []),
            "documents_analyzed": int(stats.documents_analyzed),
        },
    )


def _make_finalize_node(ctx: WorkflowContext, insufficient_fn, label: str):
    async def finalize(state: CaseAnalysisState) -> dict:
        await ctx.report_step("finalize", 100, f"Finalising {label}")

        if state.get("status") == "failed":
            return {"status": "failed", "current_step": "failed", "progress": 100}

        if state.get("result"):
            return {
                "status": "completed",
                "current_step": "completed",
                "progress": 100,
                "outcome": "completed",
            }

        if state.get("outcome") == "insufficient_sources":
            result = insufficient_fn(state)
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
                    "message": f"The {label} workflow finished without a result.",
                }
            ],
        }

    return finalize


def _build_mode_graph(
    ctx: WorkflowContext,
    *,
    analyst_name: str,
    analyst_node,
    verifier_name: str,
    verifier_node,
    insufficient_fn,
    label: str,
):
    def route_after_orchestrator(state: CaseAnalysisState) -> str:
        if state.get("status") == "failed" or state.get("outcome") == "insufficient_sources":
            return "finalize"
        return analyst_name

    def route_after_analyst(state: CaseAnalysisState) -> str:
        if state.get("status") == "failed":
            return "finalize"
        return verifier_name

    def route_after_verifier(state: CaseAnalysisState) -> str:
        if state.get("status") == "failed":
            return "finalize"
        if state.get("revision_needed"):
            return analyst_name
        return "finalize"

    builder = StateGraph(CaseAnalysisState)
    builder.add_node("orchestrator", make_orchestrator_node(ctx))
    builder.add_node(analyst_name, analyst_node)
    builder.add_node(verifier_name, verifier_node)
    builder.add_node("finalize", _make_finalize_node(ctx, insufficient_fn, label))

    builder.add_edge(START, "orchestrator")
    builder.add_conditional_edges(
        "orchestrator",
        route_after_orchestrator,
        {analyst_name: analyst_name, "finalize": "finalize"},
    )
    builder.add_conditional_edges(
        analyst_name,
        route_after_analyst,
        {verifier_name: verifier_name, "finalize": "finalize"},
    )
    builder.add_conditional_edges(
        verifier_name,
        route_after_verifier,
        {analyst_name: analyst_name, "finalize": "finalize"},
    )
    builder.add_edge("finalize", END)

    return builder.compile(checkpointer=MemorySaver())


async def run_advocate_graph(
    ctx: WorkflowContext, initial_state: CaseAnalysisState
) -> CaseAnalysisState:
    graph = _build_mode_graph(
        ctx,
        analyst_name="advocate_analyst",
        analyst_node=make_advocate_analyst_node(ctx),
        verifier_name="advocate_verifier",
        verifier_node=make_advocate_verifier_node(ctx),
        insufficient_fn=_insufficient_advocate_result,
        label="Advocate Mode",
    )
    config = {"configurable": {"thread_id": initial_state["workflow_id"]}}
    return await graph.ainvoke(initial_state, config=config)


async def run_judge_graph(
    ctx: WorkflowContext, initial_state: CaseAnalysisState
) -> CaseAnalysisState:
    graph = _build_mode_graph(
        ctx,
        analyst_name="judge_analyst",
        analyst_node=make_judge_analyst_node(ctx),
        verifier_name="judge_verifier",
        verifier_node=make_judge_verifier_node(ctx),
        insufficient_fn=_insufficient_judge_result,
        label="Judge/Clerk audit",
    )
    config = {"configurable": {"thread_id": initial_state["workflow_id"]}}
    return await graph.ainvoke(initial_state, config=config)
