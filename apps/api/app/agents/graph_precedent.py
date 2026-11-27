"""LangGraph workflow for Stage 9 — Precedent Explorer & Conflict Detector.

    START -> orchestrator --(insufficient sources)--> finalize -> END
                 |
                 +--> precedent_analyst -> precedent_verifier
                              ^                    |
                              +--(needs revision)--+
                                                   |
                                                   +--> finalize -> END
"""

from __future__ import annotations

from datetime import datetime, timezone

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.context import WorkflowContext
from app.agents.graph import ormsgpack  # noqa: F401 - ensures Windows shim is loaded
from app.agents.nodes.orchestrator import make_orchestrator_node
from app.agents.nodes.precedent_analyst_v9 import make_precedent_analyst_v9_node
from app.agents.nodes.precedent_verifier import make_precedent_verifier_node
from app.agents.schemas import SourceStats, VerificationSummary
from app.agents.schemas_precedent import (
    PRECEDENT_PROMPT_VERSION,
    PRECEDENT_RESULT_SCHEMA_VERSION,
    PRECEDENT_WORKFLOW_VERSION,
    PrecedentResult,
)
from app.agents.state import CaseAnalysisState


def _insufficient_precedent_result(state: CaseAnalysisState) -> PrecedentResult:
    notes = list(state.get("notes") or [])
    stats = SourceStats(**(state.get("source_stats") or {}))
    return PrecedentResult(
        workflow_id=str(state.get("workflow_id", "")),
        case_id=str(state.get("case_id", "")),
        generated_at=datetime.now(timezone.utc),
        provider=str(state.get("provider_name", "none")),
        model=str(state.get("model_name", "none")),
        is_mock=bool(state.get("is_mock", False)),
        workflow_version=PRECEDENT_WORKFLOW_VERSION,
        prompt_version=PRECEDENT_PROMPT_VERSION,
        result_schema_version=PRECEDENT_RESULT_SCHEMA_VERSION,
        corpus_configured=False,
        insufficient_sources=True,
        summary=(
            "No usable extracted text was available for the selected documents, "
            "so no precedent search could be performed."
        ),
        authorities=[],
        citation_pairs=[],
        potential_conflicts=[],
        limitations=[
            "Upload and complete text extraction for at least one document before running Precedent Explorer.",
            "AI-assisted legal research requires independent professional verification.",
            "Authorities sourced from configured corpus only; corpus coverage may be incomplete.",
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


def _make_precedent_finalize_node(ctx: WorkflowContext):
    async def finalize(state: CaseAnalysisState) -> dict:
        await ctx.report_step("finalize", 100, "Finalising precedent analysis")

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
            result = _insufficient_precedent_result(state)
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
                    "message": "The precedent workflow finished without a result.",
                }
            ],
        }

    return finalize


def _route_after_orchestrator(state: CaseAnalysisState) -> str:
    if state.get("status") == "failed" or state.get("outcome") == "insufficient_sources":
        return "finalize"
    return "precedent_analyst"


def _route_after_analyst(state: CaseAnalysisState) -> str:
    if state.get("status") == "failed":
        return "finalize"
    return "precedent_verifier"


def _route_after_verifier(state: CaseAnalysisState) -> str:
    if state.get("status") == "failed":
        return "finalize"
    if state.get("needs_revision"):
        return "precedent_analyst"
    return "finalize"


def build_precedent_graph(ctx: WorkflowContext):
    graph = StateGraph(CaseAnalysisState)

    graph.add_node("orchestrator", make_orchestrator_node(ctx))
    graph.add_node("precedent_analyst", make_precedent_analyst_v9_node(ctx))
    graph.add_node("precedent_verifier", make_precedent_verifier_node(ctx))
    graph.add_node("finalize", _make_precedent_finalize_node(ctx))

    graph.add_edge(START, "orchestrator")
    graph.add_conditional_edges(
        "orchestrator",
        _route_after_orchestrator,
        {"precedent_analyst": "precedent_analyst", "finalize": "finalize"},
    )
    graph.add_conditional_edges(
        "precedent_analyst",
        _route_after_analyst,
        {"precedent_verifier": "precedent_verifier", "finalize": "finalize"},
    )
    graph.add_conditional_edges(
        "precedent_verifier",
        _route_after_verifier,
        {"precedent_analyst": "precedent_analyst", "finalize": "finalize"},
    )
    graph.add_edge("finalize", END)

    return graph.compile(checkpointer=MemorySaver())


async def run_precedent_graph(
    ctx: WorkflowContext,
    initial_state: CaseAnalysisState,
) -> CaseAnalysisState:
    graph = build_precedent_graph(ctx)
    config = {
        "configurable": {"thread_id": initial_state.get("workflow_id", "workflow")},
        "recursion_limit": 16,
    }
    return await graph.ainvoke(initial_state, config=config)  # type: ignore[return-value]
