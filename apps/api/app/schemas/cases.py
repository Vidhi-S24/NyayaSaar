"""
NyayaSaar API — Cases Pydantic schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


CaseStatus = Literal["active", "review", "closed", "archived"]
CasePriority = Literal["high", "medium", "low"]


class CaseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    case_number: str | None = Field(default=None, max_length=100)
    court: str | None = Field(default=None, max_length=255)
    jurisdiction: str | None = Field(default=None, max_length=255)
    status: CaseStatus = "active"
    priority: CasePriority = "medium"
    summary: str | None = None
    tags: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


class CaseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    case_number: str | None = None
    court: str | None = None
    jurisdiction: str | None = None
    status: CaseStatus | None = None
    priority: CasePriority | None = None
    summary: str | None = None
    tags: list[str] | None = None
    issues: list[str] | None = None


class CaseResponse(BaseModel):
    id: str
    owner_id: str
    title: str
    case_number: str | None
    court: str | None
    jurisdiction: str | None
    status: str
    priority: str
    summary: str | None
    tags: list
    issues: list
    documents_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CaseListResponse(BaseModel):
    items: list[CaseResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
