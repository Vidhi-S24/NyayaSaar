"""Stage 9 Precedent Explorer analyst node.

Calls the configured LLM to identify legal authorities, citation relationships,
and potential conflicts from retrieved legal records and case document sources.
When no AI provider is configured, returns a clearly-labelled development fixture.
Never fabricates citations or holds fixture data out as real law.
"""

from __future__ import annotations

import logging

from app.agents.context import WorkflowContext
from app.agents.schemas_precedent import PrecedentSearchDraft
from app.agents.state import CaseAnalysisState
from app.ai.base import ProviderError, StructuredRequest, estimate_tokens
from app.ai.prompts.precedent_v9 import (
    PRECEDENT_SYSTEM_PROMPT,
    build_precedent_prompt,
)

logger = logging.getLogger("nyayasaar.agents.precedent_analyst_v9")


def _mock_fixture(state: CaseAnalysisState) -> dict:
    """Deterministic development fixture — clearly labelled, never real law."""
    sources = state.get("sources") or []
    retrieved = (state.get("case_context") or {}).get("retrieved_records") or []
    authorities: list[dict] = []
    citation_pairs: list[dict] = []
    conflicts: list[dict] = []

    if retrieved:
        rec = retrieved[0]
        is_fixture = rec.get("is_fixture", True)
        authorities.append(
            {
                "citation_text": f"[Development fixture] {rec.get('citation', 'Unknown citation')}",
                "title": rec.get("title", "[title not available]"),
                "court": rec.get("court", "[court not available]"),
                "jurisdiction": rec.get("jurisdiction", "[jurisdiction not available]"),
                "decision_date": rec.get("decision_date") or rec.get("year", "[date not available]"),
                "holding_summary": (
                    "[Development fixture] No AI model was called. "
                    "Configure an AI provider for real authority analysis."
                ),
                "source_id": "R1",
                "source_provider": rec.get("source_provider", "fixture"),
                "is_fixture": is_fixture,
                "relevance_note": "[Development fixture] Placeholder authority entry.",
            }
        )
        if len(retrieved) > 1:
            rec2 = retrieved[1]
            authorities.append(
                {
                    "citation_text": f"[Development fixture] {rec2.get('citation', 'Unknown citation')}",
                    "title": rec2.get("title", "[title not available]"),
                    "court": rec2.get("court", "[court not available]"),
                    "jurisdiction": rec2.get("jurisdiction", "[jurisdiction not available]"),
                    "decision_date": rec2.get("decision_date") or rec2.get("year", "[date not available]"),
                    "holding_summary": "[Development fixture] No AI model was called.",
                    "source_id": "R2",
                    "source_provider": rec2.get("source_provider", "fixture"),
                    "is_fixture": rec2.get("is_fixture", True),
                    "relevance_note": "[Development fixture]",
                }
            )
            citation_pairs.append(
                {
                    "from_citation": f"[Development fixture] {rec.get('citation', 'Authority 1')}",
                    "to_citation": f"[Development fixture] {rec2.get('citation', 'Authority 2')}",
                    "relationship_type": "cites",
                    "supporting_passage": "[Development fixture] No AI model was called.",
                    "source_ref": {"source_id": "R1", "quote": ""},
                    "confidence": "low",
                }
            )
            conflicts.append(
                {
                    "title": "[Development fixture] Potential reasoning comparison",
                    "interpretation_a": f"[Development fixture] Passage from R1: {rec.get('title', '')}",
                    "interpretation_b": f"[Development fixture] Passage from R2: {rec2.get('title', '')}",
                    "source_a_ref": {"source_id": "R1", "quote": ""},
                    "source_b_ref": {"source_id": "R2", "quote": ""},
                    "model_note": (
                        "[Development fixture] These entries demonstrate the conflict interface only. "
                        "No AI model was called; configure AI_PROVIDER, AI_MODEL, AI_API_KEY for real analysis."
                    ),
                }
            )
    elif sources:
        s0 = sources[0]
        authorities.append(
            {
                "citation_text": "[Development fixture — NOT A REAL CITATION]",
                "title": "Development Fixture — No Retrieved Legal Records",
                "court": "[court not available]",
                "jurisdiction": "[jurisdiction not available]",
                "decision_date": "[date not available]",
                "holding_summary": (
                    "[Development fixture] No legal records were retrieved and no AI model was called. "
                    "Connect a legal corpus and configure an AI provider for real precedent search."
                ),
                "source_id": s0.get("source_id", "S1"),
                "source_provider": "fixture",
                "is_fixture": True,
                "relevance_note": "[Development fixture]",
            }
        )

    return {
        "authorities": authorities,
        "citation_pairs": citation_pairs,
        "potential_conflicts": conflicts,
        "summary": (
            "[Development fixture] Prepared from "
            f"{len(sources)} case source page(s) and {len(retrieved)} retrieved legal record(s). "
            "No AI model was called; configure AI_PROVIDER, AI_MODEL, and AI_API_KEY for real "
            "precedent explorer analysis."
        ),
        "limitations": [
            "Development fixture only — not AI-generated legal analysis.",
            "Fixture authorities are NOT real legal authorities and must NOT be cited.",
            "AI-assisted legal research requires independent professional verification.",
            "Authorities sourced from configured corpus only; corpus coverage may be incomplete.",
        ],
    }


