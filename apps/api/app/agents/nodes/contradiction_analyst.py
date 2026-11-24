"""Contradiction & Gap Hunter analyst node (Stage 6).

Analyses uploaded documents for contradictions, evidentiary gaps, and
unsupported assertions. Never fabricates sources or authorities. Produces
a clearly-labelled fixture when no AI provider is configured.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.agents.context import WorkflowContext
from app.agents.schemas_extended import (
    CONTRADICTION_PROMPT_VERSION,
    CONTRADICTION_RESULT_SCHEMA_VERSION,
    CONTRADICTION_WORKFLOW_VERSION,
    ContradictionDraft,
    ContradictionItem,
    ContradictionResult,
    GapItem,
    SourceRef,
    TimelineConflictItem,
    UnsupportedAssertionItem,
)
from app.agents.state import CaseAnalysisState
from app.ai.base import ProviderError, StructuredRequest, estimate_tokens
from app.ai.prompts.contradiction import (
    CONTRADICTION_ANALYST_SYSTEM_PROMPT,
    build_contradiction_prompt,
)

logger = logging.getLogger("nyayasaar.agents.contradiction_analyst")


def _mock_fixture(state: CaseAnalysisState) -> dict:
    """Deterministic fixture — clearly labelled, no AI was called."""
    sources = state.get("sources") or []
    contradictions = []
    gaps = []
    unsupported = []
    timeline_conflicts = []

    source_ids = [s.get("source_id", f"S{i+1}") for i, s in enumerate(sources)]

    if len(sources) >= 2:
        s0 = sources[0]
        s1 = sources[1]
        contradictions.append(
            {
                "description": (
                    "[Development fixture] Demonstrating the contradiction interface. "
                    "No real contradiction was found — configure an AI provider for "
                    "substantive analysis."
                ),
                "document_a_ref": {
                    "source_id": s0.get("source_id", "S1"),
                    "quote": str(s0.get("text", ""))[:80],
                },
                "document_b_ref": {
                    "source_id": s1.get("source_id", "S2"),
                    "quote": str(s1.get("text", ""))[:80],
                },
                "conflict_type": "factual",
                "significance": "low",
            }
        )
        timeline_conflicts.append(
            {
                "description": "[Development fixture] Demonstrating the timeline conflict interface.",
                "date_a": "",
                "date_b": "",
                "source_a_ref": {"source_id": s0.get("source_id", "S1"), "quote": ""},
                "source_b_ref": {"source_id": s1.get("source_id", "S2"), "quote": ""},
            }
        )

    if sources:
        gaps.append(
            {
                "description": (
                    "[Development fixture] Demonstrating the evidence gap interface. "
                    "Configure an AI provider for real gap detection."
                ),
                "missing_evidence_type": "document",
                "affected_claim": "Fixture claim",
                "source_refs": [{"source_id": source_ids[0], "quote": ""}],
            }
        )
        unsupported.append(
            {
                "assertion": "[Development fixture] No real assertion was analysed.",
                "reason": "Fixture mode — no AI model was called.",
                "source_refs": [],
            }
        )

    return {
        "summary": (
            "[Development fixture] Prepared from "
            f"{len(sources)} source page(s). No AI model was called; this is a "
            "deterministic fixture used to exercise the Contradiction & Gap Hunter "
            "workflow and interface."
        ),
        "contradictions": contradictions,
        "gaps": gaps,
        "unsupported_assertions": unsupported,
        "timeline_conflicts": timeline_conflicts,
        "limitations": [
            "Development fixture only — not AI-generated legal analysis.",
            "No real contradiction detection was performed.",
            "Configure AI_PROVIDER, AI_MODEL, and AI_API_KEY for substantive analysis.",
        ],
    }


def _build_result(
    state: CaseAnalysisState,
    draft: ContradictionDraft,
) -> ContradictionResult:
    sources = state.get("sources") or []
    contradictions = []
    for c in draft.contradictions:
        try:
            contradictions.append(ContradictionItem(**c))
        except Exception:
            pass

    gaps = []
    for g in draft.gaps:
        try:
            source_refs = [SourceRef(**r) for r in (g.get("source_refs") or [])]
            gaps.append(GapItem(**{**g, "source_refs": source_refs}))
        except Exception:
            pass

    unsupported = []
    for u in draft.unsupported_assertions:
        try:
            source_refs = [SourceRef(**r) for r in (u.get("source_refs") or [])]
            unsupported.append(UnsupportedAssertionItem(**{**u, "source_refs": source_refs}))
        except Exception:
            pass

    timeline_conflicts = []
    for t in draft.timeline_conflicts:
        try:
            timeline_conflicts.append(TimelineConflictItem(**t))
        except Exception:
            pass

    limitations = list(draft.limitations or [])
    if "Analysis limited to uploaded documents only." not in limitations:
        limitations.append("Analysis limited to uploaded documents only.")
    if "Professional legal review required before any reliance." not in limitations:
        limitations.append("Professional legal review required before any reliance.")

    return ContradictionResult(
        workflow_id=str(state.get("workflow_id", "")),
        case_id=str(state.get("case_id", "")),
        generated_at=datetime.now(timezone.utc),
        provider=str(state.get("provider_name", "none")),
        model=str(state.get("model_name", "none")),
        is_mock=bool(state.get("is_mock", False)),
        workflow_version=CONTRADICTION_WORKFLOW_VERSION,
        result_schema_version=CONTRADICTION_RESULT_SCHEMA_VERSION,
        summary=draft.summary or "No summary produced.",
        contradictions=contradictions,
        gaps=gaps,
        unsupported_assertions=unsupported,
        timeline_conflicts=timeline_conflicts,
        limitations=limitations,
        professional_review_required=True,
        input_metadata={
            "source_count": len(sources),
            "prompt_version": CONTRADICTION_PROMPT_VERSION,
        },
    )


def make_contradiction_analyst_node(ctx: WorkflowContext):
    async def contradiction_analyst(state: CaseAnalysisState) -> dict:
        await ctx.report_step(
            "contradiction_analyst", 40, "Detecting contradictions and evidence gaps"
        )

        budget_code = ctx.budget_exceeded_code(state)
        if budget_code:
            return ctx.budget_exceeded_state(budget_code)

        calls = int(state.get("llm_calls", 0))
        usage = state.get("token_usage") or {"input": 0, "output": 0, "total": 0}

        prompt = build_contradiction_prompt(
            case_context=state.get("case_context") or {},
            sources=state.get("sources") or [],
            focus=(state.get("case_context") or {}).get("focus"),
        )

        request = StructuredRequest(
            system_prompt=CONTRADICTION_ANALYST_SYSTEM_PROMPT,
            user_prompt=prompt,
            output_schema=ContradictionDraft,
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

        draft = result.output
        if not isinstance(draft, ContradictionDraft):
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

        input_tokens = result.input_tokens or estimate_tokens(prompt)
        output_tokens = result.output_tokens or estimate_tokens(draft.model_dump_json())
        new_usage = {
            "input": int(usage.get("input", 0)) + input_tokens,
            "output": int(usage.get("output", 0)) + output_tokens,
        }
        new_usage["total"] = new_usage["input"] + new_usage["output"]

        contradiction_result = _build_result(state, draft)

        return {
            "result": contradiction_result.model_dump(mode="json"),
            "status": "running",
            "current_step": "finalize",
            "progress": 85,
            "outcome": None,
            "llm_calls": calls + 1,
            "token_usage": new_usage,
            "token_budget_exhausted": new_usage["total"] >= ctx.max_total_tokens,
            "notes": list(state.get("notes") or []),
        }

    return contradiction_analyst
