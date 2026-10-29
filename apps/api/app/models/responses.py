"""
NyayaSaar API — Shared response models

All API responses are wrapped in a consistent envelope so clients can
reliably detect success vs failure without inspecting HTTP status codes alone.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiError(BaseModel):
    """Structured error payload included in error responses."""

    code: str = Field(description="Machine-readable error code")
    message: str = Field(description="Human-readable error message")
    details: dict[str, Any] | None = Field(
        default=None, description="Optional structured error details"
    )


class ApiResponse(BaseModel, Generic[T]):
    """Standard API response envelope."""

    success: bool
    data: T | None = None
    error: ApiError | None = None
    meta: dict[str, Any] | None = None

    @classmethod
    def ok(cls, data: T, meta: dict[str, Any] | None = None) -> "ApiResponse[T]":
        return cls(success=True, data=data, meta=meta)

    @classmethod
    def fail(
        cls,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> "ApiResponse[None]":
        return cls(success=False, error=ApiError(code=code, message=message, details=details))


class PaginatedData(BaseModel, Generic[T]):
    """Pagination wrapper for list endpoints."""

    items: list[T]
    total: int
    page: int
    page_size: int
    has_next: bool


class HealthServiceStatus(BaseModel):
    status: str  # "ok" | "degraded" | "unavailable"
    latency_ms: float | None = None
    message: str | None = None


class HealthResponse(BaseModel):
    status: str  # "ok" | "degraded" | "error"
    version: str
    env: str
    timestamp: str
    services: dict[str, HealthServiceStatus]

