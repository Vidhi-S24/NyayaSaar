"""Analysis workflow endpoints.

Long-running work is never executed synchronously in the request. The POST
endpoint creates a queued run, commits it, and schedules the bounded runner as
a background task. Clients poll the run endpoint.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.schemas import CaseAnalysisResult
from app.agents.schemas_contradiction import ContradictionResult
from app.agents.schemas_precedent import PrecedentResult
from app.agents.schemas_stage10 import AdvocateResult, JudgeResult
from app.config import get_settings
from app.db.models.user import User
from app.db.session import get_async_session
from app.models.responses import ApiResponse
from app.schemas.analysis import (
    CaseAnalysisRequest,
    CitationLinkListResponse,
    CitationLinkResponse,
    FindingReviewListResponse,
    FindingReviewRequest,
    FindingReviewResponse,
    WorkflowRunListResponse,
    WorkflowRunResponse,
)
from app.services import analysis as analysis_service
from app.services import report as report_service
from app.services import report_stage10 as report_stage10_service
from app.services.auth import get_current_user

logger = logging.getLogger("nyayasaar.routers.analysis")

router = APIRouter(
    prefix="/cases/{case_id}/analysis",
    tags=["analysis"],
)

settings = get_settings()


def _get_runner(request: Request):
    runner = getattr(request.app.state, "workflow_runner", None)
    if runner is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The analysis runner is not available.",
        )
    return runner


@router.post(
    "",
    response_model=ApiResponse[WorkflowRunResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_analysis(
    case_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
    body: CaseAnalysisRequest | None = None,
) -> ApiResponse[WorkflowRunResponse]:
    """Queue a bounded Case Intelligence workflow and return its run ID."""
    runner = _get_runner(request)
    payload = body or CaseAnalysisRequest()

    try:
        run = await analysis_service.create_workflow_run(
            db,
            case_id=case_id,
            user_id=current_user.id,
            data=payload,
            workflow_type=payload.workflow_type,
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Case not found."
        )
    except analysis_service.ActiveWorkflowExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "An analysis is already queued or running for this case "
                f"(workflow {exc.workflow_id}). Wait for it to finish."
            ),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )

    # Commit before scheduling so the background runner can see the row.
    await db.commit()
    background_tasks.add_task(runner, run.id)

    return ApiResponse.ok(
        WorkflowRunResponse.from_run(run),
        meta={"poll_after_ms": 1500},
    )


@router.get("", response_model=ApiResponse[WorkflowRunListResponse])
async def list_analyses(
    case_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
    workflow_type: str = Query(default="case_analysis"),
    limit: int = Query(default=20, ge=1, le=100),
) -> ApiResponse[WorkflowRunListResponse]:
    """List recent analysis runs for an owned case, newest first."""
    try:
        runs, total = await analysis_service.list_workflow_runs(
            db,
            case_id=case_id,
            user_id=current_user.id,
            workflow_type=workflow_type,
            limit=limit,
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Case not found."
        )

    return ApiResponse.ok(
        WorkflowRunListResponse(
            items=[WorkflowRunResponse.from_run(run) for run in runs],
            total=total,
        )
    )


@router.get("/{workflow_id}", response_model=ApiResponse[WorkflowRunResponse])
async def get_analysis(
    case_id: str,
    workflow_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> ApiResponse[WorkflowRunResponse]:
    """Get status, progress, and the structured result of one run."""
    run = await analysis_service.get_workflow_run(
        db,
        workflow_id=workflow_id,
        user_id=current_user.id,
        case_id=case_id,
    )
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found."
        )
    return ApiResponse.ok(WorkflowRunResponse.from_run(run))


@router.post(
    "/{workflow_id}/retry",
    response_model=ApiResponse[WorkflowRunResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_analysis(
    case_id: str,
    workflow_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> ApiResponse[WorkflowRunResponse]:
    """Re-queue a failed analysis, subject to the configured retry limit."""
    runner = _get_runner(request)
    try:
        run = await analysis_service.retry_workflow_run(
            db,
            workflow_id=workflow_id,
            user_id=current_user.id,
            case_id=case_id,
            settings=settings,
        )
    except analysis_service.WorkflowNotRetryableError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found."
        )

    await db.commit()
    background_tasks.add_task(runner, run.id)
    return ApiResponse.ok(
        WorkflowRunResponse.from_run(run),
        meta={"poll_after_ms": 1500},
    )


@router.get("/{workflow_id}/report")
async def download_report(
    case_id: str,
    workflow_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
    format: str = Query(default="html", pattern="^(html|markdown)$"),
) -> Response:
    """Download a completed analysis as a print-ready HTML or Markdown report.

    The report is rendered from the persisted, verified result only. No model is
    called and no new facts are added.
    """
    loaded = await analysis_service.get_run_and_case(
        db,
        workflow_id=workflow_id,
        user_id=current_user.id,
        case_id=case_id,
    )
    if loaded is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found."
        )
    case, run = loaded

    if run.status != "completed" or not run.result:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The analysis has not completed, so a report is not available.",
        )

    if run.workflow_type == "contradiction":
        try:
            c_result = ContradictionResult.model_validate(run.result)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="The stored contradiction analysis could not be read.",
            )
        reviews = await analysis_service.list_finding_reviews(
            db, case_id=case_id, workflow_id=workflow_id, user_id=current_user.id
        )
        review_map = {r.finding_id: r for r in (reviews or [])}
        if format == "markdown":
            body = report_service.render_contradiction_report_markdown(
                case, run, c_result, reviews=review_map
            )
            filename = report_service.report_filename(case, run, "md")
            return PlainTextResponse(
                content=body,
                media_type="text/markdown; charset=utf-8",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "Cache-Control": "private, no-store",
                },
            )
        body = report_service.render_contradiction_report_html(
            case, run, c_result, reviews=review_map
        )
        filename = report_service.report_filename(case, run, "html")
        return HTMLResponse(
            content=body,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "private, no-store",
                "Content-Security-Policy": (
                    "default-src 'none'; style-src 'unsafe-inline'; img-src data:"
                ),
                "X-Content-Type-Options": "nosniff",
            },
        )

    if run.workflow_type == "precedent":
        try:
            p_result = PrecedentResult.model_validate(run.result)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="The stored precedent analysis could not be read.",
            )
        if format == "markdown":
            body = report_service.render_precedent_report_markdown(case, run, p_result)
            filename = report_service.report_filename(case, run, "md")
            return PlainTextResponse(
                content=body,
                media_type="text/markdown; charset=utf-8",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "Cache-Control": "private, no-store",
                },
            )
        body = report_service.render_precedent_report_html(case, run, p_result)
        filename = report_service.report_filename(case, run, "html")
        return HTMLResponse(
            content=body,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "private, no-store",
                "Content-Security-Policy": (
                    "default-src 'none'; style-src 'unsafe-inline'; img-src data:"
                ),
                "X-Content-Type-Options": "nosniff",
            },
        )

    if run.workflow_type == "advocate":
        try:
            a_result = AdvocateResult.model_validate(run.result)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="The stored advocate analysis could not be read.",
            )
        if format == "markdown":
            body = report_stage10_service.render_advocate_report_markdown(case, run, a_result)
            filename = report_service.report_filename(case, run, "md", "advocate")
            return PlainTextResponse(
                content=body,
                media_type="text/markdown; charset=utf-8",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "Cache-Control": "private, no-store",
                },
            )
        body = report_stage10_service.render_advocate_report_html(case, run, a_result)
        filename = report_service.report_filename(case, run, "html", "advocate")
        return HTMLResponse(
            content=body,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "private, no-store",
                "Content-Security-Policy": (
                    "default-src 'none'; style-src 'unsafe-inline'; img-src data:"
                ),
                "X-Content-Type-Options": "nosniff",
            },
        )

    if run.workflow_type == "judge":
        try:
            j_result = JudgeResult.model_validate(run.result)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="The stored judge/clerk audit could not be read.",
            )
        if format == "markdown":
            body = report_stage10_service.render_judge_report_markdown(case, run, j_result)
            filename = report_service.report_filename(case, run, "md", "judge-audit")
            return PlainTextResponse(
                content=body,
                media_type="text/markdown; charset=utf-8",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "Cache-Control": "private, no-store",
                },
            )
        body = report_stage10_service.render_judge_report_html(case, run, j_result)
        filename = report_service.report_filename(case, run, "html", "judge-audit")
        return HTMLResponse(
            content=body,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "private, no-store",
                "Content-Security-Policy": (
                    "default-src 'none'; style-src 'unsafe-inline'; img-src data:"
                ),
                "X-Content-Type-Options": "nosniff",
            },
        )

    try:
        result = CaseAnalysisResult.model_validate(run.result)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The stored analysis could not be read.",
        )

    if format == "markdown":
        body = report_service.render_case_report_markdown(case, run, result)
        filename = report_service.report_filename(case, run, "md")
        return PlainTextResponse(
            content=body,
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "private, no-store",
            },
        )

    body = report_service.render_case_report_html(case, run, result)
    filename = report_service.report_filename(case, run, "html")
    return HTMLResponse(
        content=body,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
            # The report is self-contained; block scripts entirely.
            "Content-Security-Policy": (
                "default-src 'none'; style-src 'unsafe-inline'; img-src data:"
            ),
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/{workflow_id}/reviews",
    response_model=ApiResponse[FindingReviewListResponse],
)
async def list_reviews(
    case_id: str,
    workflow_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> ApiResponse[FindingReviewListResponse]:
    """List persisted finding review decisions and audit history for a run."""
    rows = await analysis_service.list_finding_reviews(
        db,
        case_id=case_id,
        workflow_id=workflow_id,
        user_id=current_user.id,
    )
    if rows is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found."
        )
    return ApiResponse.ok(
        FindingReviewListResponse(
            items=[FindingReviewResponse.from_model(r) for r in rows]
        )
    )


@router.patch(
    "/{workflow_id}/findings/{finding_id}/review",
    response_model=ApiResponse[FindingReviewResponse],
)
async def update_finding_review(
    case_id: str,
    workflow_id: str,
    finding_id: str,
    body: FindingReviewRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> ApiResponse[FindingReviewResponse]:
    """Record a review decision (confirmed/dismissed/needs_review) with audit trail."""
    try:
        row = await analysis_service.upsert_finding_review(
            db,
            case_id=case_id,
            workflow_id=workflow_id,
            finding_id=finding_id,
            user_id=current_user.id,
            user_email=current_user.email,
            status=body.status,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found."
        )
    await db.commit()
    return ApiResponse.ok(FindingReviewResponse.from_model(row))


@router.get(
    "/{workflow_id}/citations",
    response_model=ApiResponse[CitationLinkListResponse],
)
async def list_citations(
    case_id: str,
    workflow_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> ApiResponse[CitationLinkListResponse]:
    """List persisted citation links for a completed precedent run."""
    rows = await analysis_service.list_citations_for_run(
        db,
        case_id=case_id,
        workflow_id=workflow_id,
        user_id=current_user.id,
    )
    if rows is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found."
        )
    items = [CitationLinkResponse.from_model(r) for r in rows]
    return ApiResponse.ok(CitationLinkListResponse(items=items, total=len(items)))
