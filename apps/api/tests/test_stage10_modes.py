"""Deterministic tests for Stage 10 — Advocate Mode & Judge/Clerk Mode."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from app.agents.context import WorkflowContext
from app.agents.graph_stage10 import run_advocate_graph, run_judge_graph
from app.agents.nodes.stage10_verifier import verify_advocate_draft, verify_judge_draft
from app.agents.schemas_stage10 import AdvocateDraft, AdvocateResult, JudgeDraft, JudgeResult
from app.agents.state import CaseAnalysisState
from app.ai.base import LLMProvider, LLMResult, ProviderError, RawCompletion, StructuredRequest
from app.config import Settings
from app.services import report_stage10


class _ScriptedProvider(LLMProvider):
    name = "scripted"
    is_mock = False

    def __init__(self, responses: list[object]) -> None:
        super().__init__(model="scripted-v1")
        self._responses = list(responses)
        self.calls = 0

    async def _generate_text(self, request: StructuredRequest) -> RawCompletion:  # type: ignore[override]
        return RawCompletion(text="{}")

    async def generate_structured(self, request: StructuredRequest) -> LLMResult:
        self.calls += 1
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return LLMResult(
            output=item,
            provider=self.name,
            model=self.model,
            is_mock=False,
            input_tokens=100,
            output_tokens=150,
            latency_ms=1,
            attempts=1,
        )


def _base_state(
    *,
    sources: list[dict] | None = None,
    retrieved: list[dict] | None = None,
    preferred_side: str = "both",
    is_mock: bool = False,
) -> CaseAnalysisState:
    return {
        "workflow_id": "wf-stage10-test",
        "case_id": "case-stage10-test",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "case_context": {
            "title": "Krishnamurthy Trust Dispute",
            "preferred_side": preferred_side,
            "retrieved_records": retrieved or [],
        },
        "sources": sources if sources is not None else [
            {
                "source_id": "S1",
                "document_id": "doc-1",
                "document_name": "trust_deed.pdf",
                "page_number": 1,
                "text": "Clause 4 states the trustee shall distribute income equally among beneficiaries.",
            },
            {
                "source_id": "S2",
                "document_id": "doc-2",
                "document_name": "letter.pdf",
                "page_number": 2,
                "text": "On 14 March 2022 the respondent disputed the accounting statement.",
            },
        ],
        "source_notes": [],
        "source_stats": {"documents_analyzed": 2, "pages_analyzed": 2},
        "provider_name": "scripted",
        "model_name": "scripted-v1",
        "is_mock": is_mock,
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
        "revision_needed": False,
        "verifier_retries": 0,
        "llm_calls": 0,
        "max_llm_calls": 4,
        "token_usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
    }


def _ctx(provider: LLMProvider) -> WorkflowContext:
    async def noop_report(step: str, progress: int, message: str | None = None) -> None:
        return None

    return WorkflowContext(
        provider=provider,
        settings=Settings(),
        report=noop_report,
        max_llm_calls=4,
        max_total_tokens=12000,
        max_verifier_retries=1,
    )


def test_advocate_verifier_enforces_speculative_tier_when_ungrounded() -> None:
    state = _base_state(
        retrieved=[
            {
                "id": "rec-1",
                "title": "Trust Precedent",
                "citation": "2020 SCC 12",
                "summary": "Trustees owe fiduciary duty of accounting.",
                "is_fixture": True,
            }
        ]
    )
    state["draft"] = AdvocateDraft(
        selected_issue="Fiduciary accounting",
        summary="Both sides present competing interpretations.",
        relevant_facts=["Trustee must distribute income equally."],
        claimant_arguments=[
            {
                "argument_id": "A-C1",
                "side": "claimant",
                "issue": "Accounting",
                "claim": "Trustee breached Clause 4.",
                "reasoning": "Clause 4 requires equal distribution.",
                "tier": "strong_supported",
                "strength": "high",
                "supporting_sources": [
                    {"source_id": "S1", "quote": "distribute income equally"},
                    {"source_id": "R1", "quote": "fiduciary duty of accounting"},
                ],
                "authority_refs": ["2020 SCC 12"],
                "counterarguments": ["Accounting was delayed due to audit."],
            },
            {
                "argument_id": "A-C2",
                "side": "claimant",
                "issue": "Damages",
                "claim": "Punitive damages apply.",
                "reasoning": "Asserted without record passage.",
                "tier": "strong_supported",
                "strength": "high",
                "supporting_sources": [],
                "authority_refs": ["2099 FAKE 999"],
            },
        ],
        respondent_arguments=[
            {
                "argument_id": "A-R1",
                "side": "respondent",
                "issue": "Accounting",
                "claim": "Accounting statement was timely disputed.",
                "reasoning": "Letter on page 2 records dispute.",
                "tier": "moderate_supported",
                "strength": "medium",
                "supporting_sources": [{"source_id": "S2", "quote": "disputed the accounting"}],
            }
        ],
    ).model_dump(mode="json")

    out = verify_advocate_draft(state)
    res = AdvocateResult.model_validate(out["result"])
    assert res.claimant_arguments[0].support == "supported"
    assert res.claimant_arguments[0].tier == "strong_supported"
    assert len(res.claimant_arguments[0].supporting_sources) == 2
    # Ungrounded argument is downgraded to speculative with evidentiary_gap=True
    assert res.claimant_arguments[1].tier == "speculative"
    assert res.claimant_arguments[1].evidentiary_gap is True
    assert res.claimant_arguments[1].strength == "low"
    assert res.claimant_arguments[1].authority_refs == []
    assert any("unverified authority" in note for note in res.verification.notes)
    assert res.verification.total_claims == 3


def test_advocate_verifier_treats_contrary_only_material_as_unsupported() -> None:
    state = _base_state()
    state["draft"] = AdvocateDraft(
        summary="Test",
        claimant_arguments=[
            {
                "argument_id": "A-C1",
                "side": "claimant",
                "claim": "Asserted claim",
                "reasoning": "Only contrary material was linked.",
                "tier": "moderate_supported",
                "supporting_sources": [],
                "opposing_sources": [
                    {"source_id": "S2", "quote": "disputed the accounting"}
                ],
            }
        ],
    ).model_dump(mode="json")

    out = verify_advocate_draft(state)
    res = AdvocateResult.model_validate(out["result"])
    argument = res.claimant_arguments[0]
    assert argument.support == "unsupported"
    assert argument.tier == "speculative"
    assert argument.evidentiary_gap is True
    assert len(argument.opposing_sources) == 1


def test_advocate_verifier_triggers_revision_on_unknown_marker() -> None:
    state = _base_state()
    state["draft"] = AdvocateDraft(
        summary="Test",
        claimant_arguments=[
            {
                "argument_id": "A-C1",
                "side": "claimant",
                "claim": "Test claim",
                "reasoning": "Test",
                "supporting_sources": [{"source_id": "S99", "quote": "invented"}],
            }
        ],
    ).model_dump(mode="json")

    out = verify_advocate_draft(state, max_verifier_retries=1)
    assert out["revision_needed"] is True
    assert out["revision_target"] == "advocate_analyst"
    assert "S99" in out["revision_feedback"][0]


def test_judge_verifier_verifies_audit_categories_and_revises() -> None:
    state = _base_state()
    state["draft"] = JudgeDraft(
        summary="Audit summary",
        issue_coverage=[
            {
                "audit_id": "J-IC1",
                "item": "Clause 4 distribution",
                "finding": "Covered in trust deed.",
                "status": "covered",
                "severity": "low",
                "opposing_considered": True,
                "source_refs": [{"source_id": "S1", "quote": "distribute income equally"}],
            }
        ],
        opposing_consideration_audit=[
            {
                "audit_id": "J-OC1",
                "item": "Respondent accounting objection",
                "finding": "Dispute raised in S2.",
                "status": "partially_covered",
                "severity": "medium",
                "opposing_considered": True,
                "source_refs": [{"source_id": "S2", "quote": "disputed the accounting"}],
            }
        ],
        overall_assessment="Record requires human verification of accounting.",
    ).model_dump(mode="json")

    out = verify_judge_draft(state)
    res = JudgeResult.model_validate(out["result"])
    assert res.issue_coverage[0].support == "supported"
    assert res.opposing_consideration_audit[0].opposing_considered is True
    assert "not a simulated judicial authority" in res.judicial_audit_disclaimer


@pytest.mark.asyncio
async def test_advocate_and_judge_graphs_handle_insufficient_sources_and_provider_error() -> None:
    empty_state = _base_state(sources=[], is_mock=True)
    provider = _ScriptedProvider([])
    adv_empty = await run_advocate_graph(_ctx(provider), dict(empty_state))
    assert adv_empty["status"] == "completed"
    assert adv_empty["result"]["insufficient_sources"] is True

    judge_empty = await run_judge_graph(_ctx(provider), dict(empty_state))
    assert judge_empty["status"] == "completed"
    assert judge_empty["result"]["insufficient_sources"] is True

    failing_provider = _ScriptedProvider(
        [ProviderError("Upstream 503", code="provider_unavailable")]
    )
    adv_err = await run_advocate_graph(_ctx(failing_provider), _base_state())
    assert adv_err["status"] == "failed"
    assert adv_err["errors"][0]["code"] == "provider_unavailable"


def test_stage10_reports_escape_html() -> None:
    case = SimpleNamespace(id="c1", title="Trust <script>alert(1)</script>")
    run = SimpleNamespace(id="wf1")
    adv_res = AdvocateResult(
        workflow_id="wf1",
        case_id="c1",
        generated_at=datetime.now(timezone.utc),
        provider="mock",
        model="fixture",
        is_mock=True,
        summary="<script>xss()</script> summary",
    )
    html_out = report_stage10.render_advocate_report_html(case, run, adv_res)
    assert "<script>alert(1)</script>" not in html_out
    assert "&lt;script&gt;xss()&lt;/script&gt;" in html_out
    md_out = report_stage10.render_advocate_report_markdown(case, run, adv_res)
    assert "Advocate Mode Argument Report" in md_out

    judge_res = JudgeResult(
        workflow_id="wf1",
        case_id="c1",
        generated_at=datetime.now(timezone.utc),
        provider="mock",
        model="fixture",
        is_mock=True,
        summary="<b>Audit</b>",
    )
    j_html = report_stage10.render_judge_report_html(case, run, judge_res)
    assert "&lt;b&gt;Audit&lt;/b&gt;" in j_html
    j_md = report_stage10.render_judge_report_markdown(case, run, judge_res)
    assert "Judge / Clerk Reasoning Audit Report" in j_md


@pytest.mark.asyncio
async def test_stage10_api_endpoints_and_cross_user_auth(client: AsyncClient) -> None:
    r1 = await client.post(
        "/api/v1/auth/register",
        json={"email": "owner_s10@example.com", "password": "StrongPassword123!", "full_name": "Owner"},
    )
    assert r1.status_code == 201
    h1 = {"Authorization": f"Bearer {r1.json()['data']['access_token']}"}

    r2 = await client.post(
        "/api/v1/auth/register",
        json={"email": "other_s10@example.com", "password": "StrongPassword123!", "full_name": "Other"},
    )
    assert r2.status_code == 201
    h2 = {"Authorization": f"Bearer {r2.json()['data']['access_token']}"}

    c_resp = await client.post(
        "/api/v1/cases",
        headers=h1,
        json={"title": "Stage 10 Case"},
    )
    assert c_resp.status_code == 201
    case_id = c_resp.json()["data"]["id"]

    adv_resp = await client.post(
        f"/api/v1/cases/{case_id}/analysis",
        headers=h1,
        json={"workflow_type": "advocate", "preferred_side": "claimant"},
    )
    assert adv_resp.status_code == 202
    adv_wf_id = adv_resp.json()["data"]["id"]

    judge_resp = await client.post(
        f"/api/v1/cases/{case_id}/analysis",
        headers=h1,
        json={"workflow_type": "judge"},
    )
    assert judge_resp.status_code == 202
    judge_wf_id = judge_resp.json()["data"]["id"]

    # Both workflows must persist a structured result through the normal API.
    for workflow_id in (adv_wf_id, judge_wf_id):
        poll = await client.get(
            f"/api/v1/cases/{case_id}/analysis/{workflow_id}", headers=h1
        )
        assert poll.status_code == 200
        run = poll.json()["data"]
        assert run["status"] == "completed"
        assert run["result"]["insufficient_sources"] is True
        assert run["result"]["is_mock"] is True

    # Cross-user access must return 404
    cross = await client.get(
        f"/api/v1/cases/{case_id}/analysis/{adv_wf_id}",
        headers=h2,
    )
    assert cross.status_code == 404

    cross_j = await client.get(
        f"/api/v1/cases/{case_id}/analysis/{judge_wf_id}/report",
        headers=h2,
    )
    assert cross_j.status_code == 404
