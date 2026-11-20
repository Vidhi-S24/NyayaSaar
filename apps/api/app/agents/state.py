"""Typed, JSON-serialisable LangGraph state."""

from __future__ import annotations

from typing import Any, TypedDict


class WorkflowError(TypedDict):
    code: str
    message: str


class CaseAnalysisState(TypedDict, total=False):
    # Identity
    workflow_id: str
    case_id: str
    started_at: str

    # Inputs (loaded by tools before the graph runs)
    case_context: dict[str, Any]
    sources: list[dict[str, Any]]
    source_notes: list[str]

    # Provider metadata (safe to persist; never includes the key)
    provider_name: str
    model_name: str
    is_mock: bool

    # Outputs
    draft: dict[str, Any] | None
    result: dict[str, Any] | None

    # Orchestration
    status: str  # running | failed | completed
    current_step: str
    progress: int
    outcome: str | None  # completed | insufficient_sources | provider_error | ...
    errors: list[WorkflowError]
    notes: list[str]

    # Bounded execution / verification
    retry_count: int
    needs_revision: bool
    verification_feedback: list[str]
    llm_calls: int
    token_usage: dict[str, int]
    token_budget_exhausted: bool
