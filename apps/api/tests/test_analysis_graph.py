"""LangGraph workflow tests using a scripted provider (no network)."""

from __future__ import annotations

import json

import pytest

from app.agents.context import WorkflowContext
from app.agents.graph import run_case_analysis_graph
from app.agents.state import CaseAnalysisState
from app.ai.base import LLMProvider, ProviderError, RawCompletion
from app.config import Settings


class ScriptedProvider(LLMProvider):
    name = "scripted"
    is_mock = False

    def __init__(self, script):
        super().__init__(model="scripted-1", max_retries=0, structured_retries=0)
        self.script = list(script)
        self.calls = 0

    async def _generate_text(self, request):
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return RawCompletion(text=json.dumps(item))


def make_context(provider, *, max_retries=1):
    async def report(step, progress, message=None):
        return None

    return WorkflowContext(
        provider=provider,
        settings=Settings(ai_provider="mock", ai_model="fixture"),
        report=report,
        max_llm_calls=3,
        max_total_tokens=80_000,
        max_verifier_retries=max_retries,
    )


def make_state(sources, notes=None):
    return CaseAnalysisState(
        workflow_id="wf-test",
        case_id="case-test",
        case_context={"title": "Test case", "issues": ["Whether the contract is valid"]},
        sources=sources,
        source_notes=notes or [],
        provider_name="scripted",
        model_name="scripted-1",
        is_mock=False,
        draft=None,
        result=None,
        status="running",
        current_step="orchestrator",
        progress=0,
        outcome=None,
        errors=[],
        notes=[],
        retry_count=0,
        needs_revision=False,
        verification_feedback=[],
        llm_calls=0,
        token_usage={"input": 0, "output": 0, "total": 0},
        token_budget_exhausted=False,
    )


SOURCE = {
    "source_id": "S1",
    "document_id": "doc-abc",
    "document_name": "agreement.pdf",
    "page_number": 2,
    "text": "The agreement was signed on 1 May 2024 by both parties.",
    "truncated": False,
}


def draft(claim, quote, summary="The agreement was signed by both parties."):
    return {
        "summary": summary,
        "parties": ["Party A", "Party B"],
        "facts": [
            {
                "claim": claim,
                "source_refs": [{"source_id": "S1", "quote": quote}],
                "confidence": "high",
            }
        ],
        "legal_issues": [],
        "timeline": [],
        "inferences": [],
        "unverified_hypotheses": [],
        "missing_information": [],
        "limitations": [],
    }


@pytest.mark.asyncio
async def test_graph_completes_and_preserves_source_references():
    provider = ScriptedProvider(
        [draft("The agreement was signed on 1 May 2024.", "signed on 1 May 2024")]
    )
    state = await run_case_analysis_graph(
        make_context(provider), make_state([SOURCE])
    )

    assert state["status"] == "completed"
    assert state["outcome"] == "completed"
    assert provider.calls == 1
    result = state["result"]
    assert result["is_mock"] is False
    assert result["facts"][0]["support"] == "supported"
    assert result["facts"][0]["sources"][0]["document_id"] == "doc-abc"
    assert result["facts"][0]["sources"][0]["page_number"] == 2
    assert result["source_manifest"][0]["source_id"] == "S1"
    assert result["verification"]["supported"] == 1


@pytest.mark.asyncio
async def test_graph_returns_insufficient_sources_without_calling_model():
    provider = ScriptedProvider([])
    state = await run_case_analysis_graph(
        make_context(provider),
        make_state([], notes=["No documents are attached to this case."]),
    )

    assert state["status"] == "completed"
    assert state["outcome"] == "insufficient_sources"
    assert provider.calls == 0
    assert state["result"]["insufficient_sources"] is True


@pytest.mark.asyncio
async def test_graph_surfaces_provider_errors_without_leaking_details():
    provider = ScriptedProvider(
        [ProviderError("The AI provider rejected the API key.", code="provider_auth_error")]
    )
    state = await run_case_analysis_graph(
        make_context(provider), make_state([SOURCE])
    )

    assert state["status"] == "failed"
    assert state["outcome"] == "provider_auth_error"
    assert state["errors"][0]["code"] == "provider_auth_error"
    assert "API key" in state["errors"][0]["message"]


@pytest.mark.asyncio
async def test_graph_retries_once_when_claims_are_unsupported():
    first = draft("The agreement was signed in June 2024.", "signed in June 2024")
    second = draft("The agreement was signed on 1 May 2024.", "signed on 1 May 2024")
    provider = ScriptedProvider([first, second])

    state = await run_case_analysis_graph(
        make_context(provider, max_retries=1), make_state([SOURCE])
    )

    assert provider.calls == 2
    assert state["status"] == "completed"
    result = state["result"]
    assert result["verification"]["retried"] is True
    assert result["facts"][0]["support"] == "supported"


@pytest.mark.asyncio
async def test_graph_stops_after_verifier_retry_budget():
    first = draft("The agreement was signed in June 2024.", "signed in June 2024")
    second = draft("The agreement was signed in July 2024.", "signed in July 2024")
    provider = ScriptedProvider([first, second])

    state = await run_case_analysis_graph(
        make_context(provider, max_retries=1), make_state([SOURCE])
    )

    assert provider.calls == 2
    assert state["status"] == "completed"
    # The second draft is still unsupported but the retry budget is exhausted,
    # so the honest result is returned rather than looping.
    assert state["result"]["facts"][0]["support"] == "partially_supported"


@pytest.mark.asyncio
async def test_graph_enforces_llm_call_budget():
    provider = ScriptedProvider([draft("A claim.", "The agreement was signed")])
    ctx = make_context(provider)
    ctx.max_llm_calls = 0

    state = await run_case_analysis_graph(ctx, make_state([SOURCE]))

    assert state["status"] == "failed"
    assert state["outcome"] == "execution_budget_exceeded"
    assert provider.calls == 0
