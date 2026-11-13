"""
NyayaSaar API — Cases router (full CRUD)
GET    /api/v1/cases
POST   /api/v1/cases
GET    /api/v1/cases/{case_id}
PATCH  /api/v1/cases/{case_id}
DELETE /api/v1/cases/{case_id}
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.db.session import get_async_session
from app.models.responses import ApiResponse
from app.schemas.cases import CaseCreate, CaseListResponse, CaseResponse, CaseUpdate
from app.services.auth import get_current_user
from app.services import cases as case_service

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("", response_model=ApiResponse[CaseListResponse])
async def list_cases(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> ApiResponse[CaseListResponse]:
    cases, total = await case_service.list_cases(
        db,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        search=search,
        status_filter=status,
    )
    return ApiResponse.ok(
        CaseListResponse(
            items=[CaseResponse.model_validate(c) for c in cases],
            total=total,
            page=page,
            page_size=page_size,
            has_next=(page * page_size) < total,
        )
    )


@router.post("", response_model=ApiResponse[CaseResponse], status_code=201)
async def create_case(
    body: CaseCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> ApiResponse[CaseResponse]:
    case = await case_service.create_case(db, user_id=current_user.id, data=body)
    return ApiResponse.ok(CaseResponse.model_validate(case))


@router.get("/{case_id}", response_model=ApiResponse[CaseResponse])
async def get_case(
    case_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> ApiResponse[CaseResponse]:
    case = await case_service.get_case(db, case_id=case_id, user_id=current_user.id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return ApiResponse.ok(CaseResponse.model_validate(case))


@router.patch("/{case_id}", response_model=ApiResponse[CaseResponse])
async def update_case(
    case_id: str,
    body: CaseUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> ApiResponse[CaseResponse]:
    case = await case_service.update_case(db, case_id=case_id, user_id=current_user.id, data=body)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return ApiResponse.ok(CaseResponse.model_validate(case))


@router.delete("/{case_id}", response_model=ApiResponse[None])
async def delete_case(
    case_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> ApiResponse[None]:
    deleted = await case_service.delete_case(db, case_id=case_id, user_id=current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Case not found")
    return ApiResponse.ok(None)
