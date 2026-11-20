"""Orchestrator node.

The orchestrator does not call the model. It validates that the workflow has
usable source text and routes to the analyst or to a clear insufficient-source
result. Keeping this deterministic makes the graph's entry behaviour testable.
"""

from __future__ import annotations

from app.agents.context import WorkflowContext
from app.agents.state import CaseAnalysisState


def make_orchestrator_node(ctx: WorkflowContext):
    async def orchestrator(state: CaseAnalysisState) -> dict:
        await ctx.report_step("orchestrator", 15, "Preparing case sources")

        sources = state.get("sources") or []
        notes = list(state.get("source_notes") or [])

        if not sources:
            return {
                "status": "running",
                "current_step": "insufficient_sources",
                "progress": 20,
                "outcome": "insufficient_sources",
                "notes": notes
                + ["No usable source text was available; no AI model was called."],
                "errors": [],
            }

        return {
            "status": "running",
            "current_step": "case_analyst",
            "progress": 25,
            "outcome": None,
            "notes": notes,
            "errors": [],
            "retry_count": state.get("retry_count", 0),
            "llm_calls": state.get("llm_calls", 0),
            "token_usage": state.get("token_usage", {"input": 0, "output": 0, "total": 0}),
        }

    return orchestrator
