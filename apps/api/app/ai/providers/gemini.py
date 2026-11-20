"""Google Gemini adapter using the official Google Gen AI SDK.

The SDK is imported lazily so the API still starts when the optional AI
dependency is missing (for example, in a constrained development image).
"""

from __future__ import annotations

import logging
from typing import Any

from app.ai.base import (
    LLMProvider,
    ProviderError,
    ProviderNotConfiguredError,
    ProviderResponseError,
    ProviderTimeoutError,
    RawCompletion,
    StructuredRequest,
)

logger = logging.getLogger("nyayasaar.ai.gemini")


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        max_retries: int = 2,
        structured_retries: int = 1,
        native_schema: bool = True,
        client: Any | None = None,
    ) -> None:
        super().__init__(
            model=model,
            max_retries=max_retries,
            structured_retries=structured_retries,
        )
        if not api_key and client is None:
            raise ProviderNotConfiguredError(
                "Gemini is selected but no API key is configured. "
                "Set AI_API_KEY (or GEMINI_API_KEY) on the server."
            )
        self.native_schema = native_schema

        if client is not None:
            self._client = client
            self._types = None
            return

        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise ProviderNotConfiguredError(
                "The google-genai package is not installed. "
                "Install apps/api/requirements.txt."
            ) from exc

        self._client = genai.Client(api_key=api_key)
        self._types = types

    async def _generate_text(self, request: StructuredRequest) -> RawCompletion:
        assert self._types is not None or self._client is not None

        config_kwargs: dict[str, Any] = {
            "system_instruction": request.system_prompt,
            "temperature": request.temperature,
            "max_output_tokens": request.max_output_tokens,
            "response_mime_type": "application/json",
        }
        if self.native_schema and self._types is not None:
            config_kwargs["response_schema"] = request.output_schema

        try:
            if self._types is not None:
                config = self._types.GenerateContentConfig(**config_kwargs)
            else:  # injected test client receives plain kwargs
                config = config_kwargs

            response = await self._client.aio.models.generate_content(
                model=self.model,
                contents=request.user_prompt,
                config=config,
            )
        except Exception as exc:
            raise self._map_error(exc) from exc

        text = getattr(response, "text", None)
        if not text or not str(text).strip():
            raise ProviderResponseError(
                "The AI model returned no usable text. It may have been blocked "
                "by a safety filter or the selected model may not support this task.",
                code="empty_response",
            )

        usage = getattr(response, "usage_metadata", None)
        input_tokens = _int_or_none(getattr(usage, "prompt_token_count", None))
        output_tokens = _int_or_none(getattr(usage, "candidates_token_count", None))
        return RawCompletion(
            text=str(text),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    @staticmethod
    def _map_error(exc: Exception) -> ProviderError:
        # Inspect only status codes / short markers; never echo the full
        # vendor message (it can include request content).
        raw = str(exc).lower()
        status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
        status_text = str(status).lower() if status is not None else ""

        if "deadline" in raw or "timeout" in raw or "timed out" in raw:
            return ProviderTimeoutError("The Gemini request timed out.")
        if "429" in raw or "resource_exhausted" in raw or "rate limit" in raw:
            return ProviderError(
                "The Gemini API rate limit was reached. Please retry shortly.",
                code="provider_rate_limited",
                retryable=True,
            )
        if (
            "401" in raw
            or "403" in raw
            or "api key" in raw
            or "permission" in raw
            or "unauthenticated" in raw
        ):
            return ProviderError(
                "Gemini authentication failed. Check the server-side API key.",
                code="provider_auth_error",
                retryable=False,
            )
        if "500" in raw or "502" in raw or "503" in raw or "504" in raw:
            return ProviderError(
                "The Gemini service is temporarily unavailable.",
                code="provider_unavailable",
                retryable=True,
            )
        if "400" in status_text or "invalid" in raw:
            return ProviderError(
                "The Gemini request was rejected. Check the configured model ID.",
                code="provider_bad_request",
                retryable=False,
            )
        return ProviderError(
            "The Gemini request failed.",
            code="provider_error",
            retryable=False,
        )


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
