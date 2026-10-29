"""
NyayaSaar API — Configuration

Uses pydantic-settings for type-safe environment variable loading.
All secrets live in environment variables; never hardcode or log them.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
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

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    # -----------------------------------------------------------------------
    # Gemini AI (server-side only)
    # -----------------------------------------------------------------------
    gemini_api_key: str = Field(
        default="",
        description="Google Gemini API key. Required for AI features.",
    )
    gemini_model_id: str = Field(
        default="gemini-2.0-flash-001",
        description="Gemini model identifier; configurable without code changes.",
    )

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
    agent_execution_timeout_s: int = 120

    # -----------------------------------------------------------------------
    # Derived helpers
    # -----------------------------------------------------------------------
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def gemini_configured(self) -> bool:
        return bool(self.gemini_api_key)

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

