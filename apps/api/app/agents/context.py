"""Runtime context shared by graph nodes.

The context carries the provider and bounded-execution limits. It is not part
of the serialisable graph state, so provider clients and database sessions
never end up in checkpoints.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.ai.base import LLMProvider
from app.config import Settings

if TYPE_CHECKING:
    from app.agents.state import CaseAnalysisState

ProgressReporter = Callable[[str, int, str | None], Awaitable[None]]

_BUDGET_MESSAGES: dict[str, str] = {
    "execution_budget_exceeded": "The workflow reached its model-call budget.",
    "token_budget_exceeded": "The workflow reached its token budget.",
}


@dataclass(slots=True)
class WorkflowContext:
    provider: LLMProvider
    settings: Settings
    report: ProgressReporter
    max_llm_calls: int
    max_total_tokens: int
    max_verifier_retries: int

    async def report_step(
        self, step: str, progress: int, message: str | None = None
    ) -> None:
        await self.report(step, progress, message)

    def budget_exceeded_code(self, state: CaseAnalysisState) -> str | None:
        """Return the error code for the first exceeded budget, or None.

        Call this at the start of any node that makes an LLM call. Stage 6
        nodes reuse this without reimplementing the budget logic.
        """
        calls = int(state.get("llm_calls", 0))
        if calls >= self.max_llm_calls:
            return "execution_budget_exceeded"
        usage = state.get("token_usage") or {}
        if int(usage.get("total", 0)) >= self.max_total_tokens:
            return "token_budget_exceeded"
        return None

    def budget_exceeded_state(self, code: str) -> dict:
        """Build a terminal failure state dict for a budget error code."""
        return {
            "status": "failed",
            "current_step": code,
            "progress": 100,
            "outcome": code,
            "errors": [{"code": code, "message": _BUDGET_MESSAGES[code]}],
        }
