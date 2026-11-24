"""Evidence Analyst node (stage B of Case Intelligence).

Receives the validated extraction, a compact source index, and the case
context. Produces legal issues (as questions), evidence questions, ambiguities,
and clearly-labelled inferences. The full document text is not resent.
"""

from __future__ import annotations

import logging

from app.agents.context import WorkflowContext
from app.agents.schemas import EvidenceAnalysisDraft
from app.agents.state import CaseAnalysisState
from app.ai.base import ProviderError, StructuredRequest, estimate_tokens
from app.ai.prompts.case_analysis import (
    EVIDENCE_ANALYST_SYSTEM_PROMPT,
    build_evidence_analyst_prompt,
)

logger = logging.getLogger("nyayasaar.agents.evidence_analyst")


def _mock_fixture(state: CaseAnalysisState) -> dict:
    sources = state.get("sources") or []
    first = sources[0] if sources else None
    refs = (
        [{"source_id": first["source_id"], "quote": str(first.get("text", ""))[:140]}]
        if first
        else []
    )
    short_pages = int((state.get("source_stats") or {}).get("short_pages", 0))

    legal_issues: list[dict] = []
    evidence_questions: list[dict] = []
    ambiguities: list[dict] = []
    inferences: list[dict] = []

    if first:
        legal_issues.append(
            {
                "question": (
                    "What legal issue does the supplied document raise, and which "
                    "facts are material to it?"
                ),
                "why_it_matters": (
                    "This development fixture cannot identify a substantive legal "
                    "issue; a configured model and professional review are required."
                ),
                "issue_type": "other",
                "source_refs": refs,
                "confidence": "low",
            }
        )
        evidence_questions.append(
            {
                "question": (
                    "Which additional documents or records would confirm the "
                    "material facts in this case?"
                ),
                "why_it_matters": (
                    "The fixture only sees the supplied page excerpts and cannot "
                    "know what other evidence exists."
                ),
                "evidence_needed": (
                    "Relevant pleadings, agreements, notices, orders, or "
                    "correspondence identified by the responsible lawyer."
                ),
                "source_refs": refs,
            }
        )
        ambiguities.append(
            {
                "statement": "The fixture cannot assess ambiguity in the document.",
                "reason": (
                    "No AI model was called. Any wording or date interpretation "
                    "requires human review."
                ),
                "severity": "medium",
                "source_refs": refs,
            }
        )
        inferences.append(
            {
                "claim": (
                    "This development fixture demonstrates the Evidence Analyst "
                    "interface; it is not legal analysis."
                ),
                "source_refs": refs,
                "confidence": "low",
            }
        )

    if short_pages:
        ambiguities.append(
            {
                "statement": (
                    f"{short_pages} supplied page(s) contain very little text."
                ),
                "reason": (
                    "Short pages may be scans or partially extracted; the analysis "
                    "may not reflect the full document."
                ),
                "severity": "high",
                "source_refs": [],
            }
        )

    return {
        "legal_issues": legal_issues,
        "evidence_questions": evidence_questions,
        "ambiguities": ambiguities,
        "inferences": inferences,
        "unverified_hypotheses": [
            "No AI model was called. Configure AI_PROVIDER, AI_MODEL, and "
            "AI_API_KEY for substantive issue analysis."
        ],
        "missing_information": [
            "A configured AI provider is required to identify potential legal issues."
        ],
        "limitations": [
            "Development fixture only — not AI-generated legal analysis.",
            "Legal issues are questions for professional review, not conclusions.",
        ],
    }


def make_evidence_analyst_node(ctx: WorkflowContext):
    async def evidence_analyst(state: CaseAnalysisState) -> dict:
        await ctx.report_step(
            "evidence_analyst", 54, "Identifying issues, evidence questions, and ambiguity"
        )

        budget_code = ctx.budget_exceeded_code(state)
        if budget_code:
            return ctx.budget_exceeded_state(budget_code)

        extraction = state.get("extraction_draft") or state.get("draft")
        if not extraction:
            return {
                "status": "failed",
                "current_step": "invalid_model_output",
                "progress": 100,
                "outcome": "invalid_model_output",
                "errors": [
                    {
                        "code": "invalid_model_output",
                        "message": "The case extraction was missing before issue analysis.",
                    }
                ],
            }

        calls = int(state.get("llm_calls", 0))
        usage = state.get("token_usage") or {"input": 0, "output": 0, "total": 0}

        prompt = build_evidence_analyst_prompt(
            case_context=state.get("case_context") or {},
            extraction=extraction,
            sources=state.get("sources") or [],
            focus=(state.get("case_context") or {}).get("focus"),
            verification_feedback=state.get("verification_feedback") or [],
            output_schema=EvidenceAnalysisDraft,
        )

        request = StructuredRequest(
            system_prompt=EVIDENCE_ANALYST_SYSTEM_PROMPT,
            user_prompt=prompt,
            output_schema=EvidenceAnalysisDraft,
            temperature=ctx.settings.ai_temperature,
            max_output_tokens=ctx.settings.ai_max_output_tokens,
            timeout_s=ctx.settings.ai_timeout_s,
            mock_fixture=_mock_fixture(state) if ctx.provider.is_mock else None,
            metadata={"stage": "evidence_analyst"},
        )

        try:
            result = await ctx.provider.generate_structured(request)
        except ProviderError as exc:
            logger.warning(
                "Evidence analyst provider error code=%s provider=%s model=%s",
                exc.code,
                ctx.provider.name,
                ctx.provider.model,
            )
            return {
                "status": "failed",
                "current_step": "provider_error",
                "progress": 100,
                "outcome": exc.code,
                "errors": [{"code": exc.code, "message": exc.message}],
            }
        except Exception as exc:  # pragma: no cover - defensive
            logger.error(
                "Evidence analyst unexpected error type=%s", type(exc).__name__
            )
            return {
                "status": "failed",
                "current_step": "internal_error",
                "progress": 100,
                "outcome": "internal_error",
                "errors": [
                    {
                        "code": "internal_error",
                        "message": "The issue-analysis stage failed unexpectedly.",
                    }
                ],
            }

        draft = result.output
        if not isinstance(draft, EvidenceAnalysisDraft):
            return {
                "status": "failed",
                "current_step": "invalid_model_output",
                "progress": 100,
                "outcome": "invalid_model_output",
                "errors": [
                    {
                        "code": "invalid_model_output",
                        "message": "The model returned an unexpected issue-analysis type.",
                    }
                ],
            }

        input_tokens = result.input_tokens
        output_tokens = result.output_tokens
        if input_tokens is None:
            input_tokens = estimate_tokens(prompt)
        if output_tokens is None:
            output_tokens = estimate_tokens(draft.model_dump_json())

        new_usage = {
            "input": int(usage.get("input", 0)) + int(input_tokens),
            "output": int(usage.get("output", 0)) + int(output_tokens),
        }
        new_usage["total"] = new_usage["input"] + new_usage["output"]

        exhausted = new_usage["total"] >= ctx.max_total_tokens
        notes = list(state.get("notes") or [])
        if exhausted:
            notes.append(
                "The workflow reached its token budget; no further model calls "
                "will be made."
            )

        return {
            "evidence_draft": draft.model_dump(),
            "status": "running",
            "current_step": "chronology_builder",
            "progress": 66,
            "outcome": None,
            "llm_calls": calls + 1,
            "token_usage": new_usage,
            "token_budget_exhausted": exhausted,
            "notes": notes,
            "needs_revision": False,
            "revision_target": None,
        }

    return evidence_analyst
