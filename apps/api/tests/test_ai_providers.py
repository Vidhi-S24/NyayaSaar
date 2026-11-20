"""Provider-layer tests.

No real AI service is called. Gemini uses an injected fake client, and the
OpenAI-compatible/Anthropic adapters use ``httpx.MockTransport``.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from pydantic import BaseModel

from app.ai.base import (
    LLMProvider,
    ProviderError,
    ProviderResponseError,
    ProviderTimeoutError,
    RawCompletion,
    StructuredRequest,
)
from app.ai.providers.anthropic import AnthropicProvider
from app.ai.providers.gemini import GeminiProvider
from app.ai.providers.mock import MockProvider
from app.ai.providers.openai_compatible import OpenAICompatibleProvider
from app.ai.registry import get_ai_status, get_provider, resolve_ai_config
from app.config import Settings


class Out(BaseModel):
    summary: str


def make_request(**overrides) -> StructuredRequest:
    base = dict(
        system_prompt="system",
        user_prompt="user",
        output_schema=Out,
        timeout_s=1.0,
        max_output_tokens=256,
        mock_fixture={"summary": "fixture summary"},
    )
    base.update(overrides)
    return StructuredRequest(**base)


class ScriptedProvider(LLMProvider):
    """Provider that returns queued raw strings or raises queued errors."""

    name = "scripted"

    def __init__(self, script, **kwargs):
        super().__init__(model="scripted-1", **kwargs)
        self.script = list(script)
        self.calls = 0

    async def _generate_text(self, request):
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return RawCompletion(text=item)


# ---------------------------------------------------------------------------
# Base behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mock_provider_returns_fixture_and_is_labelled():
    provider = MockProvider()
    result = await provider.generate_structured(make_request())
    assert provider.is_mock is True
    assert result.is_mock is True
    assert result.output.summary == "fixture summary"
    assert result.provider == "mock"


@pytest.mark.asyncio
async def test_mock_provider_requires_fixture():
    provider = MockProvider()
    with pytest.raises(ProviderResponseError) as exc:
        await provider.generate_structured(make_request(mock_fixture=None))
    assert exc.value.code == "mock_fixture_missing"


@pytest.mark.asyncio
async def test_valid_json_is_parsed_even_with_markdown_fence():
    provider = ScriptedProvider(['```json\n{"summary": "fenced"}\n```'], structured_retries=0)
    result = await provider.generate_structured(make_request())
    assert result.output.summary == "fenced"
    assert result.attempts == 1


@pytest.mark.asyncio
async def test_invalid_output_is_repaired_once_then_succeeds():
    provider = ScriptedProvider(
        ["not json", json.dumps({"summary": "repaired"})],
        structured_retries=1,
    )
    result = await provider.generate_structured(make_request())
    assert result.output.summary == "repaired"
    assert provider.calls == 2


@pytest.mark.asyncio
async def test_invalid_output_exhausts_repair_attempts():
    provider = ScriptedProvider(
        ["not json", "still not json"], structured_retries=1
    )
    with pytest.raises(ProviderResponseError) as exc:
        await provider.generate_structured(make_request())
    assert exc.value.code == "invalid_model_output"


@pytest.mark.asyncio
async def test_retryable_provider_error_is_retried():
    provider = ScriptedProvider(
        [
            ProviderError("temporary", code="provider_unavailable", retryable=True),
            json.dumps({"summary": "ok"}),
        ],
        max_retries=1,
        structured_retries=0,
    )
    provider.backoff_base_s = 0
    result = await provider.generate_structured(make_request())
    assert result.output.summary == "ok"
    assert provider.calls == 2


@pytest.mark.asyncio
async def test_non_retryable_provider_error_is_not_retried():
    provider = ScriptedProvider(
        [ProviderError("bad key", code="provider_auth_error", retryable=False)],
        max_retries=3,
        structured_retries=0,
    )
    with pytest.raises(ProviderError) as exc:
        await provider.generate_structured(make_request())
    assert exc.value.code == "provider_auth_error"
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_timeout_is_bounded_and_retried():
    class SlowProvider(LLMProvider):
        name = "slow"

        def __init__(self):
            super().__init__(model="slow-1", max_retries=1, structured_retries=0)
            self.calls = 0

        async def _generate_text(self, request):
            self.calls += 1
            await asyncio.sleep(1)
            return RawCompletion(text='{"summary": "late"}')

    provider = SlowProvider()
    with pytest.raises(ProviderTimeoutError):
        await provider.generate_structured(make_request(timeout_s=0.01))
    assert provider.calls == 2


# ---------------------------------------------------------------------------
# OpenAI-compatible adapter
# ---------------------------------------------------------------------------


def openai_body(content: str) -> dict:
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 7},
    }


@pytest.mark.asyncio
async def test_openai_compatible_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        assert request.headers["authorization"] == "Bearer test-key"
        payload = json.loads(request.content)
        assert payload["model"] == "gpt-test"
        return httpx.Response(200, json=openai_body('{"summary": "hello"}'))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(
        api_key="test-key",
        model="gpt-test",
        base_url="https://example.test/v1",
        http_client=client,
    )
    result = await provider.generate_structured(make_request())
    assert result.output.summary == "hello"
    assert result.input_tokens == 12
    assert result.output_tokens == 7


@pytest.mark.asyncio
async def test_openai_compatible_429_is_retried():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(200, json=openai_body('{"summary": "after retry"}'))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(
        api_key="test-key",
        model="gpt-test",
        base_url="https://example.test/v1",
        max_retries=1,
        structured_retries=0,
        http_client=client,
    )
    provider.backoff_base_s = 0
    result = await provider.generate_structured(make_request())
    assert result.output.summary == "after retry"
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_openai_compatible_401_is_not_retried():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(401, json={"error": "bad key"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(
        api_key="test-key",
        model="gpt-test",
        base_url="https://example.test/v1",
        max_retries=3,
        structured_retries=0,
        http_client=client,
    )
    with pytest.raises(ProviderError) as exc:
        await provider.generate_structured(make_request())
    assert exc.value.code == "provider_auth_error"
    assert calls["n"] == 1


# ---------------------------------------------------------------------------
# Anthropic adapter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_anthropic_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/messages"
        assert request.headers["x-api-key"] == "anthropic-key"
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": '{"summary": "claude"}'}],
                "usage": {"input_tokens": 5, "output_tokens": 4},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = AnthropicProvider(
        api_key="anthropic-key", model="claude-test", http_client=client
    )
    result = await provider.generate_structured(make_request())
    assert result.output.summary == "claude"
    assert result.provider == "anthropic"


# ---------------------------------------------------------------------------
# Gemini adapter (fake SDK client — no network)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gemini_success_with_fake_client():
    class FakeResponse:
        text = '{"summary": "gemini"}'
        usage_metadata = type(
            "Usage", (), {"prompt_token_count": 9, "candidates_token_count": 3}
        )()

    class FakeModels:
        async def generate_content(self, **kwargs):
            assert kwargs["model"] == "gemini-test"
            assert "response_schema" not in kwargs["config"]
            return FakeResponse()

    class FakeClient:
        aio = type("Aio", (), {"models": FakeModels()})()

    provider = GeminiProvider(
        api_key="", model="gemini-test", client=FakeClient()
    )
    result = await provider.generate_structured(make_request())
    assert result.output.summary == "gemini"
    assert result.provider == "gemini"
    assert result.input_tokens == 9


@pytest.mark.asyncio
async def test_gemini_empty_response_is_reported():
    class FakeResponse:
        text = ""
        usage_metadata = None

    class FakeModels:
        async def generate_content(self, **kwargs):
            return FakeResponse()

    class FakeClient:
        aio = type("Aio", (), {"models": FakeModels()})()

    provider = GeminiProvider(api_key="", model="gemini-test", client=FakeClient())
    with pytest.raises(ProviderResponseError) as exc:
        await provider.generate_structured(make_request())
    assert exc.value.code == "empty_response"


# ---------------------------------------------------------------------------
# Registry / status
# ---------------------------------------------------------------------------


def test_registry_selects_mock_when_no_key_outside_production():
    settings = Settings(ai_provider="gemini", ai_api_key="", gemini_api_key="")
    cfg = resolve_ai_config(settings)
    assert cfg.is_mock is True
    assert cfg.configured is True
    assert "fixture" in cfg.message.lower()
    assert isinstance(get_provider(settings), MockProvider)


def test_registry_uses_configured_gemini_key():
    settings = Settings(
        ai_provider="gemini",
        ai_api_key="secret-key",
        ai_model="gemini-custom",
    )
    cfg = resolve_ai_config(settings)
    assert cfg.is_mock is False
    assert cfg.provider == "gemini"
    assert cfg.model == "gemini-custom"
    provider = get_provider(settings)
    assert isinstance(provider, GeminiProvider)
    assert provider.model == "gemini-custom"


def test_registry_supports_openai_compatible_base_url_without_key():
    settings = Settings(
        ai_provider="openai_compatible",
        ai_base_url="http://localhost:11434/v1",
        ai_model="llama3.1",
        ai_allow_mock=False,
    )
    cfg = resolve_ai_config(settings)
    assert cfg.configured is True
    assert cfg.is_mock is False
    provider = get_provider(settings)
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.name == "openai_compatible"


def test_ai_status_never_contains_api_key():
    settings = Settings(
        ai_provider="gemini", ai_api_key="super-secret", ai_model="gemini-custom"
    )
    payload = get_ai_status(settings)
    assert payload["provider"] == "gemini"
    assert payload["model"] == "gemini-custom"
    assert "super-secret" not in json.dumps(payload)
    assert "api_key" not in payload


def test_production_without_key_is_not_configured():
    settings = Settings(
        app_env="production",
        ai_provider="gemini",
        ai_api_key="",
        gemini_api_key="",
        ai_allow_mock=False,
    )
    cfg = resolve_ai_config(settings)
    assert cfg.configured is False
    assert cfg.is_mock is False
    with pytest.raises(ProviderError):
        get_provider(settings)


def test_explicit_mock_is_blocked_in_production_by_default():
    settings = Settings(
        app_env="production", ai_provider="mock", ai_allow_mock=False
    )
    cfg = resolve_ai_config(settings)
    assert cfg.is_mock is True
    assert cfg.configured is False
    with pytest.raises(ProviderError):
        get_provider(settings)


def test_explicit_mock_can_be_allowed_in_production():
    settings = Settings(
        app_env="production", ai_provider="mock", ai_allow_mock=True
    )
    cfg = resolve_ai_config(settings)
    assert cfg.is_mock is True
    assert cfg.configured is True
    assert isinstance(get_provider(settings), MockProvider)
