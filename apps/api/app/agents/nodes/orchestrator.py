"""Orchestrator (source planner) node.

The orchestrator does not call the model. It validates that the workflow has
usable source text, records source-quality statistics, and routes to the Case
Analyst or to a clear insufficient-source result. Keeping this deterministic
makes the graph's entry behaviour testable.
"""

from __future__ import annotations

from app.agents.context import WorkflowContext
from app.agents.state import CaseAnalysisState


def make_orchestrator_node(ctx: WorkflowContext):
    async def orchestrator(state: CaseAnalysisState) -> dict:
        await ctx.report_step("orchestrator", 12, "Preparing and de-duplicating sources")

        sources = state.get("sources") or []
        notes = list(state.get("source_notes") or [])
        stats = dict(state.get("source_stats") or {})

        total_chars = sum(len(str(source.get("text", ""))) for source in sources)
        min_chars = int(getattr(ctx.settings, "agent_min_source_chars", 120))
        stats["characters_included"] = total_chars
        stats["documents_analyzed"] = len(
            {str(source.get("document_id")) for source in sources}
        )
        stats["pages_included"] = len(sources)

        if not sources:
            return {
                "status": "running",
                "current_step": "insufficient_sources",
                "progress": 20,
                "outcome": "insufficient_sources",
                "source_stats": stats,
                "notes": notes
                + ["No usable source text was available; no AI model was called."],
                "errors": [],
            }

        if total_chars < min_chars:
            return {
                "status": "running",
                "current_step": "insufficient_sources",
                "progress": 20,
                "outcome": "insufficient_sources",
                "source_stats": stats,
                "notes": notes
                + [
                    "The usable extracted text is too short for a reliable "
                    "analysis (under "
                    f"{min_chars} characters); no AI model was called."
                ],
                "errors": [],
            }

        if stats.get("short_pages"):
            notes.append(
                f"{stats['short_pages']} included page(s) are very short and may "
                "be scans or partially extracted text."
            )
        if stats.get("instruction_like_sources"):
            notes.append(
                "Instruction-like text was detected inside source pages and was "
                "treated as evidence only."
            )

        return {
            "status": "running",
            "current_step": "case_analyst",
            "progress": 22,
            "outcome": None,
            "source_stats": stats,
            "notes": notes,
            "errors": [],
            "retry_count": state.get("retry_count", 0),
            "llm_calls": state.get("llm_calls", 0),
            "token_usage": state.get(
                "token_usage", {"input": 0, "output": 0, "total": 0}
            ),
        }

    return orchestrator
