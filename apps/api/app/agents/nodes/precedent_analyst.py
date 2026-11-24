"""Precedent Explorer analyst node (Stage 6).

No external legal corpus is configured. This node implements the interface
and returns a clearly-labelled fixture. It NEVER fabricates citations or
presents fixture data as real legal authority.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.agents.context import WorkflowContext
from app.agents.schemas_extended import (
    PRECEDENT_PROMPT_VERSION,
    PRECEDENT_RESULT_SCHEMA_VERSION,
    PRECEDENT_WORKFLOW_VERSION,
    AuthorityResult,
    PrecedentResult,
)
from app.agents.state import CaseAnalysisState
from app.ai.prompts.precedent import CORPUS_NOT_CONFIGURED_MESSAGE

logger = logging.getLogger("nyayasaar.agents.precedent_analyst")


def _make_corpus_not_configured_result(state: CaseAnalysisState) -> PrecedentResult:
    """Return a clearly-labelled fixture when no corpus is connected."""
    sources = state.get("sources") or []
    case_context = state.get("case_context") or {}
    query = case_context.get("focus") or case_context.get("title") or "general legal research"

    return PrecedentResult(
        workflow_id=str(state.get("workflow_id", "")),
        case_id=str(state.get("case_id", "")),
        generated_at=datetime.now(timezone.utc),
        provider=str(state.get("provider_name", "none")),
        model=str(state.get("model_name", "none")),
        is_mock=True,
        workflow_version=PRECEDENT_WORKFLOW_VERSION,
        result_schema_version=PRECEDENT_RESULT_SCHEMA_VERSION,
        corpus_configured=False,
        query_used=str(query)[:200],
        authorities=[
            AuthorityResult(
                authority_id="fixture-001",
                citation="[FIXTURE — not a real citation]",
                title="Corpus Not Configured — Interface Demonstration",
                court="N/A",
                year="N/A",
                holding_summary=(
                    "This is a placeholder demonstrating the Precedent Explorer interface. "
                    "No real legal authority corpus is connected. "
                    "Connect an authorised legal database in production."
                ),
                relevance_score=0.0,
                is_fixture=True,
                corpus_configured=False,
            )
        ],
        summary=CORPUS_NOT_CONFIGURED_MESSAGE,
        limitations=[
            "No legal corpus is configured — no real authorities were searched.",
            "Fixture authorities are NOT real legal authorities and must NOT be cited.",
            "Connect an authorised legal database in production for real precedent search.",
            "Professional legal review required before any reliance on search results.",
        ],
        professional_review_required=True,
        input_metadata={
            "source_count": len(sources),
            "prompt_version": PRECEDENT_PROMPT_VERSION,
            "corpus_configured": False,
        },
    )


def make_precedent_analyst_node(ctx: WorkflowContext):
    """Precedent Explorer node.

    When corpus_configured is False (the current state), always returns the
    fixture result. When a real LegalCorpusProvider is integrated in a later
    stage, replace this with a real corpus search call.
    """

    async def precedent_analyst(state: CaseAnalysisState) -> dict:
        await ctx.report_step(
            "precedent_analyst",
            40,
            "Searching legal authority corpus (no corpus configured — returning fixture)",
        )

        # No corpus is configured — return fixture immediately (no LLM call).
        result = _make_corpus_not_configured_result(state)

        return {
            "result": result.model_dump(mode="json"),
            "status": "running",
            "current_step": "finalize",
            "progress": 85,
            "outcome": None,
            "notes": list(state.get("notes") or []),
        }

    return precedent_analyst
