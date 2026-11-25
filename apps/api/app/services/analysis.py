"""Analysis workflow service and in-process runner.

Stage 6 deliberately avoids Redis/Celery. Workflows are bounded (120 s by
default) and run as FastAPI background tasks in the same Render web process.
Status and results are persisted so the UI can poll and so failures survive a
restart. A durable queue is a later-stage concern (see D-024/D-025).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from app.agents.context import WorkflowContext
from app.agents.graph import run_case_analysis_graph
from app.agents.graph_contradiction import run_contradiction_graph
from app.agents.schemas import (
    CASE_INTELLIGENCE_PROMPT_VERSION,
    CASE_INTELLIGENCE_RESULT_SCHEMA_VERSION,
    CASE_INTELLIGENCE_WORKFLOW_VERSION,
)
from app.agents.schemas_contradiction import (
    CONTRADICTION_PROMPT_VERSION,
    CONTRADICTION_RESULT_SCHEMA_VERSION,
    CONTRADICTION_WORKFLOW_VERSION,
)
from app.agents.state import CaseAnalysisState
from app.agents.tools.sources import load_case_sources
from app.ai.base import LLMProvider, ProviderError, ProviderNotConfiguredError
from app.ai.embeddings import get_embedding_provider
from app.ai.registry import get_provider
from app.config import Settings, get_settings
from app.db.models.case import Case
from app.db.models.document import Document
from app.db.models.finding_review import FindingReview
from app.db.models.workflow import WorkflowRun
from app.schemas.analysis import CaseAnalysisRequest
from app.services.retrieval.hybrid import RetrievalFilters, hybrid_search

logger = logging.getLogger("nyayasaar.analysis")


class ActiveWorkflowExistsError(Exception):
    """A queued/running analysis already exists for this case and user."""

    def __init__(self, workflow_id: str) -> None:
        super().__init__("An analysis is already running for this case.")
        self.workflow_id = workflow_id


class WorkflowNotRetryableError(ValueError):
    """The workflow cannot be retried in its current state."""


# ---------------------------------------------------------------------------
# Authorization helper
# ---------------------------------------------------------------------------


async def _get_owned_case(
    db: AsyncSession, case_id: str, user_id: str
) -> Case | None:
    result = await db.execute(
        select(Case).where(Case.id == case_id, Case.owner_id == user_id)
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Create / read / retry
# ---------------------------------------------------------------------------


async def create_workflow_run(
    db: AsyncSession,
    *,
    case_id: str,
    user_id: str,
    data: CaseAnalysisRequest,
    workflow_type: str = "case_analysis",
) -> WorkflowRun:
    case = await _get_owned_case(db, case_id, user_id)
    if case is None:
        raise PermissionError("Case not found or access denied.")

    document_ids = list(dict.fromkeys(data.document_ids or []))
    if document_ids:
        docs_result = await db.execute(
            select(Document).where(
                Document.case_id == case_id,
                Document.owner_id == user_id,
                Document.id.in_(document_ids),
            )
        )
        docs = {doc.id: doc for doc in docs_result.scalars().all()}
        missing = [doc_id for doc_id in document_ids if doc_id not in docs]
        if missing:
            raise ValueError(
                "One or more selected documents do not belong to this case."
            )
        not_ready = [
            doc.original_name
            for doc in docs.values()
            if doc.processing_status != "ready"
        ]
        if not_ready:
            names = ", ".join(not_ready[:3])
            raise ValueError(
                f"These documents are not ready for analysis: {names}."
            )

    active_result = await db.execute(
        select(WorkflowRun)
        .where(
            WorkflowRun.case_id == case_id,
            WorkflowRun.user_id == user_id,
            WorkflowRun.workflow_type == workflow_type,
            WorkflowRun.status.in_(("queued", "running")),
        )
        .order_by(WorkflowRun.created_at.desc())
        .limit(1)
    )
    active = active_result.scalar_one_or_none()
    if active is not None:
        raise ActiveWorkflowExistsError(active.id)

    run = WorkflowRun(
        id=str(uuid.uuid4()),
        case_id=case_id,
        user_id=user_id,
        workflow_type=workflow_type,
        status="queued",
        progress=0,
        input_payload={"document_ids": document_ids, "focus": data.focus},
        steps=[],
        token_usage={},
        attempt_count=0,
    )
    db.add(run)
    await db.flush()
    await db.refresh(run)
    return run


async def get_workflow_run(
    db: AsyncSession,
    *,
    workflow_id: str,
    user_id: str,
    case_id: str | None = None,
) -> WorkflowRun | None:
    query = select(WorkflowRun).where(
        WorkflowRun.id == workflow_id,
        WorkflowRun.user_id == user_id,
    )
    if case_id is not None:
        query = query.where(WorkflowRun.case_id == case_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_run_and_case(
    db: AsyncSession,
    *,
    workflow_id: str,
    user_id: str,
    case_id: str,
) -> tuple[Case, WorkflowRun] | None:
    """Load an owned case and one of its analysis runs, or ``None``.

    Used by the report export so a download cannot bypass the same ownership
    checks as the JSON endpoints.
    """
    case = await _get_owned_case(db, case_id, user_id)
    if case is None:
        return None
    run = await get_workflow_run(
        db, workflow_id=workflow_id, user_id=user_id, case_id=case_id
    )
    if run is None:
        return None
    return case, run


async def list_workflow_runs(
    db: AsyncSession,
    *,
    case_id: str,
    user_id: str,
    workflow_type: str = "case_analysis",
    limit: int = 20,
) -> tuple[list[WorkflowRun], int]:
    case = await _get_owned_case(db, case_id, user_id)
    if case is None:
        raise PermissionError("Case not found or access denied.")

    base = select(WorkflowRun).where(
        WorkflowRun.case_id == case_id,
        WorkflowRun.user_id == user_id,
        WorkflowRun.workflow_type == workflow_type,
    )
    count_result = await db.execute(
        select(func.count()).select_from(base.subquery())
    )
    total = count_result.scalar_one()

    rows = await db.execute(
        base.order_by(WorkflowRun.created_at.desc()).limit(max(1, min(limit, 100)))
    )
    return list(rows.scalars().all()), total


async def retry_workflow_run(
    db: AsyncSession,
    *,
    workflow_id: str,
    user_id: str,
    case_id: str,
    settings: Settings,
) -> WorkflowRun | None:
    run = await get_workflow_run(
        db, workflow_id=workflow_id, user_id=user_id, case_id=case_id
    )
    if run is None:
        return None
    if run.status != "failed":
        raise WorkflowNotRetryableError(
            "Only failed analyses can be retried."
        )
    if (run.attempt_count or 0) >= settings.agent_max_workflow_attempts:
        raise WorkflowNotRetryableError(
            "This analysis has reached its retry limit. Start a new analysis instead."
        )

    run.status = "queued"
    run.progress = 0
    run.current_step = None
    run.error_code = None
    run.error_message = None
    run.result = None
    run.steps = []
    run.token_usage = {}
    run.started_at = None
    run.completed_at = None
    await db.flush()
    await db.refresh(run)
    return run


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class WorkflowRunner:
    """Executes one queued workflow using a fresh database session."""

    def __init__(
        self,
        session_factory: sessionmaker[AsyncSession],
        *,
        provider_factory: Callable[[Settings], LLMProvider] | None = None,
        settings_factory: Callable[[], Settings] = get_settings,
    ) -> None:
        self._session_factory = session_factory
        self._provider_factory = provider_factory or get_provider
        self._settings_factory = settings_factory

    async def __call__(self, workflow_id: str) -> None:
        settings = self._settings_factory()
        try:
            async with self._session_factory() as db:
                run = await db.get(WorkflowRun, workflow_id)
                if run is None or run.status != "queued":
                    return
                await self._execute(db, run, settings)
                await db.commit()
        except Exception as exc:  # pragma: no cover - last-resort guard
            logger.error(
                "Workflow runner crashed workflow=%s type=%s",
                workflow_id,
                type(exc).__name__,
            )
            await self._mark_failed_best_effort(
                workflow_id,
                "internal_error",
                "The analysis workflow failed unexpectedly. You can retry it.",
            )

    async def _execute(
        self, db: AsyncSession, run: WorkflowRun, settings: Settings
    ) -> None:
        now = datetime.now(timezone.utc)
        run.status = "running"
        run.started_at = now
        run.progress = 5
        run.current_step = "starting"
        wtype = run.workflow_type or "case_analysis"
        if wtype not in ("case_analysis", "contradiction"):
            await self._fail(
                db,
                run,
                "unsupported_workflow",
                "This workflow type is not available in this release.",
            )
            return
        if wtype == "contradiction":
            run.workflow_version = CONTRADICTION_WORKFLOW_VERSION
            run.prompt_version = CONTRADICTION_PROMPT_VERSION
            run.result_schema_version = CONTRADICTION_RESULT_SCHEMA_VERSION
        else:
            run.workflow_version = CASE_INTELLIGENCE_WORKFLOW_VERSION
            run.prompt_version = CASE_INTELLIGENCE_PROMPT_VERSION
            run.result_schema_version = CASE_INTELLIGENCE_RESULT_SCHEMA_VERSION
        run.attempt_count = (run.attempt_count or 0) + 1
        run.error_code = None
        run.error_message = None
        run.steps = [
            {
                "step": "starting",
                "status": "running",
                "message": "Workflow accepted",
                "at": now.isoformat(),
            }
        ]
        await db.commit()

        case = await _get_owned_case(db, run.case_id, run.user_id)
        if case is None:
            await self._fail(
                db, run, "case_not_found", "The case is no longer available."
            )
            return

        try:
            provider = self._provider_factory(settings)
        except ProviderNotConfiguredError as exc:
            await self._fail(db, run, exc.code, exc.message)
            return
        except Exception as exc:
            logger.error(
                "Provider construction failed type=%s", type(exc).__name__
            )
            await self._fail(
                db,
                run,
                "provider_not_configured",
                "The configured AI provider could not be initialised.",
            )
            return

        run.provider = provider.name
        run.model = provider.model
        run.is_mock = provider.is_mock
        await db.commit()

        payload = run.input_payload or {}
        document_ids = payload.get("document_ids") or None
        source_result = await load_case_sources(
            db,
            case_id=run.case_id,
            user_id=run.user_id,
            document_ids=document_ids,
            max_chars=settings.agent_max_input_chars,
        )
        sources = source_result.sources
        source_notes = source_result.notes
        source_stats = source_result.stats

        case_context = {
            "title": case.title,
            "case_number": case.case_number,
            "court": case.court,
            "jurisdiction": case.jurisdiction,
            "summary": case.summary,
            "issues": case.issues or [],
            "focus": payload.get("focus"),
        }

        initial_state: CaseAnalysisState = {
            "workflow_id": run.id,
            "case_id": run.case_id,
            "started_at": now.isoformat(),
            "case_context": case_context,
            "sources": [s.as_dict() for s in sources],
            "source_notes": source_notes,
            "source_stats": source_stats,
            "provider_name": provider.name,
            "model_name": provider.model,
            "is_mock": provider.is_mock,
            "draft": None,
            "extraction_draft": None,
            "evidence_draft": None,
            "chronology": [],
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

        async def report(
            step: str, progress: int, message: str | None = None
        ) -> None:
            run.current_step = step
            run.progress = max(0, min(100, int(progress)))
            steps = list(run.steps or [])
            steps.append(
                {
                    "step": step,
                    "status": "running",
                    "message": message,
                    "at": datetime.now(timezone.utc).isoformat(),
                }
            )
            run.steps = steps[-40:]
            await db.commit()

        ctx = WorkflowContext(
            provider=provider,
            settings=settings,
            report=report,
            max_llm_calls=settings.agent_max_llm_calls,
            max_total_tokens=settings.agent_max_total_tokens,
            max_verifier_retries=settings.agent_max_verifier_retries,
        )

        if wtype == "contradiction" and sources:
            query_text = (payload.get("focus") or case.title or "").strip()
            if query_text:
                try:
                    emb = get_embedding_provider(settings)
                    hits, _ = await hybrid_search(
                        db,
                        query=query_text,
                        user_id=run.user_id,
                        filters=RetrievalFilters(
                            case_id=run.case_id,
                            source_type="case_document",
                        ),
                        settings=settings,
                        embedding_provider=emb,
                        limit=8,
                    )
                    case_context["retrieved_pairs"] = [
                        {
                            "title": h.title,
                            "page_number": h.page_number,
                            "hybrid_score": h.hybrid_score,
                            "text": h.text,
                        }
                        for h in hits
                    ]
                except Exception:
                    logger.debug("Optional hybrid pre-retrieval skipped for contradiction run")

        graph_fn = (
            run_contradiction_graph
            if wtype == "contradiction"
            else run_case_analysis_graph
        )

        try:
            final_state = await asyncio.wait_for(
                graph_fn(ctx, initial_state),
                timeout=settings.agent_execution_timeout_s,
            )
        except TimeoutError:
            await self._fail(
                db,
                run,
                "workflow_timeout",
                "The analysis exceeded the execution time limit. You can retry it.",
            )
            return
        except ProviderError as exc:
            await self._fail(db, run, exc.code, exc.message)
            return
        except Exception as exc:  # pragma: no cover - defensive
            logger.error(
                "Graph execution failed workflow=%s type=%s",
                run.id,
                type(exc).__name__,
            )
            await self._fail(
                db,
                run,
                "internal_error",
                "The analysis workflow failed unexpectedly. You can retry it.",
            )
            return

        run.token_usage = final_state.get("token_usage") or {}
        run.provider = str(final_state.get("provider_name", provider.name))
        run.model = str(final_state.get("model_name", provider.model))
        run.is_mock = bool(final_state.get("is_mock", provider.is_mock))

        if final_state.get("status") == "failed":
            errors = final_state.get("errors") or []
            first = errors[0] if errors else {}
            await self._fail(
                db,
                run,
                str(first.get("code", "internal_error")),
                str(
                    first.get(
                        "message", "The analysis workflow failed unexpectedly."
                    )
                ),
            )
            return

        result = final_state.get("result")
        if not result:
            await self._fail(
                db,
                run,
                "internal_error",
                "The workflow finished without a result. You can retry it.",
            )
            return

        completed_at = datetime.now(timezone.utc)
        run.result = result
        run.status = "completed"
        run.progress = 100
        run.current_step = "completed"
        run.error_code = None
        run.error_message = None
        run.completed_at = completed_at
        steps = list(run.steps or [])
        steps.append(
            {
                "step": "completed",
                "status": "completed",
                "message": (
                    "Completed with a development fixture; no AI model was called."
                    if run.is_mock
                    else "Analysis completed."
                ),
                "at": completed_at.isoformat(),
            }
        )
        run.steps = steps[-40:]
        await db.commit()

    async def _fail(
        self,
        db: AsyncSession,
        run: WorkflowRun,
        code: str,
        message: str,
    ) -> None:
        now = datetime.now(timezone.utc)
        run.status = "failed"
        run.progress = 100
        run.current_step = "failed"
        run.error_code = code[:60]
        run.error_message = (message or "The workflow failed.")[:2000]
        run.completed_at = now
        steps = list(run.steps or [])
        steps.append(
            {
                "step": "failed",
                "status": "failed",
                "message": run.error_message,
                "at": now.isoformat(),
            }
        )
        run.steps = steps[-40:]
        await db.commit()

    async def _mark_failed_best_effort(
        self, workflow_id: str, code: str, message: str
    ) -> None:
        try:
            async with self._session_factory() as db:
                run = await db.get(WorkflowRun, workflow_id)
                if run is not None and run.status in ("queued", "running"):
                    await self._fail(db, run, code, message)
                    await db.commit()
        except Exception:
            logger.warning(
                "Could not mark workflow %s as failed", workflow_id
            )


async def recover_stale_workflows(
    session_factory: sessionmaker[AsyncSession],
) -> int:
    """Mark workflows interrupted by a restart as failed and retryable."""
    recovered = 0
    try:
        async with session_factory() as db:
            result = await db.execute(
                select(WorkflowRun).where(
                    WorkflowRun.status.in_(("queued", "running"))
                )
            )
            now = datetime.now(timezone.utc)
            for run in result.scalars().all():
                run.status = "failed"
                run.progress = 100
                run.current_step = "failed"
                run.error_code = "interrupted_by_restart"
                run.error_message = (
                    "The server restarted before this analysis completed. "
                    "You can retry it."
                )
                run.completed_at = now
                steps = list(run.steps or [])
                steps.append(
                    {
                        "step": "failed",
                        "status": "failed",
                        "message": run.error_message,
                        "at": now.isoformat(),
                    }
                )
                run.steps = steps[-40:]
                recovered += 1
            if recovered:
                await db.commit()
    except Exception as exc:
        logger.warning(
            "Stale workflow recovery skipped: %s", type(exc).__name__
        )
    return recovered


# ---------------------------------------------------------------------------
# Stage 8 — Finding review & audit trail
# ---------------------------------------------------------------------------


async def list_finding_reviews(
    db: AsyncSession,
    *,
    case_id: str,
    workflow_id: str,
    user_id: str,
) -> list[FindingReview] | None:
    loaded = await get_run_and_case(
        db, workflow_id=workflow_id, user_id=user_id, case_id=case_id
    )
    if loaded is None:
        return None
    result = await db.execute(
        select(FindingReview)
        .where(
            FindingReview.workflow_id == workflow_id,
            FindingReview.case_id == case_id,
        )
        .order_by(FindingReview.updated_at.desc())
    )
    return list(result.scalars().all())


async def upsert_finding_review(
    db: AsyncSession,
    *,
    case_id: str,
    workflow_id: str,
    finding_id: str,
    user_id: str,
    user_email: str | None,
    status: str,
    note: str | None,
) -> FindingReview | None:
    loaded = await get_run_and_case(
        db, workflow_id=workflow_id, user_id=user_id, case_id=case_id
    )
    if loaded is None:
        return None
    _, run = loaded
    findings = (run.result or {}).get("findings") or []
    known_ids = {str(f.get("finding_id", "")) for f in findings}
    if finding_id not in known_ids:
        raise ValueError("Finding ID not found in this workflow result.")

    res = await db.execute(
        select(FindingReview).where(
            FindingReview.workflow_id == workflow_id,
            FindingReview.finding_id == finding_id,
        )
    )
    existing = res.scalar_one_or_none()
    now_iso = datetime.now(timezone.utc).isoformat()

    if existing is None:
        event = {
            "previous_status": "unreviewed",
            "new_status": status,
            "note": note,
            "user_id": user_id,
            "user_email": user_email,
            "at": now_iso,
        }
        review = FindingReview(
            id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            case_id=case_id,
            finding_id=finding_id,
            status=status,
            reviewer_note=note,
            updated_by_user_id=user_id,
            history=[event],
        )
        db.add(review)
        await db.flush()
        await db.refresh(review)
        return review

    event = {
        "previous_status": existing.status,
        "new_status": status,
        "note": note,
        "user_id": user_id,
        "user_email": user_email,
        "at": now_iso,
    }
    history = list(existing.history or [])
    history.append(event)
    existing.status = status
    existing.reviewer_note = note
    existing.updated_by_user_id = user_id
    existing.history = history
    await db.flush()
    await db.refresh(existing)
    return existing
