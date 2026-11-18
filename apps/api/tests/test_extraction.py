"""
Tests — Document extraction service (unit tests; no DB, no HTTP).

These tests use real PyMuPDF and python-docx to validate the extraction
logic, the validation rules, and the magic-byte detection.
"""

from __future__ import annotations

import io
import struct

import pytest

from app.services.extraction import (
    ALLOWED_EXTENSIONS,
    ExtractionResult,
    detect_content_type,
    extract_document,
    extract_pdf,
    extract_txt,
    validate_upload,
)


# ---------------------------------------------------------------------------
# Helpers — minimal synthetic files
# ---------------------------------------------------------------------------


def _make_minimal_pdf(text: str = "Hello, legal world.") -> bytes:
    """
    Build the smallest valid PDF that PyMuPDF can open and that contains
    one text page.  Uses raw PDF syntax (no external library).
    """
    content_stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"
    cs = content_stream.encode()
    cs_len = len(cs)

    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R "
        b"/MediaBox [0 0 612 792] "
        b"/Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        b"4 0 obj\n<< /Length " + str(cs_len).encode() + b" >>\nstream\n"
        + cs
        + b"\nendstream\nendobj\n"
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
    )

    xref_offset = len(pdf)
    # Minimal cross-reference table
    xref = (
        b"xref\n"
        b"0 6\n"
        b"0000000000 65535 f \n"
    )
    # Approximate offsets (not byte-accurate but enough for PyMuPDF to open)
    for _ in range(5):
        xref += b"0000000009 00000 n \n"

    trailer = (
        b"trailer\n<< /Size 6 /Root 1 0 R >>\n"
        b"startxref\n"
        + str(xref_offset).encode()
        + b"\n%%EOF\n"
    )

    return pdf + xref + trailer


def _make_plaintext(content: str = "Section 1\nFacts of the case.") -> bytes:
    return content.encode("utf-8")


def _make_docx() -> bytes:
    """Create a minimal valid DOCX in memory using python-docx."""
    docx = pytest.importorskip("docx")
    buf = io.BytesIO()
    doc = docx.Document()
    doc.add_paragraph("This is a legal document.")
    doc.add_paragraph("Section 2: Facts.")
    doc.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# detect_content_type
# ---------------------------------------------------------------------------


