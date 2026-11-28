"""Stage 10 — Judge / Clerk Mode analyst node.

Audits uploaded case documents and retrieved legal records for issue coverage,
reasoning consistency, source support, citation integrity, consideration of
opposing points, and unresolved questions. Produces a ``JudgeDraft`` in state
for deterministic verification by ``stage10_verifier``.
"""

from __future__ import annotations

import logging

from app.agents.context import WorkflowContext
from app.agents.schemas_stage10 import JudgeDraft
from app.agents.state import CaseAnalysisState
from app.ai.base import ProviderError, StructuredRequest, estimate_tokens
from app.ai.prompts.judge import (
    JUDGE_CLERK_SYSTEM_PROMPT,
    build_judge_prompt,
)

logger = logging.getLogger("nyayasaar.agents.judge_analyst")


def _mock_judge_draft(state: CaseAnalysisState) -> dict:
    """Deterministic fixture — clearly labelled, no AI was called."""
    sources = state.get("sources") or []
    retrieved = (state.get("case_context") or {}).get("retrieved_records") or []
    first_s = sources[0].get("source_id", "S1") if sources else ""
    s_ref = [{"source_id": first_s, "quote": ""}] if first_s else []

    return {
        "summary": (
            f"[Development fixture] Judge/Clerk reasoning audit prepared from {len(sources)} "
            f"source page(s) and {len(retrieved)} retrieved record(s). No AI model was called."
        ),
        "issue_coverage": [
            {
                "audit_id": "J-IC1",
                "item": state.get("focus") or "Primary legal issue",
                "finding": "[Development fixture] Issue identified for coverage audit.",
                "status": "partially_covered",
                "severity": "low",
                "opposing_considered": True,
                "source_refs": s_ref,
            }
        ],
        "reasoning_consistency": [],
        "source_support_audit": [
            {
                "audit_id": "J-SS1",
                "item": "Record support check",
                "finding": "[Development fixture] Configure an AI provider for substantive support audit.",
                "status": "partially_covered",
                "severity": "low",
                "opposing_considered": None,
                "source_refs": s_ref,
            }
        ],
        "citation_integrity": [],
        "opposing_consideration_audit": [
            {
                "audit_id": "J-OC1",
                "item": "Contrary arguments and authorities",
                "finding": "[Development fixture] Configure an AI provider to audit opposing consideration.",
                "status": "partially_covered",
                "severity": "low",
                "opposing_considered": False,
                "source_refs": s_ref,
            }
        ],
        "unresolved_questions": [
            {
                "audit_id": "J-UQ1",
                "item": "Human legal verification",
                "finding": "[Development fixture] Configure an AI provider for live audit findings.",
                "status": "unresolved",
                "severity": "medium",
                "opposing_considered": None,
                "source_refs": s_ref,
            }
        ],
        "overall_assessment": (
            "[Development fixture] Reasoning-audit interface exercised; configure AI_PROVIDER for live audit."
        ),
        "limitations": [
            "Development fixture only — not AI-generated legal analysis.",
            "Reasoning-audit assistant only — not a judicial decision and not legal advice.",
        ],
    }


def make_judge_analyst_node(ctx: WorkflowContext):
    async def judge_analyst(state: CaseAnalysisState) -> dict:
        await ctx.report_step(
            "judge_analyst",
            50,
            "Auditing issue coverage, reasoning consistency, source support, and citations",
        )

        sources = state.get("sources") or []
        case_ctx = state.get("case_context") or {}
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
            raw = _mock_judge_draft(state)
            draft = JudgeDraft.model_validate(raw)
            return {
                "draft": draft.model_dump(mode="json"),
                "llm_calls": llm_calls + 1,
                "current_step": "judge_analyst",
                "progress": 70,
            }

        prompt = build_judge_prompt(
            case_context=case_ctx,
            sources=sources,
            focus=state.get("focus"),
            revision_feedback=state.get("revision_feedback") or None,
        )

        try:
            resp = await ctx.provider.generate_structured(
                StructuredRequest(
                    system_prompt=JUDGE_CLERK_SYSTEM_PROMPT,
                    user_prompt=prompt,
                    output_schema=JudgeDraft,
                    max_output_tokens=min(ctx.settings.ai_max_output_tokens, 3200),
                    temperature=0.1,
                    timeout_s=ctx.settings.ai_timeout_s,
                )
            )
        except ProviderError as exc:
            logger.warning("Judge analyst provider error: %s", exc.code)
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
            "current_step": "judge_analyst",
            "progress": 70,
        }

    return judge_analyst
