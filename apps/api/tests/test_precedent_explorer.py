"""Deterministic tests for Stage 9 — Precedent Explorer & Conflict Detector."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.agents.context import WorkflowContext
from app.agents.graph_precedent import run_precedent_graph
from app.agents.nodes.precedent_verifier import verify_precedent_draft
from app.agents.schemas_precedent import PrecedentResult
from app.ai.base import LLMProvider, LLMResult, RawCompletion, StructuredRequest
from app.ai.prompts.precedent_v9 import build_precedent_prompt
from app.config import Settings
from app.services.citation_graph import (
    DatabaseCitationGraphProvider,
    _NullCitationGraphProvider,
    get_citation_graph_provider,
)
from app.services.report_precedent import (
    render_precedent_report_html,
    render_precedent_report_markdown,
)


class _FakeProvider(LLMProvider):
    name = "mock"
    model = "mock-test"
    is_mock = True

    def __init__(self) -> None:
        super().__init__(model="mock-test", max_retries=0, structured_retries=0)

    async def _generate_text(self, request: StructuredRequest) -> RawCompletion:  # type: ignore[override]
        return RawCompletion(text="{}")

    async def generate_structured(self, request: StructuredRequest) -> LLMResult:
        output = request.output_schema.model_validate(request.mock_fixture)
        return LLMResult(
            output=output,
            provider="mock",
            model="mock-test",
            is_mock=True,
            input_tokens=50,
            output_tokens=50,
            latency_ms=1,
            attempts=1,
        )


def _sample_state(*, with_sources: bool = True, with_records: bool = True) -> dict:
    sources = (
        [
            {
                "source_id": "S1",
                "document_id": "doc-1",
                "document_name": "plaint.pdf",
                "page_number": 1,
                "text": "The plaintiff claims acknowledgment of debt dated 2022-03-15 under FX-LIM-001.",
                "truncated": False,
                "short": False,
            }
        ]
        if with_sources
        else []
    )
    records = (
        [
            {
                "id": "rec-1",
                "title": "[Sample Fixture] Limitation & Acknowledgment of Debt",
                "citation": "[SAMPLE FIXTURE — NOT A REAL CITATION] FX-LIM-001",
                "court": "Sample Civil Court (Fixture)",
                "jurisdiction": "India (Sample Fixture)",
                "year": "2022",
                "decision_date": "2022-03-15",
                "summary": "Development fixture illustrating limitation metadata.",
                "source_provider": "development_fixture",
                "is_fixture": True,
            },
            {
                "id": "rec-2",
                "title": "[Sample Fixture] Contract Breach & Mitigation",
                "citation": "[SAMPLE FIXTURE — NOT A REAL CITATION] FX-CON-002",
                "court": "Sample High Court (Fixture)",
                "jurisdiction": "India (Sample Fixture)",
                "year": "2021",
                "decision_date": "2021-08-10",
                "summary": "Development fixture illustrating contract mitigation.",
                "source_provider": "development_fixture",
                "is_fixture": True,
            },
        ]
        if with_records
        else []
    )
    return {
        "workflow_id": "wf-test-9",
        "case_id": "case-test-9",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "case_context": {
            "title": "Test Limitation Dispute",
            "focus": "limitation <script>alert(1)</script>",
            "retrieved_records": records,
        },
        "sources": sources,
        "source_notes": [],
        "source_stats": {
            "documents_requested": 1 if with_sources else 0,
            "documents_analyzed": 1 if with_sources else 0,
            "pages_included": 1 if with_sources else 0,
            "pages_truncated": 0,
            "total_chars": 90 if with_sources else 0,
        },
        "provider_name": "mock",
        "model_name": "mock-test",
        "is_mock": True,
        "draft": None,
        "result": None,
        "status": "running",
        "current_step": "orchestrator",
        "progress": 10,
        "outcome": None,
        "errors": [],
        "notes": [],
        "retry_count": 0,
        "needs_revision": False,
        "revision_target": None,
        "verification_feedback": [],
        "llm_calls": 0,
        "token_usage": {"input": 0, "output": 0, "total": 0},
        "token_budget_exhausted": False,
    }


def test_precedent_prompt_wraps_untrusted() -> None:
    state = _sample_state()
    prompt = build_precedent_prompt(
        case_context=state["case_context"],
        sources=state["sources"],
        retrieved_records=state["case_context"]["retrieved_records"],
        focus=state["case_context"]["focus"],
    )
    assert "<untrusted_document>" in prompt
    assert "</untrusted_document>" in prompt
    assert "PrecedentSearchDraft" in prompt or "citation_pairs" in prompt
    assert "[FIXTURE — NOT REAL LAW]" in prompt


def test_precedent_verifier_rejects_unknown_markers_and_preserves_fixture_flag() -> None:
    state = _sample_state()
    state["is_mock"] = False
    state["draft"] = {
        "authorities": [
            {
                "citation_text": "FX-LIM-001",
                "title": "Limitation Fixture",
                "court": "Sample Court",
                "jurisdiction": "India",
                "decision_date": "2022-03-15",
                "holding_summary": "Acknowledgment extends limitation.",
                "source_id": "R1",
                "source_provider": "development_fixture",
                "is_fixture": True,
            },
            {
                "citation_text": "Invented 2099 SCC 999",
                "title": "Invented Case",
                "court": "Unknown",
                "jurisdiction": "Unknown",
                "decision_date": "2099",
                "holding_summary": "Fabricated.",
                "source_id": "R99",
                "source_provider": "unknown",
                "is_fixture": False,
            },
        ],
        "citation_pairs": [],
        "potential_conflicts": [],
        "summary": "Verified test summary.",
        "limitations": [],
    }
    # On first pass with unknown R99 and can_retry=True, verifier triggers revision
    retry_out = verify_precedent_draft(state, max_verifier_retries=1)
    assert retry_out["needs_revision"] is True
    assert retry_out["revision_target"] == "precedent_analyst"

    # When retry budget is exhausted, verifier finalises and records invalid ref
    state["retry_count"] = 1
    final_out = verify_precedent_draft(state, max_verifier_retries=1)
    res = PrecedentResult.model_validate(final_out["result"])
    assert res.authorities[0].is_fixture is True
    assert res.authorities[0].support == "supported"
    assert res.authorities[1].support == "unsupported"
    assert res.verification.invalid_source_refs >= 1


@pytest.mark.asyncio
async def test_precedent_graph_with_mock_provider() -> None:
    async def noop_report(step: str, progress: int, msg: str | None = None) -> None:
        return None

    ctx = WorkflowContext(
        provider=_FakeProvider(),
        settings=Settings(ai_provider="mock", ai_model="fixture"),
        report=noop_report,
        max_llm_calls=5,
        max_total_tokens=80_000,
        max_verifier_retries=1,
    )
    final_state = await run_precedent_graph(ctx, _sample_state())
    assert final_state["status"] == "completed"
    res = PrecedentResult.model_validate(final_state["result"])
    assert res.professional_review_required is True
    assert len(res.authorities) == 2
    assert all(a.is_fixture for a in res.authorities)
    assert len(res.citation_pairs) == 1
    assert len(res.potential_conflicts) == 1


@pytest.mark.asyncio
async def test_precedent_insufficient_sources() -> None:
    async def noop_report(step: str, progress: int, msg: str | None = None) -> None:
        return None

    ctx = WorkflowContext(
        provider=_FakeProvider(),
        settings=Settings(ai_provider="mock", ai_model="fixture"),
        report=noop_report,
        max_llm_calls=5,
        max_total_tokens=80_000,
        max_verifier_retries=1,
    )
    final_state = await run_precedent_graph(ctx, _sample_state(with_sources=False))
    assert final_state["status"] == "completed"
    res = PrecedentResult.model_validate(final_state["result"])
    assert res.insufficient_sources is True
    assert res.authorities == []


def test_precedent_report_escapes_html() -> None:
    state = _sample_state()
    state["draft"] = {
        "authorities": [
            {
                "citation_text": "<script>alert('xss')</script>",
                "title": "Test Case",
                "court": "Court",
                "jurisdiction": "India",
                "decision_date": "2022-01-01",
                "holding_summary": "<b>Holding</b>",
                "source_id": "R1",
                "source_provider": "development_fixture",
                "is_fixture": True,
            }
        ],
        "citation_pairs": [],
        "potential_conflicts": [],
        "summary": "<img src=x onerror=alert(1)>",
        "limitations": [],
    }
    out = verify_precedent_draft(state, max_verifier_retries=0)
    res = PrecedentResult.model_validate(out["result"])
    case = SimpleNamespace(title="Case <script>bad()</script>")
    run = SimpleNamespace(id="wf-12345678")

    html_doc = render_precedent_report_html(case, run, res)
    assert "<script>alert('xss')</script>" not in html_doc
    assert "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;" in html_doc
    assert "<img src=x onerror=alert(1)>" not in html_doc

    md_doc = render_precedent_report_markdown(case, run, res)
    assert "Precedent Explorer Report" in md_doc
    assert "FIXTURE — NOT REAL LAW" in md_doc


@pytest.mark.asyncio
async def test_citation_graph_fallback_when_neo4j_absent() -> None:
    settings_no_neo4j = SimpleNamespace(neo4j_uri="", neo4j_user="neo4j", neo4j_password="")
    null_provider = get_citation_graph_provider(settings_no_neo4j, session_factory=None)
    assert isinstance(null_provider, _NullCitationGraphProvider)
    assert await null_provider.get_outgoing_citations("rec-1") == []
    assert await null_provider.get_incoming_citations("rec-1") == []
    assert await null_provider.store_citations([]) == 0

    db_provider = get_citation_graph_provider(settings_no_neo4j, session_factory=object())
    assert isinstance(db_provider, DatabaseCitationGraphProvider)
