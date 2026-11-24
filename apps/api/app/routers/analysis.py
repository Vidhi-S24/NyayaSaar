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
from app.config import get_settings
from app.db.models.user import User
from app.db.session import get_async_session
from app.models.responses import ApiResponse
from app.schemas.analysis import (
    CaseAnalysisRequest,
    WorkflowRunListResponse,
    WorkflowRunResponse,
)
from app.services import analysis as analysis_service
from app.services import report as report_service
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
    limit: int = Query(default=20, ge=1, le=100),
) -> ApiResponse[WorkflowRunListResponse]:
    """List recent analysis runs for an owned case, newest first."""
    try:
        runs, total = await analysis_service.list_workflow_runs(
            db, case_id=case_id, user_id=current_user.id, limit=limit
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
