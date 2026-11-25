"""LangGraph workflow for Stage 8 — Contradiction & Gap Hunter.

    START -> orchestrator --(insufficient sources)--> finalize -> END
                 |
                 +--> contradiction_analyst -> contradiction_verifier
                              ^                        |
                              +---(needs revision)-----+
                                                       |
                                                       +--> finalize -> END
"""

from __future__ import annotations

from datetime import datetime, timezone

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.context import WorkflowContext
from app.agents.graph import ormsgpack  # noqa: F401 - ensures Windows shim is loaded
from app.agents.nodes.contradiction_analyst import make_contradiction_analyst_node
from app.agents.nodes.contradiction_verifier import make_contradiction_verifier_node
from app.agents.nodes.orchestrator import make_orchestrator_node
from app.agents.schemas import SourceStats, VerificationSummary
from app.agents.schemas_contradiction import (
    CONTRADICTION_PROMPT_VERSION,
    CONTRADICTION_RESULT_SCHEMA_VERSION,
    CONTRADICTION_WORKFLOW_VERSION,
    ContradictionResult,
)
from app.agents.state import CaseAnalysisState


def _insufficient_contradiction_result(state: CaseAnalysisState) -> ContradictionResult:
    notes = list(state.get("notes") or [])
    stats = SourceStats(**(state.get("source_stats") or {}))
    return ContradictionResult(
        workflow_id=str(state.get("workflow_id", "")),
        case_id=str(state.get("case_id", "")),
        generated_at=datetime.now(timezone.utc),
        provider=str(state.get("provider_name", "none")),
        model=str(state.get("model_name", "none")),
        is_mock=bool(state.get("is_mock", False)),
        workflow_version=CONTRADICTION_WORKFLOW_VERSION,
        prompt_version=CONTRADICTION_PROMPT_VERSION,
        result_schema_version=CONTRADICTION_RESULT_SCHEMA_VERSION,
        insufficient_sources=True,
        summary=(
            "No usable extracted text was available for the selected documents, so "
            "no cross-document contradiction or gap analysis could be performed."
        ),
        findings=[],
        timeline=[],
        missing_information=[
            "Upload and complete text extraction for at least one (ideally two or more) documents before running Contradiction & Gap Hunter."
        ],
        limitations=[
            "No analysis was generated because the source material was insufficient.",
            "AI-assisted output requires independent professional legal verification.",
        ],
        verification=VerificationSummary(notes=notes),
        source_manifest=[],
        source_stats=stats,
        professional_review_required=True,
        input_metadata={
            "source_count": len(state.get("sources") or []),
            "documents_analyzed": int(stats.documents_analyzed),
            "focus_supplied": bool((state.get("case_context") or {}).get("focus")),
        },
    )


def _make_contradiction_finalize_node(ctx: WorkflowContext):
    async def finalize(state: CaseAnalysisState) -> dict:
        await ctx.report_step("finalize", 100, "Finalising contradiction analysis")

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
            result = _insufficient_contradiction_result(state)
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


def _route_after_orchestrator(state: CaseAnalysisState) -> str:
    if state.get("status") == "failed" or state.get("outcome") == "insufficient_sources":
        return "finalize"
    return "contradiction_analyst"


def _route_after_analyst(state: CaseAnalysisState) -> str:
    if state.get("status") == "failed":
        return "finalize"
    return "contradiction_verifier"


def _route_after_verifier(state: CaseAnalysisState) -> str:
    if state.get("status") == "failed":
        return "finalize"
    if state.get("needs_revision"):
        return "contradiction_analyst"
    return "finalize"


def build_contradiction_graph(ctx: WorkflowContext):
    graph = StateGraph(CaseAnalysisState)

    graph.add_node("orchestrator", make_orchestrator_node(ctx))
    graph.add_node("contradiction_analyst", make_contradiction_analyst_node(ctx))
    graph.add_node("contradiction_verifier", make_contradiction_verifier_node(ctx))
    graph.add_node("finalize", _make_contradiction_finalize_node(ctx))

    graph.add_edge(START, "orchestrator")
    graph.add_conditional_edges(
        "orchestrator",
        _route_after_orchestrator,
        {"contradiction_analyst": "contradiction_analyst", "finalize": "finalize"},
    )
    graph.add_conditional_edges(
        "contradiction_analyst",
        _route_after_analyst,
        {"contradiction_verifier": "contradiction_verifier", "finalize": "finalize"},
    )
    graph.add_conditional_edges(
        "contradiction_verifier",
        _route_after_verifier,
        {"contradiction_analyst": "contradiction_analyst", "finalize": "finalize"},
    )
    graph.add_edge("finalize", END)

    return graph.compile(checkpointer=MemorySaver())


async def run_contradiction_graph(
    ctx: WorkflowContext,
    initial_state: CaseAnalysisState,
) -> CaseAnalysisState:
    graph = build_contradiction_graph(ctx)
    config = {
        "configurable": {"thread_id": initial_state.get("workflow_id", "workflow")},
        "recursion_limit": 16,
    }
    return await graph.ainvoke(initial_state, config=config)  # type: ignore[return-value]
