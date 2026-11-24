"""Judge / Clerk Mode analyst node (Stage 6).

Audits uploaded documents for issue coverage, reasoning consistency, source
support, citation integrity, and unresolved questions. This is an analytical
audit tool — it does NOT simulate judicial decision-making, render legal
rulings, or fabricate citations.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.agents.context import WorkflowContext
from app.agents.schemas_extended import (
    JUDGE_PROMPT_VERSION,
    JUDGE_RESULT_SCHEMA_VERSION,
    JUDGE_WORKFLOW_VERSION,
    AuditItem,
    JudgeDraft,
    JudgeResult,
    SourceRef,
)
from app.agents.state import CaseAnalysisState
from app.ai.base import ProviderError, StructuredRequest, estimate_tokens
from app.ai.prompts.judge import (
    JUDGE_CLERK_SYSTEM_PROMPT,
    build_judge_prompt,
)

logger = logging.getLogger("nyayasaar.agents.judge_analyst")


def _mock_fixture(state: CaseAnalysisState) -> dict:
    """Deterministic fixture — clearly labelled, no AI was called."""
    sources = state.get("sources") or []
    source_ids = [s.get("source_id", f"S{i+1}") for i, s in enumerate(sources)]
    first_ref = [{"source_id": source_ids[0], "quote": ""}] if source_ids else []

    fixture_item = {
        "item": "[Development fixture] Interface demonstration",
        "finding": "Configure an AI provider for substantive audit.",
        "severity": "low",
        "source_refs": first_ref,
    }

    return {
        "summary": (
            "[Development fixture] Prepared from "
            f"{len(sources)} source page(s). No AI model was called; this is a "
            "deterministic fixture used to exercise the Judge/Clerk Mode workflow "
            "and interface."
        ),
        "issue_coverage": [fixture_item],
        "reasoning_consistency": [],
        "source_support_audit": [fixture_item],
        "citation_integrity": [],
        "unresolved_questions": [fixture_item],
        "overall_assessment": (
            "[Development fixture] No real audit was performed — configure an AI provider."
        ),
        "limitations": [
            "Development fixture only — not AI-generated legal analysis.",
            "Audit limited to uploaded documents only; no external legal corpus consulted.",
            "This is an analytical tool — not a judicial decision and not legal advice.",
            "Professional legal review required before any reliance.",
        ],
    }


def _parse_audit_items(raw: list[dict]) -> list[AuditItem]:
    items = []
    for a in raw:
        try:
            a2 = dict(a)
            a2["source_refs"] = [SourceRef(**r) for r in (a2.get("source_refs") or [])]
            items.append(AuditItem(**a2))
        except Exception:
            pass
    return items


def _build_result(state: CaseAnalysisState, draft: JudgeDraft) -> JudgeResult:
    sources = state.get("sources") or []
    limitations = list(draft.limitations or [])
    for required in [
        "Audit limited to uploaded documents only; no external legal corpus consulted.",
        "This is an analytical tool — not a judicial decision and not legal advice.",
        "Professional legal review required before any reliance.",
    ]:
        if required not in limitations:
            limitations.append(required)

    return JudgeResult(
        workflow_id=str(state.get("workflow_id", "")),
        case_id=str(state.get("case_id", "")),
        generated_at=datetime.now(timezone.utc),
        provider=str(state.get("provider_name", "none")),
        model=str(state.get("model_name", "none")),
        is_mock=bool(state.get("is_mock", False)),
        workflow_version=JUDGE_WORKFLOW_VERSION,
        result_schema_version=JUDGE_RESULT_SCHEMA_VERSION,
        summary=draft.summary or "No summary produced.",
        issue_coverage=_parse_audit_items(draft.issue_coverage),
        reasoning_consistency=_parse_audit_items(draft.reasoning_consistency),
        source_support_audit=_parse_audit_items(draft.source_support_audit),
        citation_integrity=_parse_audit_items(draft.citation_integrity),
        unresolved_questions=_parse_audit_items(draft.unresolved_questions),
        overall_assessment=draft.overall_assessment or "",
        limitations=limitations,
        professional_review_required=True,
        input_metadata={
            "source_count": len(sources),
            "prompt_version": JUDGE_PROMPT_VERSION,
        },
    )


def make_judge_analyst_node(ctx: WorkflowContext):
    async def judge_analyst(state: CaseAnalysisState) -> dict:
        await ctx.report_step(
            "judge_analyst", 40, "Auditing documents for consistency and coverage"
        )

        budget_code = ctx.budget_exceeded_code(state)
        if budget_code:
            return ctx.budget_exceeded_state(budget_code)

        calls = int(state.get("llm_calls", 0))
        usage = state.get("token_usage") or {"input": 0, "output": 0, "total": 0}

        prompt = build_judge_prompt(
            case_context=state.get("case_context") or {},
            sources=state.get("sources") or [],
            focus=(state.get("case_context") or {}).get("focus"),
        )

        request = StructuredRequest(
            system_prompt=JUDGE_CLERK_SYSTEM_PROMPT,
            user_prompt=prompt,
            output_schema=JudgeDraft,
            temperature=ctx.settings.ai_temperature,
            max_output_tokens=ctx.settings.ai_max_output_tokens,
            timeout_s=ctx.settings.ai_timeout_s,
            mock_fixture=_mock_fixture(state) if ctx.provider.is_mock else None,
            metadata={"stage": "judge_analyst"},
        )

        try:
            result = await ctx.provider.generate_structured(request)
        except ProviderError as exc:
            logger.warning("Judge analyst provider error code=%s", exc.code)
            return {
                "status": "failed",
                "current_step": "provider_error",
                "progress": 100,
                "outcome": exc.code,
                "errors": [{"code": exc.code, "message": exc.message}],
            }

        draft = result.output
        if not isinstance(draft, JudgeDraft):
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

        judge_result = _build_result(state, draft)

        return {
            "result": judge_result.model_dump(mode="json"),
            "status": "running",
            "current_step": "finalize",
            "progress": 85,
            "outcome": None,
            "llm_calls": calls + 1,
            "token_usage": new_usage,
            "token_budget_exhausted": new_usage["total"] >= ctx.max_total_tokens,
            "notes": list(state.get("notes") or []),
        }

    return judge_analyst
