"""Stage 6 Case Intelligence contracts, verifier extensions, and report export."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.agents.nodes.verifier import verify_draft
from app.agents.schemas import (
    CaseAnalysisDraft,
    CaseAnalysisResult,
    DraftAmount,
    DraftEntity,
    DraftLegalIssue,
    DraftParty,
    DraftProceduralEvent,
    DraftSourceRef,
    EvidenceAnalysisDraft,
)
from app.agents.tools.sources import SourceExcerpt
from app.db.models.case import Case
from app.db.models.workflow import WorkflowRun
from app.services.report import (
    render_case_report_html,
    render_case_report_markdown,
    report_filename,
    slugify_filename,
)

SOURCE_TEXT = (
    "The agreement was signed on 1 May 2024 by Acme Trading Pvt Ltd and "
    "Ravi Kumar. The agreed amount was Rs. 5,00,000. Acme filed a notice "
    "of arbitration on 3 June 2024 before the Bombay High Court."
)


def source() -> SourceExcerpt:
    return SourceExcerpt(
        source_id="S1",
        document_id="doc-123",
        document_name="agreement.pdf",
        page_number=3,
        text=SOURCE_TEXT,
    )


def draft() -> CaseAnalysisDraft:
    return CaseAnalysisDraft(
        summary="The documents record an agreement, an amount, and a notice.",
        parties=[
            DraftParty(
                name="Acme Trading Pvt Ltd",
                role="Claimant",
                source_refs=[
                    DraftSourceRef(source_id="S1", quote="Acme Trading Pvt Ltd")
                ],
            ),
            DraftParty(
                name="Ravi Kumar",
                role="Respondent",
                source_refs=[DraftSourceRef(source_id="S1", quote="Ravi Kumar")],
            ),
        ],
        entities=[
            DraftEntity(
                name="Acme Trading Pvt Ltd",
                entity_type="organisation",
                role="Claimant",
                source_refs=[
                    DraftSourceRef(source_id="S1", quote="Acme Trading Pvt Ltd")
                ],
            ),
            DraftEntity(
                name="Invented Person",
                entity_type="person",
                source_refs=[
                    DraftSourceRef(source_id="S9", quote="Invented Person")
                ],
            ),
        ],
        amounts=[
            DraftAmount(
                description="Agreed amount",
                amount_text="Rs. 5,00,000",
                currency="INR",
                source_refs=[DraftSourceRef(source_id="S1", quote="Rs. 5,00,000")],
            )
        ],
        facts=[
            {
                "claim": "The agreement was signed on 1 May 2024.",
                "source_refs": [
                    DraftSourceRef(source_id="S1", quote="signed on 1 May 2024")
                ],
                "confidence": "high",
            },
            {
                "claim": "The agreement was signed in December 2025.",
                "source_refs": [
                    DraftSourceRef(source_id="S1", quote="signed in December 2025")
                ],
                "confidence": "low",
            },
        ],
        procedural_history=[
            DraftProceduralEvent(
                stage="Notice of arbitration",
                description="Acme filed a notice of arbitration.",
                date_text="3 June 2024",
                forum="Bombay High Court",
                source_refs=[
                    DraftSourceRef(
                        source_id="S1", quote="notice of arbitration on 3 June 2024"
                    )
                ],
            )
        ],
        timeline=[
            {
                "date_text": "1 May 2024",
                "event": "Agreement signed.",
                "significance": "factual",
                "source_refs": [
                    DraftSourceRef(source_id="S1", quote="signed on 1 May 2024")
                ],
            }
        ],
    )


def evidence() -> EvidenceAnalysisDraft:
    return EvidenceAnalysisDraft(
        legal_issues=[
            DraftLegalIssue(
                question="Whether the arbitration notice was validly served?",
                why_it_matters="Service affects the tribunal's jurisdiction.",
                issue_type="procedural",
                source_refs=[
                    DraftSourceRef(
                        source_id="S1", quote="notice of arbitration on 3 June 2024"
                    )
                ],
            )
        ],
        evidence_questions=[
            {
                "question": "Is there proof of service of the notice?",
                "why_it_matters": "Service is disputed.",
                "evidence_needed": "Acknowledgment or postal receipt.",
                "source_refs": [
                    DraftSourceRef(source_id="S1", quote="notice of arbitration")
                ],
            }
        ],
        ambiguities=[
            {
                "statement": "The date format is unambiguous.",
                "reason": "The document writes the month in words.",
                "severity": "low",
                "source_refs": [
                    DraftSourceRef(source_id="S1", quote="3 June 2024")
                ],
            }
        ],
    )


def build_result():
    return verify_draft(
        draft(),
        [source()],
        workflow_id="wf-1",
        case_id="case-1",
        provider_name="mock",
        model_name="fixture",
        is_mock=True,
        evidence=evidence(),
        chronology=[
            {
                "date_text": "1 May 2024",
                "event": "Agreement signed.",
                "significance": "factual",
                "date_sort_key": "2024-05-01",
                "date_precision": "day",
                "date_ambiguous": False,
                "source_refs": [
                    {"source_id": "S1", "quote": "signed on 1 May 2024"}
                ],
            }
        ],
        source_stats={"documents_available": 1, "documents_analyzed": 1},
    )


# ---------------------------------------------------------------------------
# Verifier extensions
# ---------------------------------------------------------------------------


def test_verifier_records_entities_amounts_and_spans():
    result = build_result()

    entity = next(item for item in result.entities if item.name == "Acme Trading Pvt Ltd")
    assert entity.support == "supported"
    ref = entity.sources[0]
    assert ref.document_id == "doc-123"
    assert ref.page_number == 3
    assert ref.quote_verified is True
    assert ref.span_start is not None and ref.span_end is not None
    assert SOURCE_TEXT[ref.span_start : ref.span_end].casefold() == "acme trading pvt ltd"

    amount = result.amounts[0]
    assert amount.amount_text == "Rs. 5,00,000"
    assert amount.support == "supported"


def test_verifier_links_parties_to_sources():
    result = build_result()

    assert [party.name for party in result.parties] == [
        "Acme Trading Pvt Ltd",
        "Ravi Kumar",
    ]
    claimant = result.parties[0]
    assert claimant.role == "Claimant"
    assert claimant.support == "supported"
    ref = claimant.sources[0]
    assert ref.document_id == "doc-123"
    assert ref.page_number == 3
    assert ref.quote_verified is True
    assert ref.span_start is not None and ref.span_end is not None
    assert SOURCE_TEXT[ref.span_start : ref.span_end].casefold() == "acme trading pvt ltd"


def test_verifier_rejects_unknown_source_marker():
    result = build_result()
    invented = next(item for item in result.entities if item.name == "Invented Person")
    assert invented.sources == []
    assert invented.support == "unsupported"
    assert result.verification.invalid_source_refs == 1


def test_verifier_distinguishes_supported_and_unsupported_facts():
    result = build_result()
    supported, unsupported = result.facts
    assert supported.support == "supported"
    assert unsupported.support == "partially_supported"
    assert result.verification.supported >= 1
    assert result.verification.partially_supported >= 1


def test_verifier_includes_chronology_and_procedural_dates():
    result = build_result()
    assert result.timeline[0].date_sort_key == "2024-05-01"
    assert result.timeline[0].date_precision == "day"
    assert result.timeline[0].date_ambiguous is False
    assert result.procedural_history[0].date_sort_key == "2024-06-03"
    assert result.procedural_history[0].forum == "Bombay High Court"


def test_verifier_keeps_legal_issues_as_questions_and_separates_ambiguity():
    result = build_result()
    assert result.issue_analysis[0].question.endswith("?")
    assert result.issue_analysis[0].support == "supported"
    assert result.evidence_questions[0].evidence_needed
    assert result.ambiguities[0].severity == "low"
    assert result.professional_review_required is True


def test_verifier_never_claims_external_authority():
    result = build_result()
    joined = " ".join(result.limitations).lower()
    assert "no external legal authority" in joined
    assert result.verification.notes
    assert any("professional review" in item.lower() for item in result.limitations)


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------


def report_models():
    case = Case(id="case-1", owner_id="user-1", title="Acme <script>alert(1)</script>")
    case.case_number = "COMM/2024/1"
    case.court = "Bombay High Court"
    case.jurisdiction = "India"
    run = WorkflowRun(
        id=str(uuid.uuid4()),
        case_id="case-1",
        user_id="user-1",
        workflow_type="case_analysis",
        status="completed",
        progress=100,
        current_step="completed",
        input_payload={},
        steps=[],
        token_usage={},
        attempt_count=1,
    )
    run.created_at = datetime.now(timezone.utc)
    run.updated_at = datetime.now(timezone.utc)
    return case, run


def test_html_report_is_escaped_and_contains_all_sections():
    case, run = report_models()
    html = render_case_report_html(case, run, build_result())

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "Executive summary" in html
    assert "Material facts" in html
    assert "Parties" in html
    assert "Acme Trading Pvt Ltd" in html
    assert "Claimant" in html
    assert "Supported by source" in html
    assert "Chronology" in html
    assert "Potential legal issues" in html
    assert "Questions requiring further evidence" in html
    assert "Ambiguity and uncertainty" in html
    assert "Development fixture" in html
    assert "Professional review required" in html


def test_markdown_report_contains_sections_and_source_pages():
    case, run = report_models()
    markdown = render_case_report_markdown(case, run, build_result())

    assert markdown.startswith("# Case Intelligence Report")
    assert "## Parties" in markdown
    assert "**Acme Trading Pvt Ltd** — Claimant" in markdown
    assert "agreement.pdf p.3" in markdown
    assert "## Chronology" in markdown
    assert "## Potential legal issues" in markdown
    assert "agreement.pdf p.3" in markdown
    assert "Verified" in markdown or "verified" in markdown


def test_legacy_string_parties_are_read_as_unsupported():
    data = build_result().model_dump(mode="json")
    data["parties"] = ["Acme Trading Pvt Ltd", "Ravi Kumar"]

    legacy = CaseAnalysisResult.model_validate(data)

    assert [party.name for party in legacy.parties] == [
        "Acme Trading Pvt Ltd",
        "Ravi Kumar",
    ]
    assert all(party.support == "unsupported" for party in legacy.parties)
    assert all(party.sources == [] for party in legacy.parties)


def test_report_filename_is_safe():
    case, run = report_models()
    filename = report_filename(case, run, "html")
    assert filename.startswith("nyayasaar-case-intelligence-")
    assert filename.endswith(".html")
    assert "<" not in filename
    assert " " not in filename
    assert slugify_filename("A/B: C?") == "a-b-c"


# ---------------------------------------------------------------------------
# API: mock-provider result shape and authenticated report export
# ---------------------------------------------------------------------------


async def register(client, email: str) -> tuple[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "securepass123",
            "full_name": "Intelligence User",
        },
    )
    assert response.status_code == 201, response.text
    token = response.json()["data"]["access_token"]
    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    return token, me.json()["data"]["id"]


async def create_case(client, token: str, title: str = "Intelligence case") -> str:
    response = await client.post(
        "/api/v1/cases",
        json={"title": title},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


async def seed_document(test_app, *, case_id: str, user_id: str) -> str:
    from app.db.models.document import Document, DocumentChunk

    factory = test_app.state.test_session_factory
    doc_id = str(uuid.uuid4())
    text = (
        "The agreement was signed on 1 May 2024 by Acme Trading Pvt Ltd. "
        "The amount payable was Rs. 5,00,000. A notice of arbitration was "
        "filed on 3 June 2024 before the Bombay High Court."
    )
    async with factory() as session:
        session.add(
            Document(
                id=doc_id,
                case_id=case_id,
                owner_id=user_id,
                original_name="agreement.txt",
                storage_key=f"test/{doc_id}",
                content_type="text/plain",
                file_size=len(text),
                processing_status="ready",
                page_count=1,
                extraction_completeness=100,
            )
        )
        session.add(
            DocumentChunk(
                id=str(uuid.uuid4()),
                document_id=doc_id,
                page_number=1,
                extracted_text=text,
                char_count=len(text),
            )
        )
        await session.commit()
    return doc_id


@pytest.mark.asyncio
async def test_result_exposes_stage6_sections_and_versions(client, test_app):
    token, user_id = await register(client, "stage6@test.com")
    case_id = await create_case(client, token)
    await seed_document(test_app, case_id=case_id, user_id=user_id)

    start = await client.post(
        f"/api/v1/cases/{case_id}/analysis", json={}, headers={"Authorization": f"Bearer {token}"}
    )
    assert start.status_code == 202, start.text
    workflow_id = start.json()["data"]["id"]

    poll = await client.get(
        f"/api/v1/cases/{case_id}/analysis/{workflow_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    run = poll.json()["data"]
    assert run["status"] == "completed"
    assert run["workflow_version"] == "6.1.0"
    result = run["result"]

    assert "entities" in result and result["entities"]
    assert "amounts" in result
    assert "procedural_history" in result
    assert "issue_analysis" in result and result["issue_analysis"]
    assert "evidence_questions" in result
    assert "ambiguities" in result
    assert result["timeline"]
    assert result["source_stats"]["documents_analyzed"] == 1
    assert result["facts"][0]["sources"][0]["document_id"]
    # Fixture output must never masquerade as a real model result.
    assert result["is_mock"] is True


@pytest.mark.asyncio
async def test_report_export_requires_auth_and_ownership(client, test_app):
    token, user_id = await register(client, "report-owner@test.com")
    other_token, _ = await register(client, "report-other@test.com")
    case_id = await create_case(client, token)
    await seed_document(test_app, case_id=case_id, user_id=user_id)
    start = await client.post(
        f"/api/v1/cases/{case_id}/analysis", json={}, headers={"Authorization": f"Bearer {token}"}
    )
    workflow_id = start.json()["data"]["id"]

    anonymous = await client.get(
        f"/api/v1/cases/{case_id}/analysis/{workflow_id}/report"
    )
    assert anonymous.status_code == 401

    cross_user = await client.get(
        f"/api/v1/cases/{case_id}/analysis/{workflow_id}/report",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert cross_user.status_code == 404

    html = await client.get(
        f"/api/v1/cases/{case_id}/analysis/{workflow_id}/report?format=html",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert html.status_code == 200
    assert html.headers["content-type"].startswith("text/html")
    assert "attachment" in html.headers["content-disposition"]
    assert "Case Intelligence Report" in html.text

    markdown = await client.get(
        f"/api/v1/cases/{case_id}/analysis/{workflow_id}/report?format=markdown",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert markdown.status_code == 200
    assert markdown.headers["content-type"].startswith("text/markdown")
    assert markdown.text.startswith("# Case Intelligence Report")


@pytest.mark.asyncio
async def test_report_export_rejects_incomplete_run(client, test_app):
    token, user_id = await register(client, "report-incomplete@test.com")
    case_id = await create_case(client, token)

    factory = test_app.state.test_session_factory
    run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    async with factory() as session:
        session.add(
            WorkflowRun(
                id=run_id,
                case_id=case_id,
                user_id=user_id,
                workflow_type="case_analysis",
                status="failed",
                progress=100,
                current_step="failed",
                input_payload={},
                steps=[],
                token_usage={},
                attempt_count=1,
                error_code="provider_error",
                error_message="Previous attempt failed.",
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()

    response = await client.get(
        f"/api/v1/cases/{case_id}/analysis/{run_id}/report",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409
