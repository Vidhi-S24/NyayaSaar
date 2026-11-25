"""Contradiction & Gap Hunter analyst node (Stage 8).

Calls the provider-agnostic LLM interface to compare passages across selected
case documents, extract timeline events, and flag contradictions, possible
inconsistencies, evidence gaps, and unsupported claims.
"""

from __future__ import annotations

import logging

from app.agents.context import WorkflowContext
from app.agents.schemas_contradiction import ContradictionAnalysisDraft
from app.agents.state import CaseAnalysisState
from app.ai.base import ProviderError, StructuredRequest, estimate_tokens
from app.ai.prompts.contradiction import (
    CONTRADICTION_SYSTEM_PROMPT,
    build_contradiction_prompt,
)

logger = logging.getLogger("nyayasaar.agents.contradiction_analyst")


def _mock_fixture(state: CaseAnalysisState) -> dict:
    """Deterministic, clearly-labelled fixture using real supplied sources."""
    sources = state.get("sources") or []
    findings: list[dict] = []
    timeline: list[dict] = []

    if len(sources) >= 2:
        s1, s2 = sources[0], sources[1]
        q1 = " ".join(str(s1.get("text", "")).split())[:110]
        q2 = " ".join(str(s2.get("text", "")).split())[:110]
        findings.append(
            {
                "finding_id": "F1",
                "category": "possible_inconsistency",
                "dimension": "statement",
                "severity": "medium",
                "title": "[Development fixture] Cross-document passage comparison",
                "observed_evidence_summary": (
                    f"{s1.get('document_name')} (p.{s1.get('page_number')}) and "
                    f"{s2.get('document_name')} (p.{s2.get('page_number')}) contain "
                    "distinct factual statements."
                ),
                "model_interpretation": (
                    "[Development fixture] No AI model was called. Configure an AI "
                    "provider to evaluate whether these passages conflict."
                ),
                "side_a_label": str(s1.get("document_name", "Source A")),
                "side_a_refs": [{"source_id": s1["source_id"], "quote": q1}],
                "side_b_label": str(s2.get("document_name", "Source B")),
                "side_b_refs": [{"source_id": s2["source_id"], "quote": q2}],
                "issue_tag": "Cross-document comparison",
                "date_text": None,
            }
        )

    if sources:
        s0 = sources[0]
        q0 = " ".join(str(s0.get("text", "")).split())[:110]
        findings.append(
            {
                "finding_id": f"F{len(findings) + 1}",
                "category": "evidence_gap",
                "dimension": "missing_document",
                "severity": "low",
                "title": "[Development fixture] Supporting-record check",
                "observed_evidence_summary": (
                    f"Passage observed in {s0.get('document_name')} "
                    f"(p.{s0.get('page_number')})."
                ),
                "model_interpretation": (
                    "[Development fixture] Placeholder gap item demonstrating the "
                    "evidence-gap category when no AI key is configured."
                ),
                "side_a_label": str(s0.get("document_name", "Source A")),
                "side_a_refs": [{"source_id": s0["source_id"], "quote": q0}],
                "side_b_label": None,
                "side_b_refs": [],
                "issue_tag": "Evidentiary support",
                "date_text": None,
            }
        )
        timeline.append(
            {
                "date_text": "Undated in fixture",
                "event": f"[Development fixture] Excerpt from {s0.get('document_name')}",
                "significance": "evidential",
                "source_refs": [{"source_id": s0["source_id"], "quote": q0}],
            }
        )

    return {
        "summary": (
            "[Development fixture] Prepared from "
            f"{len(sources)} source page(s). No AI model was called; configure "
            "AI_PROVIDER, AI_MODEL, and AI_API_KEY for substantive contradiction "
            "and gap analysis."
        ),
        "findings": findings,
        "timeline": timeline,
        "missing_information": [
            "A configured AI provider is required for substantive cross-document comparison."
        ],
        "limitations": [
            "Development fixture only — not AI-generated legal analysis.",
            "Observed passages require independent professional review.",
        ],
    }


def make_contradiction_analyst_node(ctx: WorkflowContext):
    async def contradiction_analyst(state: CaseAnalysisState) -> dict:
        await ctx.report_step(
            "contradiction_analyst",
            45,
            "Comparing statements, dates, and evidence gaps across documents",
        )

        budget_code = ctx.budget_exceeded_code(state)
        if budget_code:
            return ctx.budget_exceeded_state(budget_code)

        calls = int(state.get("llm_calls", 0))
        usage = state.get("token_usage") or {"input": 0, "output": 0, "total": 0}
        case_context = state.get("case_context") or {}

        prompt = build_contradiction_prompt(
            case_context=case_context,
            sources=state.get("sources") or [],
            retrieved_pairs=case_context.get("retrieved_pairs") or None,
            focus=case_context.get("focus"),
            verification_feedback=state.get("verification_feedback") or [],
        )

        request = StructuredRequest(
            system_prompt=CONTRADICTION_SYSTEM_PROMPT,
            user_prompt=prompt,
            output_schema=ContradictionAnalysisDraft,
            temperature=ctx.settings.ai_temperature,
            max_output_tokens=ctx.settings.ai_max_output_tokens,
            timeout_s=ctx.settings.ai_timeout_s,
            mock_fixture=_mock_fixture(state) if ctx.provider.is_mock else None,
            metadata={"stage": "contradiction_analyst"},
        )

        try:
            result = await ctx.provider.generate_structured(request)
        except ProviderError as exc:
            logger.warning("Contradiction analyst provider error code=%s", exc.code)
            return {
                "status": "failed",
                "current_step": "provider_error",
                "progress": 100,
                "outcome": exc.code,
                "errors": [{"code": exc.code, "message": exc.message}],
            }
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Contradiction analyst unexpected error type=%s", type(exc).__name__)
            return {
                "status": "failed",
                "current_step": "internal_error",
                "progress": 100,
                "outcome": "internal_error",
                "errors": [
                    {
                        "code": "internal_error",
                        "message": "The contradiction analysis failed unexpectedly.",
                    }
                ],
            }

        draft = result.output
        if not isinstance(draft, ContradictionAnalysisDraft):
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
            "current_step": "contradiction_verifier",
            "progress": 75,
            "outcome": None,
            "llm_calls": calls + 1,
            "token_usage": new_usage,
            "token_budget_exhausted": exhausted,
            "notes": notes,
            "needs_revision": False,
            "revision_target": None,
        }

    return contradiction_analyst
