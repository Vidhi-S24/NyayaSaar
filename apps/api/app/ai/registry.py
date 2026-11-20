"""AI provider selection.

Provider and model selection is entirely configuration-driven. Agent nodes
never see these details; they only receive an ``LLMProvider``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.ai.base import LLMProvider, ProviderNotConfiguredError
from app.ai.providers.anthropic import AnthropicProvider
from app.ai.providers.gemini import GeminiProvider
from app.ai.providers.mock import MockProvider
from app.ai.providers.openai_compatible import OpenAICompatibleProvider
from app.config import Settings

DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com",
}


@dataclass(slots=True)
class AIConfig:
    requested_provider: str
    provider: str
    model: str
    base_url: str
    is_mock: bool
    configured: bool
    message: str
    api_key: str = field(default="", repr=False)


def resolve_ai_config(settings: Settings) -> AIConfig:
    """Resolve environment settings into an effective provider configuration."""
    requested = settings.ai_provider
    model = settings.effective_ai_model
    api_key = settings.effective_ai_api_key
    base_url = settings.ai_base_url or DEFAULT_BASE_URLS.get(requested, "")

    if requested == "mock":
        if settings.is_production and not settings.ai_mock_allowed:
            return AIConfig(
                requested_provider=requested,
                provider="mock",
                model=model or "fixture",
                base_url="",
                is_mock=True,
                configured=False,
                message=(
                    "Fixture mode is disabled in production. Configure a real "
                    "provider or set AI_ALLOW_MOCK=true for a deliberately "
                    "labelled non-production deployment."
                ),
            )
        return AIConfig(
            requested_provider=requested,
            provider="mock",
            model=model or "fixture",
            base_url="",
            is_mock=True,
            configured=True,
            message=(
                "Development fixture mode is active. No AI model is called and "
                "the output is not real AI analysis."
            ),
        )

    if settings.ai_configured:
        return AIConfig(
            requested_provider=requested,
            provider=requested,
            model=model,
            base_url=base_url,
            is_mock=False,
            configured=True,
            message="AI provider configured.",
            api_key=api_key,
        )

    if settings.ai_mock_allowed:
        return AIConfig(
            requested_provider=requested,
            provider="mock",
            model="fixture",
            base_url="",
            is_mock=True,
            configured=True,
            message=(
                "No AI credentials are configured. Using a clearly-labelled "
                "development fixture; no AI model is called. Set AI_PROVIDER, "
                "AI_MODEL, and AI_API_KEY for real analysis."
            ),
        )

    return AIConfig(
        requested_provider=requested,
        provider=requested,
        model=model,
        base_url=base_url,
        is_mock=False,
        configured=False,
        message=(
            "No AI provider is configured. Set AI_PROVIDER, AI_MODEL, and "
            "AI_API_KEY on the server."
        ),
    )


def get_provider(settings: Settings) -> LLMProvider:
    """Construct the configured provider adapter.

    Raises:
        ProviderNotConfiguredError: when no real provider is configured and
            the development fixture is not allowed (for example, in production).
    """
    cfg = resolve_ai_config(settings)
    if not cfg.configured:
        raise ProviderNotConfiguredError(cfg.message)

    retry_options = {
        "max_retries": settings.ai_max_retries,
        "structured_retries": settings.ai_structured_retries,
    }

    if cfg.is_mock:
        return MockProvider(model=cfg.model)

    if cfg.provider == "gemini":
        return GeminiProvider(
            api_key=cfg.api_key,
            model=cfg.model,
            max_retries=settings.ai_max_retries,
            structured_retries=settings.ai_structured_retries,
            native_schema=settings.ai_gemini_native_schema,
        )

    if cfg.provider in ("openai", "openai_compatible"):
        return OpenAICompatibleProvider(
            api_key=cfg.api_key,
            model=cfg.model,
            base_url=cfg.base_url,
            json_mode=settings.ai_json_mode,
            provider_name=cfg.provider,
            **retry_options,
        )

    if cfg.provider == "anthropic":
        return AnthropicProvider(
            api_key=cfg.api_key,
            model=cfg.model,
            base_url=cfg.base_url,
            **retry_options,
        )

    raise ProviderNotConfiguredError(
        f"Unsupported AI provider '{cfg.provider}'."
    )


def get_ai_status(settings: Settings) -> dict[str, object]:
    """Safe status payload for the frontend. Never includes the API key."""
    cfg = resolve_ai_config(settings)
    return {
        "provider": cfg.provider,
        "requested_provider": cfg.requested_provider,
        "model": cfg.model,
        "is_mock": cfg.is_mock,
        "configured": cfg.configured,
        "message": cfg.message,
    }
