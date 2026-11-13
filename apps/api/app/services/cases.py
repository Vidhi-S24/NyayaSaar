"""
NyayaSaar API — Cases CRUD service layer.
Authorization is enforced here — not just in routers.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.case import Case
from app.schemas.cases import CaseCreate, CaseUpdate


async def create_case(db: AsyncSession, user_id: str, data: CaseCreate) -> Case:
    case = Case(
        id=str(uuid.uuid4()),
        owner_id=user_id,
        title=data.title,
        case_number=data.case_number,
        court=data.court,
        jurisdiction=data.jurisdiction,
        status=data.status,
        priority=data.priority,
        summary=data.summary,
        tags=data.tags,
        issues=data.issues,
    )
    db.add(case)
    await db.flush()
    await db.refresh(case)
    return case


async def get_case(db: AsyncSession, case_id: str, user_id: str) -> Case | None:
    """Return case if user is owner, else None (do not leak existence)."""
    result = await db.execute(
        select(Case).where(Case.id == case_id, Case.owner_id == user_id)
    )
    return result.scalar_one_or_none()


async def list_cases(
    db: AsyncSession,
    user_id: str,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    status_filter: str | None = None,
) -> tuple[list[Case], int]:
    """Return (cases, total) for the authenticated user."""
    base_q = select(Case).where(Case.owner_id == user_id)

    if status_filter:
        base_q = base_q.where(Case.status == status_filter)
    if search:
        term = f"%{search}%"
        base_q = base_q.where(
            or_(
                Case.title.ilike(term),
                Case.case_number.ilike(term),
                Case.court.ilike(term),
            )
        )

    # Count total
    count_q = select(func.count()).select_from(base_q.subquery())
    total_result = await db.execute(count_q)
    total = total_result.scalar_one()

    # Paginate
    offset = (page - 1) * page_size
    rows_q = base_q.order_by(Case.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(rows_q)
    cases = list(result.scalars().all())

    return cases, total


async def update_case(
    db: AsyncSession, case_id: str, user_id: str, data: CaseUpdate
) -> Case | None:
    case = await get_case(db, case_id, user_id)
    if case is None:
        return None
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(case, field, value)
    await db.flush()
    await db.refresh(case)
    return case


async def delete_case(db: AsyncSession, case_id: str, user_id: str) -> bool:
    case = await get_case(db, case_id, user_id)
    if case is None:
        return False
    await db.delete(case)
    await db.flush()
    return True
