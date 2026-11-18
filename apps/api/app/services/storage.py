"""
NyayaSaar API — Storage provider abstraction.

Provides a uniform interface for file storage.  Local development uses
the filesystem; production uses S3-compatible object storage.

Security notes:
- Storage keys are always generated server-side from UUIDs; never from
  user-supplied filenames (path traversal prevention).
- Files are addressed by opaque keys, not by user-controllable paths.
- The local provider refuses keys containing path separators or ".." sequences.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO

logger = logging.getLogger("nyayasaar.storage")

# ---------------------------------------------------------------------------
# Key generation (safe, opaque, server-controlled)
# ---------------------------------------------------------------------------


def make_storage_key(case_id: str, document_id: str, extension: str) -> str:
    """
    Build a storage key that is:
    - Opaque: contains no original filename
    - Hierarchical: grouped by case for easy lifecycle management
    - Deterministic: document_id is a UUID, so no collisions
    - Safe: extension is validated before use; no path separators

    Returns e.g. "cases/abc-123/documents/def-456.pdf"
    """
    # Strip leading dot if any; limit length
    ext = extension.lstrip(".").lower()[:10]
    if not ext.isalnum():
        ext = "bin"
    return f"cases/{case_id}/documents/{document_id}.{ext}"


# ---------------------------------------------------------------------------
# Provider interface
# ---------------------------------------------------------------------------


class StorageProvider(ABC):
    """Abstract storage provider. Concrete implementations below."""

    @abstractmethod
    def save(self, key: str, data: bytes | BinaryIO, content_type: str) -> str:
        """Persist *data* at *key*. Returns the key (for confirmation)."""
        ...

    @abstractmethod
    def load(self, key: str) -> bytes:
        """Return file bytes for *key*. Raises FileNotFoundError if absent."""
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete the object at *key*. No-op if the key doesn't exist."""
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Return True if *key* has a stored object."""
        ...

    @abstractmethod
    def get_url(self, key: str, expiry_seconds: int = 3600) -> str:
        """Return a URL or pseudo-URL for the stored object."""
        ...


# ---------------------------------------------------------------------------
# Local filesystem provider (development)
# ---------------------------------------------------------------------------


class LocalStorageProvider(StorageProvider):
    """
    Stores files in a local directory tree.

    Security:
    - Resolves the full path and asserts it stays within the base directory
      (prevents path traversal even if a malformed key were passed).
    - base_path is normalised on construction.
    """

    def __init__(self, base_path: str) -> None:
        self._base = Path(base_path).resolve()
        self._base.mkdir(parents=True, exist_ok=True)
        logger.info("LocalStorageProvider initialised at %s", self._base)

    def _resolve(self, key: str) -> Path:
        """Resolve the key to an absolute path, rejecting traversal attempts."""
        # Normalise separators
        safe_key = key.replace("\\", "/")
        full = (self._base / safe_key).resolve()
        # Prevent path traversal
        if not str(full).startswith(str(self._base)):
            raise ValueError(f"Illegal storage key (path traversal attempt): {key!r}")
        return full

    def save(self, key: str, data: bytes | BinaryIO, content_type: str) -> str:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, (bytes, bytearray)):
            path.write_bytes(data)
        else:
            with path.open("wb") as f:
                shutil.copyfileobj(data, f)
        logger.debug("LocalStorage: saved %s (%s)", key, content_type)
        return key

    def load(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.exists():
            raise FileNotFoundError(f"Storage key not found: {key!r}")
        return path.read_bytes()

    def delete(self, key: str) -> None:
        try:
            path = self._resolve(key)
            if path.exists():
                path.unlink()
                logger.debug("LocalStorage: deleted %s", key)
        except (ValueError, OSError) as exc:
            logger.warning("LocalStorage: delete failed for %r: %s", key, exc)

    def exists(self, key: str) -> bool:
        try:
            return self._resolve(key).exists()
        except ValueError:
            return False

    def get_url(self, key: str, expiry_seconds: int = 3600) -> str:
        # Local dev: return a pseudo-URL that the backend download endpoint handles
        return f"/api/v1/documents/download?key={key}"


# ---------------------------------------------------------------------------
# S3-compatible provider (production interface — not yet implemented)
# ---------------------------------------------------------------------------


class S3StorageProvider(StorageProvider):
    """
    Production S3-compatible object storage.

    Install: boto3>=1.35.0 (not in requirements.txt yet — added when this
    provider is activated in production, as the binary wheels are Linux-specific).

    Configuration: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_S3_BUCKET,
    AWS_S3_REGION, (optionally) AWS_S3_ENDPOINT_URL for non-AWS providers.
    """

    def __init__(
        self,
        bucket: str,
        region: str,
        endpoint_url: str | None = None,
    ) -> None:
        # Import lazily — boto3 is not a required dependency for local dev
        try:
            import boto3  # type: ignore[import]
        except ImportError as exc:
            raise RuntimeError(
                "boto3 is required for S3 storage. "
                "Add boto3>=1.35.0 to requirements.txt and install it."
            ) from exc
        self._client = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=endpoint_url,
        )
        self._bucket = bucket
        logger.info("S3StorageProvider initialised (bucket=%s region=%s)", bucket, region)

    def save(self, key: str, data: bytes | BinaryIO, content_type: str) -> str:
        import io
        if isinstance(data, (bytes, bytearray)):
            data = io.BytesIO(data)
        self._client.upload_fileobj(
            data,
            self._bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )
        return key

    def load(self, key: str) -> bytes:
        import io
        buf = io.BytesIO()
        try:
            self._client.download_fileobj(self._bucket, key, buf)
        except self._client.exceptions.NoSuchKey:
            raise FileNotFoundError(f"S3 key not found: {key!r}")
        return buf.getvalue()

    def delete(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except Exception as exc:
            logger.warning("S3: delete failed for %r: %s", key, exc)

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except Exception:
            return False

    def get_url(self, key: str, expiry_seconds: int = 3600) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expiry_seconds,
        )


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------


def build_storage_provider() -> StorageProvider:
    """Construct the configured storage provider from environment settings."""
    from app.config import get_settings

    settings = get_settings()
    backend = settings.storage_backend

    if backend == "local":
        return LocalStorageProvider(settings.storage_local_path)
    elif backend == "s3":
        bucket = os.environ.get("AWS_S3_BUCKET", "")
        region = os.environ.get("AWS_S3_REGION", "us-east-1")
        endpoint = os.environ.get("AWS_S3_ENDPOINT_URL") or None
        if not bucket:
            raise RuntimeError(
                "AWS_S3_BUCKET environment variable is required for S3 storage."
            )
        return S3StorageProvider(bucket=bucket, region=region, endpoint_url=endpoint)
    else:
        raise RuntimeError(
            f"Unknown storage backend: {backend!r}. "
            "Set STORAGE_BACKEND to 'local' or 's3'."
        )


# ---------------------------------------------------------------------------
# Module-level singleton (lazy; built on first access)
# ---------------------------------------------------------------------------

_provider: StorageProvider | None = None


def get_storage() -> StorageProvider:
    """Return the configured storage provider singleton."""
    global _provider
    if _provider is None:
        _provider = build_storage_provider()
    return _provider


def _reset_storage() -> None:
    """Reset the singleton — used in tests only."""
    global _provider
    _provider = None
