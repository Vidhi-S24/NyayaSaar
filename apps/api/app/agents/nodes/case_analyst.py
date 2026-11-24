"""Case Analyst node (stage A of Case Intelligence).

Calls the provider through the provider-agnostic interface, validates the
structured extraction draft, and records token usage. All prompt construction
happens in ``app.ai.prompts``; all provider details live behind ``LLMProvider``.
"""

from __future__ import annotations

import logging
import re

from app.agents.context import WorkflowContext
from app.agents.schemas import CaseAnalysisDraft
from app.agents.state import CaseAnalysisState
from app.ai.base import ProviderError, StructuredRequest, estimate_tokens
from app.ai.prompts.case_analysis import (
    CASE_ANALYST_SYSTEM_PROMPT,
    build_case_analyst_prompt,
)

logger = logging.getLogger("nyayasaar.agents.case_analyst")

_DATE_RE = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
    r"|\d{1,2}(?:st|nd|rd|th)?\s+[A-Z][a-z]+,?\s+\d{4}"
    r"|[A-Z][a-z]+\s+\d{1,2},?\s+\d{4})\b"
)
_AMOUNT_RE = re.compile(
    r"(?:₹|Rs\.?|INR|USD|\$)\s?[\d,]+(?:\.\d{1,2})?(?:\s?(?:lakh|crore|million|billion))?",
    re.IGNORECASE,
)


def _mock_fixture(state: CaseAnalysisState) -> dict:
    """Deterministic, clearly-labelled fixture with real source references."""
    sources = state.get("sources") or []
    facts: list[dict] = []
    entities: list[dict] = []
    amounts: list[dict] = []
    procedural: list[dict] = []
    timeline: list[dict] = []
    key_dates: list[dict] = []

    for source in sources[:4]:
        text = " ".join(str(source.get("text", "")).split())
        if not text:
            continue
        snippet = text[:200]
        quote = text[:140]
        refs = [{"source_id": source["source_id"], "quote": quote}]

        facts.append(
            {
                "claim": f"The supplied document states: {snippet}",
                "source_refs": refs,
                "confidence": "medium",
            }
        )
        entities.append(
            {
                "name": str(source.get("document_name", "Source document")),
                "entity_type": "other",
                "role": "Source document",
                "source_refs": refs,
                "confidence": "low",
            }
        )

        amount_match = _AMOUNT_RE.search(text)
        if amount_match:
            amounts.append(
                {
                    "description": "Amount mentioned in the supplied document",
                    "amount_text": amount_match.group(0),
                    "source_refs": refs,
                    "confidence": "low",
                }
            )

        date_match = _DATE_RE.search(text)
        if date_match:
            date_text = date_match.group(0)
            timeline.append(
                {
                    "date_text": date_text,
                    "event": f"Dated statement in the supplied document: {snippet[:160]}",
                    "significance": "factual",
                    "source_refs": refs,
                }
            )
            key_dates.append(
                {
                    "date_text": date_text,
                    "label": "Date mentioned in the supplied document",
                    "source_refs": refs,
                }
            )

        lowered = text.lower()
        for stage, keyword in (
            ("Filing", "filed"),
            ("Notice", "notice"),
            ("Hearing", "hearing"),
            ("Order", "order"),
        ):
            if keyword in lowered:
                procedural.append(
                    {
                        "stage": stage,
                        "description": f"The document refers to a {stage.lower()}.",
                        "date_text": date_match.group(0) if date_match else None,
                        "source_refs": refs,
                    }
                )
                break

    return {
        "summary": (
            "[Development fixture] Prepared from "
            f"{len(sources)} source page(s). No AI model was called; this is a "
            "deterministic fixture used to exercise the Case Intelligence "
            "workflow and verification interface."
        ),
        "parties": [],
        "entities": entities,
        "amounts": amounts,
        "facts": facts,
        "procedural_history": procedural,
        "key_dates": key_dates,
        "timeline": timeline,
        "legal_issues": [],
        "inferences": [],
        "unverified_hypotheses": [
            "No AI model was called. Configure AI_PROVIDER, AI_MODEL, and "
            "AI_API_KEY for substantive analysis."
        ],
        "missing_information": [
            "A configured AI provider is required for substantive analysis."
        ],
        "limitations": [
            "Development fixture only — not AI-generated legal analysis.",
            "No external legal authority database was consulted.",
        ],
    }


def make_case_analyst_node(ctx: WorkflowContext):
    async def case_analyst(state: CaseAnalysisState) -> dict:
        await ctx.report_step(
            "case_analyst", 34, "Extracting facts, parties, entities, and dates"
        )

        budget_code = ctx.budget_exceeded_code(state)
        if budget_code:
            return ctx.budget_exceeded_state(budget_code)

        calls = int(state.get("llm_calls", 0))
        usage = state.get("token_usage") or {"input": 0, "output": 0, "total": 0}

        prompt = build_case_analyst_prompt(
            case_context=state.get("case_context") or {},
            sources=state.get("sources") or [],
            focus=(state.get("case_context") or {}).get("focus"),
            verification_feedback=state.get("verification_feedback") or [],
            output_schema=CaseAnalysisDraft,
        )

        request = StructuredRequest(
            system_prompt=CASE_ANALYST_SYSTEM_PROMPT,
            user_prompt=prompt,
            output_schema=CaseAnalysisDraft,
            temperature=ctx.settings.ai_temperature,
            max_output_tokens=ctx.settings.ai_max_output_tokens,
            timeout_s=ctx.settings.ai_timeout_s,
            mock_fixture=_mock_fixture(state) if ctx.provider.is_mock else None,
            metadata={"stage": "case_analyst"},
        )

        try:
            result = await ctx.provider.generate_structured(request)
        except ProviderError as exc:
            logger.warning(
                "Case analyst provider error code=%s provider=%s model=%s",
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
                "Case analyst unexpected error type=%s", type(exc).__name__
            )
            return {
                "status": "failed",
                "current_step": "internal_error",
                "progress": 100,
                "outcome": "internal_error",
                "errors": [
                    {
                        "code": "internal_error",
                        "message": "The analysis workflow failed unexpectedly.",
                    }
                ],
            }

        draft = result.output
        if not isinstance(draft, CaseAnalysisDraft):
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
            "draft": draft.model_dump(),
            "extraction_draft": draft.model_dump(),
            "status": "running",
            "current_step": "evidence_analyst",
            "progress": 52,
            "outcome": None,
            "llm_calls": calls + 1,
            "token_usage": new_usage,
            "token_budget_exhausted": exhausted,
            "notes": notes,
            "needs_revision": False,
            "revision_target": None,
        }

    return case_analyst
