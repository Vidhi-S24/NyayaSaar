"""Stage 10 — Advocate Mode analyst node.

Develops structured arguments for BOTH sides from uploaded case documents and
retrieved legal-corpus records. Produces an ``AdvocateDraft`` in state for
deterministic verification by ``stage10_verifier``.
"""

from __future__ import annotations

import logging

from app.agents.context import WorkflowContext
from app.agents.schemas_stage10 import AdvocateDraft
from app.agents.state import CaseAnalysisState
from app.ai.base import ProviderError, StructuredRequest, estimate_tokens
from app.ai.prompts.advocate import (
    ADVOCATE_ANALYST_SYSTEM_PROMPT,
    build_advocate_prompt,
)

logger = logging.getLogger("nyayasaar.agents.advocate_analyst")


def _mock_advocate_draft(state: CaseAnalysisState) -> dict:
    """Deterministic fixture — clearly labelled, no AI was called."""
    sources = state.get("sources") or []
    retrieved = (state.get("case_context") or {}).get("retrieved_records") or []
    first_s = sources[0].get("source_id", "S1") if sources else ""
    first_r = "R1" if retrieved else ""
    s_ref = [{"source_id": first_s, "quote": ""}] if first_s else []
    r_ref = [{"source_id": first_r, "quote": ""}] if first_r else []
    preferred_side = str((state.get("case_context") or {}).get("preferred_side") or "both")

    return {
        "selected_issue": state.get("focus") or "Primary disputed issue in case record",
        "summary": (
            f"[Development fixture] Advocate Mode prepared from {len(sources)} source page(s) "
            f"and {len(retrieved)} retrieved record(s) (side focus: {preferred_side}). "
            "No AI model was called."
        ),
        "relevant_facts": [
            f"[Development fixture] Source record {first_s or 'N/A'} loaded for review."
        ],
        "claimant_arguments": [
            {
                "argument_id": "A-C1",
                "side": "claimant",
                "issue": state.get("focus") or "Core claim",
                "claim": "[Development fixture] Claimant position grounded in uploaded record.",
                "reasoning": "Configure an AI provider for substantive legal argument synthesis.",
                "tier": "moderate_supported" if first_s else "speculative",
                "strength": "low",
                "supporting_sources": s_ref + r_ref,
                "opposing_sources": [],
                "authority_refs": [retrieved[0].get("citation", "R1")] if retrieved else [],
                "counterarguments": ["[Development fixture] Subject to evidentiary verification."],
                "evidentiary_gap": True,
                "gap_description": "Fixture mode active — no AI model was called.",
            }
        ],
        "respondent_arguments": [
            {
                "argument_id": "A-R1",
                "side": "respondent",
                "issue": state.get("focus") or "Core defence",
                "claim": "[Development fixture] Respondent counter-position from uploaded record.",
                "reasoning": "Configure an AI provider for substantive counter-argument synthesis.",
                "tier": "moderate_supported" if first_s else "speculative",
                "strength": "low",
                "supporting_sources": s_ref,
                "opposing_sources": [],
                "authority_refs": [],
                "counterarguments": ["[Development fixture] Contrary material preserved for review."],
                "evidentiary_gap": True,
                "gap_description": "Fixture mode active — no AI model was called.",
            }
        ],
        "evidentiary_gaps": [
            {
                "description": "[Development fixture] Configure an AI provider for real gap analysis.",
                "missing_evidence_type": "document",
                "affected_claim": "A-C1 / A-R1",
                "source_refs": s_ref,
            }
        ],
        "unresolved_questions": [
            "[Development fixture] Independent legal verification required."
        ],
        "strengths": ["[Development fixture] Source provenance preserved."],
        "weaknesses": ["[Development fixture] Fixture mode — configure AI_PROVIDER for live analysis."],
        "limitations": [
            "Development fixture only — not AI-generated legal analysis.",
            "Research tool only — does not constitute legal advice.",
        ],
    }


def make_advocate_analyst_node(ctx: WorkflowContext):
    async def advocate_analyst(state: CaseAnalysisState) -> dict:
        await ctx.report_step(
            "advocate_analyst",
            50,
            "Developing arguments, counterarguments, and evidentiary gaps for both sides",
        )

        sources = state.get("sources") or []
        case_ctx = state.get("case_context") or {}
        preferred_side = str(case_ctx.get("preferred_side") or "both")
        llm_calls = int(state.get("llm_calls") or 0)
        max_calls = int(state.get("max_llm_calls") or 4)
        usage = dict(state.get("token_usage") or {})

        if llm_calls >= max_calls:
            return {
                "status": "failed",
                "current_step": "budget_exceeded",
                "progress": 100,
                "outcome": "budget_exceeded",
                "errors": [
                    {
                        "code": "budget_exceeded",
                        "message": "The workflow reached its bounded model-call limit.",
                    }
                ],
            }

        if ctx.provider.is_mock:
            raw = _mock_advocate_draft(state)
            draft = AdvocateDraft.model_validate(raw)
            return {
                "draft": draft.model_dump(mode="json"),
                "llm_calls": llm_calls + 1,
                "current_step": "advocate_analyst",
                "progress": 70,
            }

        prompt = build_advocate_prompt(
            case_context=case_ctx,
            sources=sources,
            focus=state.get("focus"),
            preferred_side=preferred_side,
            revision_feedback=state.get("revision_feedback") or None,
        )

        try:
            resp = await ctx.provider.generate_structured(
                StructuredRequest(
                    system_prompt=ADVOCATE_ANALYST_SYSTEM_PROMPT,
                    user_prompt=prompt,
                    output_schema=AdvocateDraft,
                    max_output_tokens=min(ctx.settings.ai_max_output_tokens, 3200),
                    temperature=0.1,
                    timeout_s=ctx.settings.ai_timeout_s,
                )
            )
        except ProviderError as exc:
            logger.warning("Advocate analyst provider error: %s", exc.code)
            return {
                "status": "failed",
                "current_step": "provider_error",
                "progress": 100,
                "outcome": exc.code,
                "errors": [{"code": exc.code, "message": exc.message}],
            }

        usage["input_tokens"] = int(usage.get("input_tokens") or 0) + (
            resp.input_tokens or estimate_tokens(prompt)
        )
        usage["output_tokens"] = int(usage.get("output_tokens") or 0) + (
            resp.output_tokens or 0
        )
        usage["total_tokens"] = int(usage["input_tokens"]) + int(usage["output_tokens"])

        return {
            "draft": resp.output.model_dump(mode="json"),
            "llm_calls": llm_calls + 1,
            "token_usage": usage,
            "current_step": "advocate_analyst",
            "progress": 70,
        }

    return advocate_analyst