def make_precedent_analyst_v9_node(ctx: WorkflowContext):
    """Build the Stage 9 precedent analyst node."""

    async def precedent_analyst(state: CaseAnalysisState) -> dict:
        await ctx.report_step(
            "precedent_analyst",
            45,
            "Analysing retrieved legal records and identifying authorities",
        )

        budget_code = ctx.budget_exceeded_code(state)
        if budget_code:
            return ctx.budget_exceeded_state(budget_code)

        calls = int(state.get("llm_calls", 0))
        usage = state.get("token_usage") or {"input": 0, "output": 0, "total": 0}
        case_context = state.get("case_context") or {}

        prompt = build_precedent_prompt(
            case_context=case_context,
            sources=state.get("sources") or [],
            retrieved_records=case_context.get("retrieved_records") or None,
            focus=case_context.get("focus"),
            verification_feedback=state.get("verification_feedback") or [],
        )

        request = StructuredRequest(
            system_prompt=PRECEDENT_SYSTEM_PROMPT,
            user_prompt=prompt,
            output_schema=PrecedentSearchDraft,
            temperature=ctx.settings.ai_temperature,
            max_output_tokens=ctx.settings.ai_max_output_tokens,
            timeout_s=ctx.settings.ai_timeout_s,
            mock_fixture=_mock_fixture(state) if ctx.provider.is_mock else None,
            metadata={"stage": "precedent_analyst_v9"},
        )

        try:
            result = await ctx.provider.generate_structured(request)
        except ProviderError as exc:
            logger.warning("Precedent analyst provider error code=%s", exc.code)
            return {
                "status": "failed",
                "current_step": "provider_error",
                "progress": 100,
                "outcome": exc.code,
                "errors": [{"code": exc.code, "message": exc.message}],
            }
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Precedent analyst unexpected error type=%s", type(exc).__name__)
            return {
                "status": "failed",
                "current_step": "internal_error",
                "progress": 100,
                "outcome": "internal_error",
                "errors": [
                    {
                        "code": "internal_error",
                        "message": "The precedent analysis failed unexpectedly.",
                    }
                ],
            }

        draft = result.output
        if not isinstance(draft, PrecedentSearchDraft):
            return {
                "status": "failed",
                "current_step": "invalid_model_output",
                "progress": 100,
                "outcome": "invalid_model_output",
                "errors": [
                    {
                        "code": "invalid_model_output",
                        "message": "The model returned an unexpected output type.",
                    }
                ],
            }

        input_tokens = (
            result.input_tokens
            if result.input_tokens is not None
            else estimate_tokens(prompt)
        )
        output_tokens = (
            result.output_tokens
            if result.output_tokens is not None
            else estimate_tokens(draft.model_dump_json())
        )
        new_usage = {
            "input": int(usage.get("input", 0)) + int(input_tokens),
            "output": int(usage.get("output", 0)) + int(output_tokens),
        }
        new_usage["total"] = new_usage["input"] + new_usage["output"]

        exhausted = new_usage["total"] >= ctx.max_total_tokens
        notes = list(state.get("notes") or [])
        if exhausted:
            notes.append(
                "The workflow reached its token budget; no further model calls will be made."
            )

        return {
            "draft": draft.model_dump(),
            "status": "running",
            "current_step": "precedent_verifier",
            "progress": 75,
            "outcome": None,
            "llm_calls": calls + 1,
            "token_usage": new_usage,
            "token_budget_exhausted": exhausted,
            "notes": notes,
            "needs_revision": False,
            "revision_target": None,
        }

    return precedent_analyst
