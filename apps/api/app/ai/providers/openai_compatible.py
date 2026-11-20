"""OpenAI-compatible Chat Completions adapter.

Works with OpenAI, Azure OpenAI-compatible gateways, Groq, OpenRouter,
Together, DeepSeek, Mistral, local Ollama/LM Studio, and any other service
that implements ``POST /chat/completions``.

Only the base URL, API key, model, and optional JSON mode need to change.
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


class OpenAICompatibleProvider(LLMProvider):
    name = "openai_compatible"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        json_mode: str = "json_object",
        max_retries: int = 2,
        structured_retries: int = 1,
        http_client: httpx.AsyncClient | None = None,
        provider_name: str = "openai_compatible",
    ) -> None:
        super().__init__(
            model=model,
            max_retries=max_retries,
            structured_retries=structured_retries,
        )
        self.name = provider_name
        if not base_url:
            raise ProviderNotConfiguredError(
                "An OpenAI-compatible provider is selected but AI_BASE_URL is empty."
            )
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.json_mode = json_mode
        self._http_client = http_client

    async def _generate_text(self, request: StructuredRequest) -> RawCompletion:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens,
        }
        if self.json_mode == "json_object":
            payload["response_format"] = {"type": "json_object"}
        elif self.json_mode == "json_schema":
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": request.output_schema.__name__,
                    "schema": request.output_schema.model_json_schema(),
                    "strict": True,
                },
            }

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        url = f"{self.base_url}/chat/completions"
        timeout = httpx.Timeout(request.timeout_s, connect=min(10.0, request.timeout_s))

        try:
            if self._http_client is not None:
                response = await self._http_client.post(
                    url, json=payload, headers=headers
                )
            else:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                "The AI provider request timed out."
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderError(
                "Could not reach the AI provider.",
                code="provider_unavailable",
                retryable=True,
            ) from exc

        if response.status_code >= 400:
            raise self._map_status(response.status_code)

        try:
            body = response.json()
        except ValueError as exc:
            raise ProviderResponseError(
                "The AI provider returned a non-JSON response.",
                code="provider_bad_response",
            ) from exc

        try:
            choice = body["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderResponseError(
                "The AI provider response did not contain a message.",
                code="provider_bad_response",
            ) from exc

        if isinstance(content, list):
            text = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        else:
            text = str(content or "")

        if not text.strip():
            raise ProviderResponseError(
                "The AI model returned an empty response.",
                code="empty_response",
            )

        usage = body.get("usage") or {}
        return RawCompletion(
            text=text,
            input_tokens=_int_or_none(usage.get("prompt_tokens")),
            output_tokens=_int_or_none(usage.get("completion_tokens")),
        )

    @staticmethod
    def _map_status(status_code: int) -> ProviderError:
        if status_code in (401, 403):
            return ProviderError(
                "The AI provider rejected the API key.",
                code="provider_auth_error",
                retryable=False,
            )
        if status_code == 429:
            return ProviderError(
                "The AI provider rate limit was reached. Please retry shortly.",
                code="provider_rate_limited",
                retryable=True,
            )
        if status_code in (408, 504):
            return ProviderTimeoutError("The AI provider timed out.")
        if status_code >= 500:
            return ProviderError(
                "The AI provider is temporarily unavailable.",
                code="provider_unavailable",
                retryable=True,
            )
        if status_code == 400:
            return ProviderError(
                "The AI provider rejected the request. Check the configured model "
                "and structured-output mode.",
                code="provider_bad_request",
                retryable=False,
            )
        return ProviderError(
            "The AI provider request failed.",
            code="provider_error",
            retryable=False,
        )


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
