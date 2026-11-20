"""Provider-agnostic AI layer.

Agent nodes depend only on the :class:`LLMProvider` interface. Adding or
swapping a model/provider is an environment-variable change, not an
application-code change.
"""

from app.ai.base import (
    LLMProvider,
    LLMResult,
    ProviderError,
    ProviderNotConfiguredError,
    ProviderResponseError,
    ProviderTimeoutError,
    RawCompletion,
    StructuredRequest,
)
from app.ai.registry import get_ai_status, get_provider, resolve_ai_config

__all__ = [
    "LLMProvider",
    "LLMResult",
    "ProviderError",
    "ProviderNotConfiguredError",
    "ProviderResponseError",
    "ProviderTimeoutError",
    "RawCompletion",
    "StructuredRequest",
    "get_ai_status",
    "get_provider",
    "resolve_ai_config",
]