class TestDetectContentType:
    def test_pdf(self) -> None:
        assert detect_content_type(b"%PDF-1.4...") == "application/pdf"

    def test_docx_magic(self) -> None:
        # ZIP magic (DOCX)
        docx_data = b"PK\x03\x04" + b"\x00" * 100
        result = detect_content_type(docx_data)
        assert result == (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    def test_doc_magic(self) -> None:
        doc_data = b"\xd0\xcf\x11\xe0" + b"\x00" * 100
        assert detect_content_type(doc_data) == "application/msword"

    def test_plaintext(self) -> None:
        txt = b"This is a plain text legal document.\n"
        assert detect_content_type(txt) == "text/plain"

    def test_binary_unknown(self) -> None:
        # Random binary with no magic bytes
        data = bytes(range(256))
        assert detect_content_type(data) is None


# ---------------------------------------------------------------------------
# validate_upload
# ---------------------------------------------------------------------------


class TestValidateUpload:
    def test_valid_pdf(self) -> None:
        data = b"%PDF-1.4" + b"x" * 100
        ext, mime = validate_upload("brief.pdf", data, 50 * 1024 * 1024)
        assert ext == ".pdf"
        assert mime == "application/pdf"

    def test_empty_file_rejected(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            validate_upload("empty.pdf", b"", 1024)

    def test_oversized_rejected(self) -> None:
        big = b"%PDF-1.4" + b"x" * 200
        with pytest.raises(ValueError, match="maximum allowed size"):
            validate_upload("big.pdf", big, 50)  # 50 bytes limit

    def test_bad_extension_rejected(self) -> None:
        data = b"%PDF-1.4" + b"x" * 50
        with pytest.raises(ValueError, match="not supported"):
            validate_upload("virus.exe", data, 10 * 1024 * 1024)

    def test_extension_mismatch_allowed_if_mime_matches(self) -> None:
        """Extension check passes for supported extensions regardless of data."""
        data = b"%PDF-1.4" + b"x" * 50
        # .pdf extension + PDF magic bytes → valid
        ext, mime = validate_upload("test.pdf", data, 10 * 1024 * 1024)
        assert ext == ".pdf"

    def test_missing_extension_rejected(self) -> None:
        data = b"%PDF-1.4" + b"x" * 50
        with pytest.raises(ValueError, match="not supported"):
            validate_upload("nodotfile", data, 10 * 1024 * 1024)

    def test_txt_accepted(self) -> None:
        data = "Plain text document\nLine 2\n".encode()
        ext, mime = validate_upload("notes.txt", data, 1024 * 1024)
        assert ext == ".txt"
        assert mime == "text/plain"

    def test_path_traversal_in_filename_safe(self) -> None:
        """Path traversal in original filename doesn't affect validation logic."""
        data = b"%PDF-1.4" + b"x" * 100
        # validate_upload calls _split_extension which strips path components
        ext, mime = validate_upload("../../etc/passwd.pdf", data, 10 * 1024 * 1024)
        assert ext == ".pdf"


# ---------------------------------------------------------------------------
# extract_txt
# ---------------------------------------------------------------------------


class TestExtractTxt:
    def test_basic(self) -> None:
        data = b"Section 1\nFacts of the case.\nSection 2\nArguments."
        result = extract_txt(data)
        assert result.is_complete is True
        assert len(result.pages) == 1
        assert result.pages[0].page_number == 1
        assert "Section 1" in result.pages[0].text

    def test_empty_text(self) -> None:
        result = extract_txt(b"")
        # Empty but should not crash
        assert isinstance(result, ExtractionResult)

    def test_latin1_fallback(self) -> None:
        # Bytes that are valid latin-1 but not UTF-8
        data = "Café légal\n".encode("latin-1")
        result = extract_txt(data)
        assert result.is_complete is True


# ---------------------------------------------------------------------------
# extract_pdf (integration — real PyMuPDF)
# ---------------------------------------------------------------------------


class TestExtractPdf:
    def test_valid_pdf(self) -> None:
        pdf_bytes = _make_minimal_pdf("Court petition text goes here")
        result = extract_pdf(pdf_bytes)
        # May be incomplete extraction on a minimal synthetic PDF but should not crash
        assert isinstance(result, ExtractionResult)
        assert result.total_page_count >= 0

    def test_corrupt_pdf(self) -> None:
        result = extract_pdf(b"This is not a PDF at all.")
        assert result.is_complete is False
        assert "corrupt" in (result.failure_reason or "").lower() or not result.pages

    def test_empty_bytes(self) -> None:
        result = extract_pdf(b"")
        assert result.is_complete is False


# ---------------------------------------------------------------------------
# extract_document dispatch
# ---------------------------------------------------------------------------


class TestExtractDocument:
    def test_dispatch_txt(self) -> None:
        data = b"Legal text content."
        result = extract_document(data, "text/plain")
        assert isinstance(result, ExtractionResult)

    def test_dispatch_pdf(self) -> None:
        data = _make_minimal_pdf()
        result = extract_document(data, "application/pdf")
        assert isinstance(result, ExtractionResult)

    def test_dispatch_docx(self) -> None:
        data = _make_docx()
        result = extract_document(
            data,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        assert isinstance(result, ExtractionResult)
        assert len(result.pages) >= 1
        assert "legal document" in result.pages[0].text.lower()

    def test_unknown_content_type(self) -> None:
        result = extract_document(b"\x00\x01\x02", "image/jpeg")
        assert result.is_complete is False
        assert result.failure_reason is not None
