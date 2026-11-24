"""
NyayaSaar API — Configuration

Uses pydantic-settings for type-safe environment variable loading.
All secrets live in environment variables; never hardcode or log them.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve apps/api/.env regardless of the process working directory. A relative
# ".env" only works when uvicorn is started from apps/api, which is a common
# source of "I added a key but the backend still uses the fixture" confusion.
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -----------------------------------------------------------------------
    # Application
    # -----------------------------------------------------------------------
    app_name: str = "NyayaSaar API"
    app_version: str = "0.1.0"
    app_env: Literal["development", "staging", "production"] = "development"
    app_secret_key: str = Field(
        default="INSECURE-dev-secret-replace-in-production",
        description="Used for signing tokens; must be changed in production.",
    )
    log_level: str = "INFO"

    # -----------------------------------------------------------------------
    # CORS
    # -----------------------------------------------------------------------
    cors_origins: list[str] = Field(
        default=["http://localhost:3000"],
        description="Comma-separated list of allowed frontend origins.",
    )
    cors_origin_regex: str = Field(
        default="",
        description=(
            "Optional regex of allowed frontend origins. In development, "
            "localhost/127.0.0.1 on any port is allowed by default."
        ),
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    # -----------------------------------------------------------------------
    # AI provider (server-side only, provider-agnostic)
    # -----------------------------------------------------------------------
    # AI_PROVIDER selects the adapter; AI_MODEL selects the model. Agent code
    # depends only on the LLMProvider interface, so switching providers/models
    # requires no application-code changes.
    ai_provider: Literal[
        "gemini", "openai", "openai_compatible", "anthropic", "mock"
    ] = Field(
        default="gemini",
        description=(
            "LLM adapter: gemini | openai | openai_compatible | anthropic | mock. "
            "Use openai_compatible for Groq, OpenRouter, Together, Ollama, etc."
        ),
    )
    ai_model: str = Field(
        default="",
        description=(
            "Model identifier for the selected provider. If empty, a provider "
            "default is used (or GEMINI_MODEL_ID for the Gemini adapter)."
        ),
    )
    ai_api_key: str = Field(
        default="",
        description="API key for the selected provider. Never exposed to clients.",
    )
    ai_base_url: str = Field(
        default="",
        description=(
            "Optional base URL. Required for openai_compatible providers; "
            "optional override for OpenAI/Anthropic-compatible gateways."
        ),
    )
    ai_timeout_s: float = Field(
        default=45.0,
        gt=0,
        description="Per-request provider timeout in seconds.",
    )
    ai_max_retries: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Transport-level retries for timeouts, 429s, and 5xx errors.",
    )
    ai_structured_retries: int = Field(
        default=1,
        ge=0,
        le=2,
        description="Repair attempts when the model returns invalid structured output.",
    )
    ai_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    ai_max_output_tokens: int = Field(default=4096, ge=256, le=32768)
    ai_json_mode: Literal["none", "json_object", "json_schema"] = Field(
        default="json_object",
        description=(
            "Structured-output mode for OpenAI-compatible providers. "
            "Use 'none' for providers that reject response_format."
        ),
    )
    ai_allow_mock: bool | None = Field(
        default=None,
        description=(
            "Allow the clearly-labelled development fixture provider when no "
            "API key is configured. Defaults to true outside production."
        ),
    )
    ai_gemini_native_schema: bool = Field(
        default=True,
        description=(
            "Pass a native response schema to Gemini. Disable if the selected "
            "model does not support structured output."
        ),
    )

    # Backwards-compatible Gemini variables (used when AI_PROVIDER=gemini).
    gemini_api_key: str = Field(
        default="",
        description="Google Gemini API key. Used if AI_API_KEY is empty.",
    )
    gemini_model_id: str = Field(
        default="gemini-3.1-flash-lite",
        description="Gemini model identifier; used if AI_MODEL is empty.",
    )

    # -----------------------------------------------------------------------
    # JWT / Auth
    # -----------------------------------------------------------------------
    jwt_secret_key: str = Field(
        default="",
        description="JWT signing secret. Falls back to app_secret_key if empty.",
    )
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    # -----------------------------------------------------------------------
    # Database (staged)
    # -----------------------------------------------------------------------
    database_url: str = Field(
        default="",
        description="Async PostgreSQL URL (asyncpg). Required from Stage 3.",
    )
    database_sync_url: str = Field(
        default="",
        description="Sync PostgreSQL URL for Alembic. Required from Stage 3.",
    )

    # -----------------------------------------------------------------------
    # Redis (optional until background jobs are needed)
    # -----------------------------------------------------------------------
    redis_url: str = Field(
        default="",
        description="Redis connection URL. Required when background jobs are enabled.",
    )

    # -----------------------------------------------------------------------
    # Neo4j (optional)
    # -----------------------------------------------------------------------
    neo4j_uri: str = ""
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""

    # -----------------------------------------------------------------------
    # Storage
    # -----------------------------------------------------------------------
    storage_backend: Literal["local", "s3", "gcs", "azure"] = "local"
    storage_local_path: str = "./storage"

    # -----------------------------------------------------------------------
    # Limits
    # -----------------------------------------------------------------------
    max_upload_size_mb: int = 50
    max_documents_per_case: int = 100
    max_analysis_focus_chars: int = 1000

    # Agent execution budgets (bounded, auditable workflows)
    agent_execution_timeout_s: int = 120
    agent_max_llm_calls: int = 5
    agent_max_input_chars: int = 24_000
    agent_min_source_chars: int = 40
    agent_max_total_tokens: int = 80_000
    agent_max_verifier_retries: int = 1
    agent_max_workflow_attempts: int = 2

    # -----------------------------------------------------------------------
    # Retrieval and legal-authority corpus (Stage 6)
    # -----------------------------------------------------------------------
    # Deterministic lexical retrieval is always on. Optional hashing embeddings
    # provide a local, offline similarity signal; a real embedding provider can
    # replace it behind the same interface.
    retrieval_embeddings_enabled: bool = False
    retrieval_embedding_dim: int = 256
    retrieval_max_candidates: int = 400
    # Precedent Explorer: no corpus by default. Set provider=json and a path to
    # an operator-supplied corpus. Never invent authorities.
    legal_corpus_provider: str = "none"
    legal_corpus_path: str = ""

    # -----------------------------------------------------------------------
    # Derived helpers
    # -----------------------------------------------------------------------
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def effective_ai_api_key(self) -> str:
        if self.ai_api_key:
            return self.ai_api_key
        if self.ai_provider == "gemini":
            return self.gemini_api_key
        return ""

    @property
    def effective_ai_model(self) -> str:
        if self.ai_model:
            return self.ai_model
        if self.ai_provider == "gemini" and self.gemini_model_id:
            return self.gemini_model_id
        defaults = {
            "gemini": "gemini-3.1-flash-lite",
            "openai": "gpt-4.1-mini",
            "anthropic": "claude-sonnet-4-5",
            "openai_compatible": "",
            "mock": "fixture",
        }
        return defaults.get(self.ai_provider, "")

    @property
    def ai_mock_allowed(self) -> bool:
        if self.ai_allow_mock is not None:
            return self.ai_allow_mock
        return not self.is_production

    @property
    def ai_configured(self) -> bool:
        """True when a real provider can be constructed from configuration."""
        if self.ai_provider == "mock":
            return True
        if self.effective_ai_api_key:
            return True
        # Local OpenAI-compatible servers (Ollama, LM Studio) often need no key.
        if self.ai_provider == "openai_compatible" and self.ai_base_url:
            return True
        return False

    @property
    def database_configured(self) -> bool:
        return bool(self.database_url)

    @property
    def redis_configured(self) -> bool:
        return bool(self.redis_url)

    @property
    def neo4j_configured(self) -> bool:
        return bool(self.neo4j_uri and self.neo4j_password)


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings singleton.

    Use ``get_settings.cache_clear()`` in tests to reset between cases.
    """
    return Settings()

