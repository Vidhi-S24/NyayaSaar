"""Analysis API integration tests (auth, polling, retries, source fidelity)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.db.models.document import Document, DocumentChunk
from app.db.models.workflow import WorkflowRun
from app.ai.base import LLMProvider, ProviderError
from app.services.analysis import WorkflowRunner


class FailingProvider(LLMProvider):
    name = "failing"
    is_mock = False

    def __init__(self) -> None:
        super().__init__(model="failing-1", max_retries=0, structured_retries=0)

    async def _generate_text(self, request):
        raise ProviderError(
            "The AI provider rejected the API key.",
            code="provider_auth_error",
            retryable=False,
        )


async def register(client, email: str) -> tuple[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "securepass123",
            "full_name": "Analysis User",
        },
    )
    assert response.status_code == 201, response.text
    token = response.json()["data"]["access_token"]
    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    return token, me.json()["data"]["id"]


async def create_case(client, token: str, title: str = "Analysis case") -> str:
    response = await client.post(
        "/api/v1/cases",
        json={"title": title},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


async def seed_ready_document(
    test_app,
    *,
    case_id: str,
    user_id: str,
    name: str = "agreement.txt",
    text: str = "The agreement was signed on 1 May 2024 by both parties.",
) -> str:
    factory = test_app.state.test_session_factory
    doc_id = str(uuid.uuid4())
    async with factory() as session:
        document = Document(
            id=doc_id,
            case_id=case_id,
            owner_id=user_id,
            original_name=name,
            storage_key=f"test/{doc_id}",
            content_type="text/plain",
            file_size=len(text),
            processing_status="ready",
            page_count=1,
            extraction_completeness=100,
        )
        session.add(document)
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


async def seed_run(
    test_app,
    *,
    case_id: str,
    user_id: str,
    status: str = "failed",
    attempt_count: int = 0,
) -> str:
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
                status=status,
                progress=100 if status == "failed" else 10,
                current_step=status,
                input_payload={"document_ids": [], "focus": None},
                steps=[],
                token_usage={},
                attempt_count=attempt_count,
                error_code="provider_error" if status == "failed" else None,
                error_message="Previous attempt failed." if status == "failed" else None,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()
    return run_id


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analysis_endpoints_require_auth(client):
    response = await client.post("/api/v1/cases/any/analysis")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_ai_status_requires_auth(client):
    response = await client.get("/api/v1/ai/status")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_ai_status_reports_fixture_mode_without_secrets(client):
    token, _ = await register(client, "status@test.com")
    response = await client.get("/api/v1/ai/status", headers=auth(token))
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["is_mock"] is True
    assert "fixture" in data["message"].lower()
    assert "api_key" not in data
    assert "key" not in " ".join(data.keys()).lower()


# ---------------------------------------------------------------------------
# Start / poll
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analysis_without_documents_completes_as_insufficient(client):
    token, _ = await register(client, "nodocs@test.com")
    case_id = await create_case(client, token)

    start = await client.post(
        f"/api/v1/cases/{case_id}/analysis", json={}, headers=auth(token)
    )
    assert start.status_code == 202, start.text
    workflow_id = start.json()["data"]["id"]
    assert start.json()["data"]["status"] in ("queued", "running", "completed")

    poll = await client.get(
        f"/api/v1/cases/{case_id}/analysis/{workflow_id}", headers=auth(token)
    )
    assert poll.status_code == 200
    run = poll.json()["data"]
    assert run["status"] == "completed"
    assert run["is_mock"] is True
    assert run["provider"] == "mock"
    assert run["result"]["insufficient_sources"] is True
    assert run["result"]["is_mock"] is True


@pytest.mark.asyncio
async def test_analysis_preserves_document_ids_and_page_references(client, test_app):
    token, user_id = await register(client, "sources@test.com")
    case_id = await create_case(client, token)
    doc_id = await seed_ready_document(
        test_app, case_id=case_id, user_id=user_id
    )

    start = await client.post(
        f"/api/v1/cases/{case_id}/analysis", json={}, headers=auth(token)
    )
    assert start.status_code == 202, start.text
    workflow_id = start.json()["data"]["id"]

    poll = await client.get(
        f"/api/v1/cases/{case_id}/analysis/{workflow_id}", headers=auth(token)
    )
    run = poll.json()["data"]
    assert run["status"] == "completed"
    result = run["result"]
    assert result["insufficient_sources"] is False
    assert result["source_manifest"][0]["document_id"] == doc_id
    assert result["source_manifest"][0]["page_number"] == 1
    assert result["facts"], "fixture should produce at least one source-linked fact"
    assert result["facts"][0]["sources"][0]["document_id"] == doc_id
    assert result["facts"][0]["sources"][0]["page_number"] == 1
    assert run["token_usage"]["total"] >= 0


@pytest.mark.asyncio
async def test_analysis_is_scoped_to_case_owner(client, test_app):
    token_a, user_a = await register(client, "owner-analysis@test.com")
    token_b, _ = await register(client, "other-analysis@test.com")
    case_id = await create_case(client, token_a)
    await seed_ready_document(test_app, case_id=case_id, user_id=user_a)

    start = await client.post(
        f"/api/v1/cases/{case_id}/analysis", json={}, headers=auth(token_a)
    )
    workflow_id = start.json()["data"]["id"]

    cross_start = await client.post(
        f"/api/v1/cases/{case_id}/analysis", json={}, headers=auth(token_b)
    )
    assert cross_start.status_code == 404

    cross_get = await client.get(
        f"/api/v1/cases/{case_id}/analysis/{workflow_id}", headers=auth(token_b)
    )
    assert cross_get.status_code == 404

    cross_list = await client.get(
        f"/api/v1/cases/{case_id}/analysis", headers=auth(token_b)
    )
    assert cross_list.status_code == 404


@pytest.mark.asyncio
async def test_list_analysis_runs(client, test_app):
    token, user_id = await register(client, "list-analysis@test.com")
    case_id = await create_case(client, token)
    await seed_ready_document(test_app, case_id=case_id, user_id=user_id)

    start = await client.post(
        f"/api/v1/cases/{case_id}/analysis", json={}, headers=auth(token)
    )
    assert start.status_code == 202

    response = await client.get(
        f"/api/v1/cases/{case_id}/analysis", headers=auth(token)
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["status"] == "completed"


@pytest.mark.asyncio
async def test_unknown_analysis_returns_404(client):
    token, _ = await register(client, "missing@test.com")
    case_id = await create_case(client, token)
    response = await client.get(
        f"/api/v1/cases/{case_id}/analysis/does-not-exist", headers=auth(token)
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_selected_document_must_belong_to_case(client, test_app):
    token, user_id = await register(client, "selected@test.com")
    case_id = await create_case(client, token)
    other_case = await create_case(client, token, title="Other case")
    other_doc = await seed_ready_document(
        test_app, case_id=other_case, user_id=user_id
    )

    response = await client.post(
        f"/api/v1/cases/{case_id}/analysis",
        json={"document_ids": [other_doc]},
        headers=auth(token),
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Concurrency / retries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_active_run_blocks_a_second_start(client, test_app):
    token, user_id = await register(client, "conflict@test.com")
    case_id = await create_case(client, token)
    await seed_run(test_app, case_id=case_id, user_id=user_id, status="queued")

    response = await client.post(
        f"/api/v1/cases/{case_id}/analysis", json={}, headers=auth(token)
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_failed_run_can_be_retried(client, test_app):
    token, user_id = await register(client, "retry@test.com")
    case_id = await create_case(client, token)
    await seed_ready_document(test_app, case_id=case_id, user_id=user_id)
    run_id = await seed_run(
        test_app, case_id=case_id, user_id=user_id, status="failed", attempt_count=0
    )

    retry = await client.post(
        f"/api/v1/cases/{case_id}/analysis/{run_id}/retry", headers=auth(token)
    )
    assert retry.status_code == 202, retry.text

    poll = await client.get(
        f"/api/v1/cases/{case_id}/analysis/{run_id}", headers=auth(token)
    )
    run = poll.json()["data"]
    assert run["status"] == "completed"
    assert run["attempt_count"] == 1
    assert run["error"] is None


@pytest.mark.asyncio
async def test_retry_limit_is_enforced(client, test_app):
    token, user_id = await register(client, "retrylimit@test.com")
    case_id = await create_case(client, token)
    run_id = await seed_run(
        test_app, case_id=case_id, user_id=user_id, status="failed", attempt_count=2
    )

    response = await client.post(
        f"/api/v1/cases/{case_id}/analysis/{run_id}/retry", headers=auth(token)
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_provider_failure_is_recoverable_and_retryable(client, test_app):
    token, user_id = await register(client, "providerfail@test.com")
    case_id = await create_case(client, token)
    await seed_ready_document(test_app, case_id=case_id, user_id=user_id)

    original_runner = test_app.state.workflow_runner
    test_app.state.workflow_runner = WorkflowRunner(
        test_app.state.test_session_factory,
        provider_factory=lambda settings: FailingProvider(),
    )
    try:
        start = await client.post(
            f"/api/v1/cases/{case_id}/analysis", json={}, headers=auth(token)
        )
        assert start.status_code == 202
        workflow_id = start.json()["data"]["id"]

        failed = await client.get(
            f"/api/v1/cases/{case_id}/analysis/{workflow_id}", headers=auth(token)
        )
        run = failed.json()["data"]
        assert run["status"] == "failed"
        assert run["error"]["code"] == "provider_auth_error"
        assert run["result"] is None
        assert run["attempt_count"] == 1
    finally:
        test_app.state.workflow_runner = original_runner

    retry = await client.post(
        f"/api/v1/cases/{case_id}/analysis/{workflow_id}/retry", headers=auth(token)
    )
    assert retry.status_code == 202, retry.text

    completed = await client.get(
        f"/api/v1/cases/{case_id}/analysis/{workflow_id}", headers=auth(token)
    )
    run = completed.json()["data"]
    assert run["status"] == "completed"
    assert run["error"] is None
    assert run["attempt_count"] == 2


@pytest.mark.asyncio
async def test_completed_run_is_not_retryable(client, test_app):
    token, user_id = await register(client, "retrydone@test.com")
    case_id = await create_case(client, token)
    run_id = await seed_run(
        test_app, case_id=case_id, user_id=user_id, status="completed", attempt_count=1
    )

    response = await client.post(
        f"/api/v1/cases/{case_id}/analysis/{run_id}/retry", headers=auth(token)
    )
    assert response.status_code == 422
