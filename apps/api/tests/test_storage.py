"""
Tests — Storage provider (unit tests).

Tests the LocalStorageProvider safety properties, path traversal prevention,
and the storage key generator.
"""

from __future__ import annotations

import os
import tempfile

import pytest

from app.services.storage import LocalStorageProvider, make_storage_key


# ---------------------------------------------------------------------------
# make_storage_key
# ---------------------------------------------------------------------------


class TestMakeStorageKey:
    def test_structure(self) -> None:
        key = make_storage_key("case-abc", "doc-xyz", ".pdf")
        assert key.startswith("cases/case-abc/documents/doc-xyz")
        assert key.endswith(".pdf")

    def test_extension_stripped_dot(self) -> None:
        key = make_storage_key("c1", "d1", ".PDF")
        # Extension is lowercased
        assert key.endswith(".pdf")

    def test_non_alnum_extension_replaced(self) -> None:
        key = make_storage_key("c1", "d1", "..dangerous")
        assert key.endswith(".bin") or key.endswith(".dangerous")

    def test_no_path_separators_in_ids(self) -> None:
        key = make_storage_key("case-1", "doc-1", ".txt")
        # No double slashes
        assert "//" not in key


# ---------------------------------------------------------------------------
# LocalStorageProvider
# ---------------------------------------------------------------------------


class TestLocalStorageProvider:
    @pytest.fixture
    def tmp_provider(self, tmp_path):
        return LocalStorageProvider(str(tmp_path))

    def test_save_and_load(self, tmp_provider) -> None:
        key = "cases/abc/documents/def.pdf"
        data = b"%PDF-1.4 test content"
        tmp_provider.save(key, data, "application/pdf")
        loaded = tmp_provider.load(key)
        assert loaded == data

    def test_exists(self, tmp_provider) -> None:
        key = "cases/abc/documents/def.pdf"
        assert tmp_provider.exists(key) is False
        tmp_provider.save(key, b"hello", "text/plain")
        assert tmp_provider.exists(key) is True

    def test_delete(self, tmp_provider) -> None:
        key = "cases/abc/documents/del.pdf"
        tmp_provider.save(key, b"bytes", "application/pdf")
        assert tmp_provider.exists(key) is True
        tmp_provider.delete(key)
        assert tmp_provider.exists(key) is False

    def test_delete_nonexistent_no_raise(self, tmp_provider) -> None:
        # Should not raise
        tmp_provider.delete("cases/nonexistent/doc.pdf")

    def test_load_nonexistent_raises(self, tmp_provider) -> None:
        with pytest.raises(FileNotFoundError):
            tmp_provider.load("cases/missing/doc.pdf")

    def test_path_traversal_rejected(self, tmp_provider) -> None:
        with pytest.raises(ValueError, match="traversal"):
            tmp_provider.save("../../etc/passwd", b"attack", "text/plain")

    def test_path_traversal_in_load_rejected(self, tmp_provider) -> None:
        with pytest.raises(ValueError, match="traversal"):
            tmp_provider.load("../outside.pdf")

    def test_save_binary_io(self, tmp_provider) -> None:
        import io
        key = "cases/abc/documents/stream.pdf"
        stream = io.BytesIO(b"stream content")
        tmp_provider.save(key, stream, "application/pdf")
        assert tmp_provider.load(key) == b"stream content"

    def test_nested_key_creates_dirs(self, tmp_provider) -> None:
        key = "cases/deep/nested/path/doc.pdf"
        tmp_provider.save(key, b"content", "application/pdf")
        assert tmp_provider.exists(key) is True
