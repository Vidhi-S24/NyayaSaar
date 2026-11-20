"""Provider-agnostic LLM interface.

Design goals
------------
* Agent nodes never import a vendor SDK. They call ``generate_structured``.
* Provider/model changes are environment-only changes.
* Structured output is validated by Pydantic before it reaches an agent.
* Transport retries, timeouts, and repair attempts are bounded.
* Errors are sanitised: prompts, document text, and API keys are never logged.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger("nyayasaar.ai")

TModel = TypeVar("TModel", bound=BaseModel)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ProviderError(Exception):
    """Base class for safe, user-presentable provider errors."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "provider_error",
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.retryable = retryable


class ProviderTimeoutError(ProviderError):
    def __init__(self, message: str = "The AI provider timed out.") -> None:
        super().__init__(message, code="provider_timeout", retryable=True)


class ProviderResponseError(ProviderError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "invalid_model_output",
        retryable: bool = False,
    ) -> None:
        super().__init__(message, code=code, retryable=retryable)


class ProviderNotConfiguredError(ProviderError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="provider_not_configured", retryable=False)


# ---------------------------------------------------------------------------
# Request / response value objects
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class StructuredRequest:
    """A single structured-generation request.

    ``mock_fixture`` is only consumed by the development fixture provider. It
    lets the graph exercise real source IDs and page references without making
    a network call. Real providers ignore it.
    """

    system_prompt: str
    user_prompt: str
    output_schema: type[BaseModel]
    temperature: float = 0.2
    max_output_tokens: int = 4096
    timeout_s: float = 45.0
    mock_fixture: dict[str, Any] | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class RawCompletion:
    """Provider text plus optional token accounting."""

    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(slots=True)
class LLMResult:
    """Validated structured output returned to an agent node."""

    output: BaseModel
    provider: str
    model: str
    is_mock: bool
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int
    attempts: int


# ---------------------------------------------------------------------------
# Provider base class
# ---------------------------------------------------------------------------


class LLMProvider(ABC):
    """Base adapter. Subclasses implement one vendor-specific call."""

    name: str = "unknown"
    is_mock: bool = False

    def __init__(
        self,
        *,
        model: str,
        max_retries: int = 2,
        structured_retries: int = 1,
        backoff_base_s: float = 0.5,
    ) -> None:
        if not model:
            raise ValueError("A model identifier is required.")
        self.model = model
        self.max_retries = max(0, max_retries)
        self.structured_retries = max(0, structured_retries)
        self.backoff_base_s = max(0.0, backoff_base_s)

    # -- public API ---------------------------------------------------------

    async def generate_structured(self, request: StructuredRequest) -> LLMResult:
        """Generate and validate structured output with bounded retries."""
        if not isinstance(request.output_schema, type) or not issubclass(
            request.output_schema, BaseModel
        ):
            raise TypeError("output_schema must be a Pydantic BaseModel subclass.")
        if request.timeout_s <= 0:
            raise ValueError("timeout_s must be positive.")

        started = time.perf_counter()
        attempts = 0
        repair_note = ""

        for _structure_attempt in range(self.structured_retries + 1):
            current = request
            if repair_note:
                current = replace(
                    request,
                    user_prompt=request.user_prompt + repair_note,
                )

            raw, call_attempts = await self._call_with_retries(current)
            attempts += call_attempts

            try:
                output = self._parse_output(raw.text, request.output_schema)
            except (ValueError, ValidationError):
                # Do not include the raw output in logs or errors: it may
                # contain sensitive document-derived text.
                repair_note = (
                    "\n\nIMPORTANT: Your previous response was not valid JSON for the "
                    "required schema. Return only a single JSON object that matches the "
                    "schema. Do not include markdown fences or commentary."
                )
                logger.warning(
                    "Structured output rejected provider=%s model=%s",
                    self.name,
                    self.model,
                )
                continue

            latency_ms = int((time.perf_counter() - started) * 1000)
            return LLMResult(
                output=output,
                provider=self.name,
                model=self.model,
                is_mock=self.is_mock,
                input_tokens=raw.input_tokens,
                output_tokens=raw.output_tokens,
                latency_ms=latency_ms,
                attempts=attempts,
            )

        raise ProviderResponseError(
            "The model did not return output matching the required schema.",
            code="invalid_model_output",
        )

    # -- internals ----------------------------------------------------------

    async def _call_with_retries(
        self, request: StructuredRequest
    ) -> tuple[RawCompletion, int]:
        last_error: ProviderError | None = None
        total_attempts = self.max_retries + 1

        for attempt in range(1, total_attempts + 1):
            try:
                raw = await asyncio.wait_for(
                    self._generate_text(request),
                    timeout=request.timeout_s,
                )
                return raw, attempt
            except TimeoutError:
                last_error = ProviderTimeoutError()
            except ProviderError as exc:
                if not exc.retryable:
                    raise
                last_error = exc
            except Exception as exc:  # pragma: no cover - defensive
                # Never surface vendor exception text (it can include request
                # URLs, headers, or document excerpts).
                logger.warning(
                    "Provider call failed provider=%s model=%s type=%s",
                    self.name,
                    self.model,
                    type(exc).__name__,
                )
                last_error = ProviderError(
                    "The AI provider request failed.",
                    code="provider_error",
                    retryable=True,
                )

            if attempt < total_attempts:
                delay = min(self.backoff_base_s * (2 ** (attempt - 1)), 4.0)
                if delay:
                    await asyncio.sleep(delay)

        assert last_error is not None
        raise last_error

    @staticmethod
    def _parse_output(text: str, schema: type[TModel]) -> TModel:
        if not text or not text.strip():
            raise ValueError("empty response")
        cleaned = text.strip()

        # Tolerate markdown fences even when a provider ignores JSON mode.
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("no JSON object found")
        candidate = cleaned[start : end + 1]
        return schema.model_validate_json(candidate)

    @abstractmethod
    async def _generate_text(self, request: StructuredRequest) -> RawCompletion:
        """Perform one vendor call and return raw JSON text."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Helpers shared by adapters
# ---------------------------------------------------------------------------


def schema_json(schema: type[BaseModel]) -> str:
    """Compact JSON schema for inclusion in prompts."""
    return json.dumps(schema.model_json_schema(), ensure_ascii=False, separators=(",", ":"))


def estimate_tokens(text: str) -> int:
    """Rough fallback when a provider omits usage metadata."""
    return max(1, len(text) // 4)
