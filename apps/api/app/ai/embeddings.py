"""Configurable embedding provider abstraction (Stage 7).

Keeps vector dimensions consistent with the pgvector / SQLite storage index.
Supports:
  - ``hashing``: deterministic offline feature-hashing embeddings (no network/key)
  - ``gemini``: Google Gemini API via the official ``google-genai`` SDK
  - ``openai`` / ``openai_compatible``: OpenAI-compatible embeddings endpoint
  - ``none``: embeddings disabled (lexical-only retrieval)

Provider keys stay strictly server-side and are never logged or returned.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from app.ai.base import ProviderError, ProviderNotConfiguredError
from app.config import Settings

logger = logging.getLogger("nyayasaar.ai.embeddings")

_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    vectors: list[list[float]]
    provider: str
    model: str
    dimensions: int
    is_mock: bool = False


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Exact cosine similarity for two equal-length vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0
    return max(-1.0, min(1.0, dot / (norm_a * norm_b)))


def _l2_normalise(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm <= 0.0:
        return vec
    return [x / norm for x in vec]


class EmbeddingProvider(ABC):
    """Abstract embedding provider interface."""

    name: str
    model: str
    dimensions: int
    is_mock: bool = False

    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        """Generate fixed-dimension embeddings for ``texts``."""

    async def embed_query(self, query: str) -> list[float]:
        result = await self.embed_texts([query])
        return result.vectors[0] if result.vectors else []

    def _validate_dimensions(self, vectors: list[list[float]]) -> None:
        for vec in vectors:
            if len(vec) != self.dimensions:
                raise ProviderError(
                    code="embedding_dimension_mismatch",
                    message=(
                        f"Embedding provider returned {len(vec)} dimensions, "
                        f"expected {self.dimensions} to match the vector index."
                    ),
                    retryable=False,
                )


class HashingEmbeddingProvider(EmbeddingProvider):
    """Deterministic local feature-hashing embeddings (no network or API key).

    Maps unigrams and bigrams into a fixed-size signed vector using Blake2b
    hashing, then L2-normalises. Useful for offline development, CI, and as a
    reproducible fallback when no external embedding API is configured.
    """

    name = "hashing"
    is_mock = False

    def __init__(self, *, dimensions: int = 256) -> None:
        self.dimensions = dimensions
        self.model = f"hashing-{dimensions}"

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dimensions
        tokens = _TOKEN_RE.findall((text or "").casefold())
        if not tokens:
            return vec
        features = list(tokens) + [
            f"{tokens[i]}_{tokens[i + 1]}" for i in range(len(tokens) - 1)
        ]
        for feat in features:
            digest = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if (digest[4] & 1) == 0 else -1.0
            vec[idx] += sign
        return _l2_normalise(vec)

    async def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        vectors = [self._embed_one(t) for t in texts]
        self._validate_dimensions(vectors)
        return EmbeddingResult(
            vectors=vectors,
            provider=self.name,
            model=self.model,
            dimensions=self.dimensions,
            is_mock=False,
        )


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Google Gemini embeddings via the official ``google-genai`` SDK."""

    name = "gemini"
    is_mock = False

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gemini-embedding-001",
        dimensions: int = 256,
        timeout_s: float = 20.0,
    ) -> None:
        if not api_key:
            raise ProviderNotConfiguredError(
                "Gemini embedding provider requires an API key."
            )
        self._api_key = api_key
        self.model = model or "gemini-embedding-001"
        self.dimensions = dimensions
        self._timeout_s = timeout_s

    async def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        if not texts:
            return EmbeddingResult([], self.name, self.model, self.dimensions)

        def _call() -> list[list[float]]:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self._api_key)
            resp = client.models.embed_content(
                model=self.model,
                contents=texts,
                config=types.EmbedContentConfig(
                    output_dimensionality=self.dimensions
                ),
            )
            embeddings = getattr(resp, "embeddings", None) or []
            return [list(e.values) for e in embeddings]

        try:
            vectors = await asyncio.wait_for(
                asyncio.to_thread(_call), timeout=self._timeout_s
            )
        except TimeoutError as exc:
            raise ProviderError(
                code="embedding_timeout",
                message="The embedding request timed out.",
                retryable=True,
            ) from exc
        except ProviderError:
            raise
        except Exception as exc:
            logger.warning("Gemini embedding call failed type=%s", type(exc).__name__)
            raise ProviderError(
                code="embedding_provider_error",
                message="The configured embedding provider returned an error.",
                retryable=True,
            ) from exc

        self._validate_dimensions(vectors)
        return EmbeddingResult(
            vectors=vectors,
            provider=self.name,
            model=self.model,
            dimensions=self.dimensions,
        )


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    """OpenAI or OpenAI-compatible ``/embeddings`` HTTP endpoint."""

    is_mock = False

    def __init__(
        self,
        *,
        name: str,
        api_key: str,
        base_url: str,
        model: str,
        dimensions: int = 256,
        timeout_s: float = 20.0,
    ) -> None:
        if name == "openai" and not api_key:
            raise ProviderNotConfiguredError(
                "OpenAI embedding provider requires an API key."
            )
        if not base_url:
            raise ProviderNotConfiguredError(
                "Embedding base URL is required for openai_compatible."
            )
        self.name = name
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self.model = model or "text-embedding-3-small"
        self.dimensions = dimensions
        self._timeout_s = timeout_s

    async def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        if not texts:
            return EmbeddingResult([], self.name, self.model, self.dimensions)
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        payload = {
            "model": self.model,
            "input": texts,
            "dimensions": self.dimensions,
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                resp = await client.post(
                    f"{self._base_url}/embeddings",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.TimeoutException as exc:
            raise ProviderError(
                code="embedding_timeout",
                message="The embedding request timed out.",
                retryable=True,
            ) from exc
        except Exception as exc:
            logger.warning("HTTP embedding call failed type=%s", type(exc).__name__)
            raise ProviderError(
                code="embedding_provider_error",
                message="The configured embedding provider returned an error.",
                retryable=True,
            ) from exc

        items = sorted(data.get("data") or [], key=lambda item: item.get("index", 0))
        vectors = [list(item.get("embedding") or []) for item in items]
        self._validate_dimensions(vectors)
        return EmbeddingResult(
            vectors=vectors,
            provider=self.name,
            model=self.model,
            dimensions=self.dimensions,
        )


def get_embedding_provider(settings: Settings) -> EmbeddingProvider | None:
    """Build the configured embedding provider, or ``None`` if disabled."""
    if not settings.retrieval_embeddings_enabled:
        return None
    name = (settings.embedding_provider or "hashing").strip().lower()
    dim = settings.retrieval_embedding_dim
    if name == "none":
        return None
    if name == "hashing":
        return HashingEmbeddingProvider(dimensions=dim)
    if name == "gemini":
        key = settings.embedding_api_key or settings.effective_ai_api_key
        return GeminiEmbeddingProvider(
            api_key=key,
            model=settings.embedding_model or "gemini-embedding-001",
            dimensions=dim,
            timeout_s=settings.embedding_timeout_s,
        )
    if name in ("openai", "openai_compatible"):
        key = settings.embedding_api_key or settings.effective_ai_api_key
        base_url = settings.embedding_base_url or (
            "https://api.openai.com/v1" if name == "openai" else ""
        )
        return OpenAICompatibleEmbeddingProvider(
            name=name,
            api_key=key,
            base_url=base_url,
            model=settings.embedding_model or "text-embedding-3-small",
            dimensions=dim,
            timeout_s=settings.embedding_timeout_s,
        )
    raise ProviderNotConfiguredError(
        f"Unknown embedding provider '{settings.embedding_provider}'."
    )
