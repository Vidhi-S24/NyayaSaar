"""Anthropic Messages API adapter.

Uses a plain HTTPS call so the platform does not need a second vendor SDK.
Switching to Anthropic is an environment-only change.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.ai.base import (
    LLMProvider,
    ProviderError,
    ProviderNotConfiguredError,
    ProviderResponseError,
    ProviderTimeoutError,
    RawCompletion,
    StructuredRequest,
)

ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.anthropic.com",
        max_retries: int = 2,
        structured_retries: int = 1,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(
            model=model,
            max_retries=max_retries,
            structured_retries=structured_retries,
        )
        if not api_key:
            raise ProviderNotConfiguredError(
                "Anthropic is selected but no API key is configured. "
                "Set AI_API_KEY on the server."
            )
        self.api_key = api_key
        base = (base_url or "https://api.anthropic.com").rstrip("/")
        self.messages_url = (
            f"{base}/messages" if base.endswith("/v1") else f"{base}/v1/messages"
        )
        self._http_client = http_client

    async def _generate_text(self, request: StructuredRequest) -> RawCompletion:
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": request.max_output_tokens,
            "temperature": request.temperature,
            "system": request.system_prompt,
            "messages": [{"role": "user", "content": request.user_prompt}],
        }
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        }
        timeout = httpx.Timeout(request.timeout_s, connect=min(10.0, request.timeout_s))

        try:
            if self._http_client is not None:
                response = await self._http_client.post(
                    self.messages_url, json=payload, headers=headers
                )
            else:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        self.messages_url, json=payload, headers=headers
                    )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                "The Anthropic request timed out."
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderError(
                "Could not reach the Anthropic API.",
                code="provider_unavailable",
                retryable=True,
            ) from exc

        if response.status_code >= 400:
            raise self._map_status(response.status_code)

        try:
            body = response.json()
        except ValueError as exc:
            raise ProviderResponseError(
                "Anthropic returned a non-JSON response.",
                code="provider_bad_response",
            ) from exc

        content = body.get("content")
        if not isinstance(content, list):
            raise ProviderResponseError(
                "Anthropic returned an unexpected response shape.",
                code="provider_bad_response",
            )
        text = "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
        if not text.strip():
            raise ProviderResponseError(
                "Anthropic returned an empty response.",
                code="empty_response",
            )

        usage = body.get("usage") or {}
        return RawCompletion(
            text=text,
            input_tokens=_int_or_none(usage.get("input_tokens")),
            output_tokens=_int_or_none(usage.get("output_tokens")),
        )

    @staticmethod
    def _map_status(status_code: int) -> ProviderError:
        if status_code in (401, 403):
            return ProviderError(
                "Anthropic rejected the API key.",
                code="provider_auth_error",
                retryable=False,
            )
        if status_code == 429:
            return ProviderError(
                "The Anthropic rate limit was reached. Please retry shortly.",
                code="provider_rate_limited",
                retryable=True,
            )
        if status_code in (408, 504):
            return ProviderTimeoutError("The Anthropic request timed out.")
        if status_code >= 500:
            return ProviderError(
                "Anthropic is temporarily unavailable.",
                code="provider_unavailable",
                retryable=True,
            )
        if status_code == 400:
            return ProviderError(
                "Anthropic rejected the request. Check the configured model.",
                code="provider_bad_request",
                retryable=False,
            )
        return ProviderError(
            "The Anthropic request failed.",
            code="provider_error",
            retryable=False,
        )


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
