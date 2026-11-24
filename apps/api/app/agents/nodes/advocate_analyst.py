"""Advocate Mode analyst node (Stage 6).

Develops arguments for BOTH sides from uploaded documents only. Never
fabricates authorities. Flags evidentiary gaps. Includes mandatory
research-tool disclaimer in all results.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.agents.context import WorkflowContext
from app.agents.schemas_extended import (
    ADVOCATE_PROMPT_VERSION,
    ADVOCATE_RESULT_SCHEMA_VERSION,
    ADVOCATE_WORKFLOW_VERSION,
    AdvocateDraft,
    AdvocateResult,
    ArgumentItem,
    GapItem,
    SourceRef,
)
from app.agents.state import CaseAnalysisState
from app.ai.base import ProviderError, StructuredRequest, estimate_tokens
from app.ai.prompts.advocate import (
    ADVOCATE_ANALYST_SYSTEM_PROMPT,
    build_advocate_prompt,
)

logger = logging.getLogger("nyayasaar.agents.advocate_analyst")


def _mock_fixture(state: CaseAnalysisState) -> dict:
    """Deterministic fixture — clearly labelled, no AI was called."""
    sources = state.get("sources") or []
    source_ids = [s.get("source_id", f"S{i+1}") for i, s in enumerate(sources)]
    first_ref = [{"source_id": source_ids[0], "quote": ""}] if source_ids else []

    return {
        "summary": (
            "[Development fixture] Prepared from "
            f"{len(sources)} source page(s). No AI model was called; this is a "
            "deterministic fixture used to exercise the Advocate Mode workflow "
            "and interface."
        ),
        "claimant_arguments": [
            {
                "claim": "[Development fixture] Claimant argument interface demonstration.",
                "reasoning": "Configure an AI provider for substantive argument analysis.",
                "strength": "low",
                "supporting_sources": first_ref,
                "opposing_sources": [],
                "evidentiary_gap": True,
                "gap_description": "No AI analysis performed — fixture mode active.",
            }
        ],
        "respondent_arguments": [
            {
                "claim": "[Development fixture] Respondent argument interface demonstration.",
                "reasoning": "Configure an AI provider for substantive argument analysis.",
                "strength": "low",
                "supporting_sources": first_ref,
                "opposing_sources": [],
                "evidentiary_gap": True,
                "gap_description": "No AI analysis performed — fixture mode active.",
            }
        ],
        "evidentiary_gaps": [
            {
                "description": "[Development fixture] No real gap analysis was performed.",
                "missing_evidence_type": "document",
                "affected_claim": "All arguments",
                "source_refs": first_ref,
            }
        ],
        "strengths": ["[Development fixture] Configure AI provider for real analysis."],
        "weaknesses": ["[Development fixture] Configure AI provider for real analysis."],
        "limitations": [
            "Development fixture only — not AI-generated legal analysis.",
            "Arguments derived only from uploaded documents; no external authorities consulted.",
            "Research tool only — does not constitute legal advice.",
            "Professional legal review required before any reliance.",
        ],
    }


def _build_result(state: CaseAnalysisState, draft: AdvocateDraft) -> AdvocateResult:
    sources = state.get("sources") or []

    def _parse_args(raw: list[dict]) -> list[ArgumentItem]:
        items = []
        for a in raw:
            try:
                a2 = dict(a)
                a2["supporting_sources"] = [
                    SourceRef(**r) for r in (a2.get("supporting_sources") or [])
                ]
                a2["opposing_sources"] = [
                    SourceRef(**r) for r in (a2.get("opposing_sources") or [])
                ]
                items.append(ArgumentItem(**a2))
            except Exception:
                pass
        return items

    def _parse_gaps(raw: list[dict]) -> list[GapItem]:
        items = []
        for g in raw:
            try:
                g2 = dict(g)
                g2["source_refs"] = [SourceRef(**r) for r in (g2.get("source_refs") or [])]
                items.append(GapItem(**g2))
            except Exception:
                pass
        return items

    limitations = list(draft.limitations or [])
    for required in [
        "Arguments derived only from uploaded documents; no external authorities consulted.",
        "Research tool only — does not constitute legal advice.",
        "Professional legal review required before any reliance.",
    ]:
        if required not in limitations:
            limitations.append(required)

    return AdvocateResult(
        workflow_id=str(state.get("workflow_id", "")),
        case_id=str(state.get("case_id", "")),
        generated_at=datetime.now(timezone.utc),
        provider=str(state.get("provider_name", "none")),
        model=str(state.get("model_name", "none")),
        is_mock=bool(state.get("is_mock", False)),
        workflow_version=ADVOCATE_WORKFLOW_VERSION,
        result_schema_version=ADVOCATE_RESULT_SCHEMA_VERSION,
        summary=draft.summary or "No summary produced.",
        claimant_arguments=_parse_args(draft.claimant_arguments),
        respondent_arguments=_parse_args(draft.respondent_arguments),
        evidentiary_gaps=_parse_gaps(draft.evidentiary_gaps),
        strengths=list(draft.strengths or []),
        weaknesses=list(draft.weaknesses or []),
        limitations=limitations,
        professional_review_required=True,
        input_metadata={
            "source_count": len(sources),
            "prompt_version": ADVOCATE_PROMPT_VERSION,
        },
    )


def make_advocate_analyst_node(ctx: WorkflowContext):
    async def advocate_analyst(state: CaseAnalysisState) -> dict:
        await ctx.report_step(
            "advocate_analyst", 40, "Developing arguments for both sides"
        )

        budget_code = ctx.budget_exceeded_code(state)
        if budget_code:
            return ctx.budget_exceeded_state(budget_code)

        calls = int(state.get("llm_calls", 0))
        usage = state.get("token_usage") or {"input": 0, "output": 0, "total": 0}

        prompt = build_advocate_prompt(
            case_context=state.get("case_context") or {},
            sources=state.get("sources") or [],
            focus=(state.get("case_context") or {}).get("focus"),
        )

        request = StructuredRequest(
            system_prompt=ADVOCATE_ANALYST_SYSTEM_PROMPT,
            user_prompt=prompt,
            output_schema=AdvocateDraft,
            temperature=ctx.settings.ai_temperature,
            max_output_tokens=ctx.settings.ai_max_output_tokens,
            timeout_s=ctx.settings.ai_timeout_s,
            mock_fixture=_mock_fixture(state) if ctx.provider.is_mock else None,
            metadata={"stage": "advocate_analyst"},
        )

        try:
            result = await ctx.provider.generate_structured(request)
        except ProviderError as exc:
            logger.warning("Advocate analyst provider error code=%s", exc.code)
            return {
                "status": "failed",
                "current_step": "provider_error",
                "progress": 100,
                "outcome": exc.code,
                "errors": [{"code": exc.code, "message": exc.message}],
            }

        draft = result.output
        if not isinstance(draft, AdvocateDraft):
            return {
                "status": "failed",
                "current_step": "invalid_model_output",
                "progress": 100,
                "outcome": "invalid_model_output",
                "errors": [{"code": "invalid_model_output", "message": "Unexpected output type."}],
            }

        input_tokens = result.input_tokens or estimate_tokens(prompt)
        output_tokens = result.output_tokens or estimate_tokens(draft.model_dump_json())
        new_usage = {
            "input": int(usage.get("input", 0)) + input_tokens,
            "output": int(usage.get("output", 0)) + output_tokens,
        }
        new_usage["total"] = new_usage["input"] + new_usage["output"]

        advocate_result = _build_result(state, draft)

        return {
            "result": advocate_result.model_dump(mode="json"),
            "status": "running",
            "current_step": "finalize",
            "progress": 85,
            "outcome": None,
            "llm_calls": calls + 1,
            "token_usage": new_usage,
            "token_budget_exhausted": new_usage["total"] >= ctx.max_total_tokens,
            "notes": list(state.get("notes") or []),
        }

    return advocate_analyst
