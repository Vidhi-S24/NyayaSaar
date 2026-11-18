"""
NyayaSaar API — Document text extraction service (PyMuPDF).

Security notes:
- All extracted text is treated as UNTRUSTED CONTENT (uploaded by users).
- Extraction errors are reported as metadata; no raw exception messages
  containing document content are exposed to callers.
- OCR is not performed in this stage; scanned PDFs are detected and flagged.
- Never pass extracted text to shell commands or eval equivalents.

Extraction strategy:
1. PDF  → PyMuPDF page-by-page extraction; detect scanned/image PDFs.
2. DOCX → python-docx paragraph extraction with page boundary approximation.
3. TXT  → plain text, single page.

Page numbers are 1-indexed and stable — downstream AI claims MUST cite the
exact (document_id, page_number) pair so the user can verify the source.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

logger = logging.getLogger("nyayasaar.extraction")

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ExtractedPage:
    """
    Text content of a single page extracted from a document.

    page_number is 1-indexed and matches the original document page.
    char_count approximates the amount of usable text on the page.
    """

    page_number: int
    text: str  # UNTRUSTED — treat as adversarial input
    char_count: int = field(init=False)

    def __post_init__(self) -> None:
        self.char_count = len(self.text)


@dataclass
class ExtractionResult:
    """
    Full extraction result for a single document.

    is_complete: False when any pages failed or extraction was partial.
    is_ocr_required: True when the document appears to be a scanned/image-only PDF.
    failure_reason: Human-readable note (no raw document text; safe to store).
    completeness_pct: Percentage of pages successfully extracted (0–100).
    """

    pages: list[ExtractedPage]
    total_page_count: int
    is_complete: bool
    is_ocr_required: bool = False
    failure_reason: str | None = None
    completeness_pct: int = 100


# ---------------------------------------------------------------------------
# MIME-type / magic byte detection
# ---------------------------------------------------------------------------

# Minimum magic bytes required to identify a file type
_PDF_MAGIC = b"%PDF"
_DOCX_MAGIC = b"PK\x03\x04"  # ZIP archive (DOCX, XLSX, PPTX)
_DOC_MAGIC = b"\xd0\xcf\x11\xe0"  # Compound Document (old .doc)


def detect_content_type(data: bytes) -> str | None:
    """
    Detect content type from file bytes (magic bytes).
    Returns a MIME type string or None if unrecognised.

    Never trust the client-supplied MIME type or file extension alone.
    """
    if data[:4] == _PDF_MAGIC:
        return "application/pdf"
    if data[:4] == _DOCX_MAGIC:
        # Could be DOCX, XLSX, PPTX — check the internal structure below
        # For simplicity, return the DOCX type; the extractor will validate
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if data[:4] == _DOC_MAGIC:
        return "application/msword"
    if _is_valid_utf8_text(data[:512]):
        return "text/plain"
    return None


def _is_valid_utf8_text(data: bytes) -> bool:
    """Heuristic: check if bytes are valid UTF-8 with mostly printable content."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    # Must be mostly printable ASCII/Unicode characters
    printable = sum(1 for c in text if c.isprintable() or c in "\n\r\t")
    return len(text) > 0 and (printable / max(len(text), 1)) > 0.80


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
}

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}


def validate_upload(
    filename: str,
    data: bytes,
    max_size_bytes: int,
) -> tuple[str, str]:
    """
    Validate an upload and return (safe_extension, detected_mime_type).

    Raises ValueError with a user-safe message on any violation.
    Does NOT trust the client MIME type; always detects from bytes.
    """
    # Size check
    if len(data) == 0:
        raise ValueError("The uploaded file is empty.")
    if len(data) > max_size_bytes:
        mb = max_size_bytes // (1024 * 1024)
        raise ValueError(f"File exceeds the maximum allowed size of {mb} MB.")

    # Extension check (from original filename)
    stem, ext = _split_extension(filename)
    if not ext or ext.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"File type '{ext or 'none'}' is not supported. "
            f"Accepted: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    # Content type detection from bytes
    detected = detect_content_type(data)
    if detected is None:
        raise ValueError("Could not determine file type from content. The file may be corrupt.")
    if detected not in ALLOWED_MIME_TYPES:
        raise ValueError(
            f"Detected file type '{detected}' is not permitted. "
            f"Upload PDF, DOCX, or plain-text files only."
        )

    return ext.lower(), detected


def _split_extension(filename: str) -> tuple[str, str]:
    """Return (stem, '.ext') normalised to lowercase."""
    # Strip path components defensively (even though we never use the name as a path)
    name = Path(filename).name
    if "." in name:
        stem, _, ext = name.rpartition(".")
        return stem, f".{ext.lower()}"
    return name, ""


# ---------------------------------------------------------------------------
# PDF extractor (PyMuPDF)
# ---------------------------------------------------------------------------

# A page is considered "text-rich" only if it has this many non-space characters.
_MIN_TEXT_CHARS_PER_PAGE = 30


def extract_pdf(data: bytes) -> ExtractionResult:
    """
    Extract text from a PDF using PyMuPDF (fitz).

    - Attempts text extraction on every page.
    - Detects image-only / scanned pages by low character count.
    - Returns partial results when some pages succeed.
    - Reports OCR requirement without attempting OCR (future extension point).
    """
    try:
        import fitz  # type: ignore[import]  # PyMuPDF
    except ImportError:
        return ExtractionResult(
            pages=[],
            total_page_count=0,
            is_complete=False,
            failure_reason=(
                "PyMuPDF is not installed. Install it with: "
                "pip install PyMuPDF>=1.24.0"
            ),
        )

    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception:
        # Do not log raw exception — it may contain document content fragments
        logger.warning("PDF could not be opened — file may be corrupt or encrypted.")
        return ExtractionResult(
            pages=[],
            total_page_count=0,
            is_complete=False,
            failure_reason="PDF could not be opened. The file may be corrupt, encrypted, or malformed.",
        )

    total = doc.page_count
    pages: list[ExtractedPage] = []
    ocr_pages = 0
    failed_pages = 0

    for page_idx in range(total):
        page_num = page_idx + 1  # 1-indexed
        try:
            page = doc[page_idx]
            text = page.get_text("text")  # plain-text extraction
            # Normalise whitespace but preserve paragraph breaks
            text = _normalise_whitespace(text)
        except Exception:
            logger.warning("Page %d extraction failed; skipping.", page_num)
            failed_pages += 1
            continue

        char_count = sum(1 for c in text if not c.isspace())
        if char_count < _MIN_TEXT_CHARS_PER_PAGE:
            # Likely a scanned/image page
            ocr_pages += 1
            # Still include the page in results with what we have
            pages.append(ExtractedPage(page_number=page_num, text=text or ""))
        else:
            pages.append(ExtractedPage(page_number=page_num, text=text))

    doc.close()

    is_ocr = ocr_pages > 0 and (ocr_pages / max(total, 1)) > 0.5
    extracted = len(pages)
    completeness = round((extracted / max(total, 1)) * 100)
    is_complete = failed_pages == 0 and not is_ocr

    failure_reason: str | None = None
    if is_ocr:
        failure_reason = (
            f"The document appears to be a scanned PDF "
            f"({ocr_pages} of {total} pages have little or no selectable text). "
            f"OCR is not yet enabled; extracted text may be incomplete. "
            f"Convert the document to a text-layer PDF for best results."
        )
    elif failed_pages > 0:
        failure_reason = (
            f"{failed_pages} of {total} pages could not be extracted due to errors."
        )

    return ExtractionResult(
        pages=pages,
        total_page_count=total,
        is_complete=is_complete,
        is_ocr_required=is_ocr,
        failure_reason=failure_reason,
        completeness_pct=completeness,
    )


# ---------------------------------------------------------------------------
# DOCX extractor (python-docx with page approximation)
# ---------------------------------------------------------------------------


def extract_docx(data: bytes) -> ExtractionResult:
    """
    Extract text from a DOCX file.

    DOCX does not have a stable page-number concept (pagination depends on the
    renderer). We approximate page boundaries by grouping paragraphs: every
    ~40 paragraphs is treated as one logical 'page'. This provides stable,
    reproducible page numbers so downstream AI claims can cite a specific page.
    """
    try:
        import io
        import docx  # type: ignore[import]  # python-docx
    except ImportError:
        return ExtractionResult(
            pages=[],
            total_page_count=1,
            is_complete=False,
            failure_reason=(
                "python-docx is not installed. Install it with: "
                "pip install python-docx>=1.1.0"
            ),
        )

    try:
        doc = docx.Document(io.BytesIO(data))
    except Exception:
        logger.warning("DOCX could not be opened — file may be corrupt.")
        return ExtractionResult(
            pages=[],
            total_page_count=0,
            is_complete=False,
            failure_reason="DOCX file could not be opened. The file may be corrupt or malformed.",
        )

    paragraphs = [p.text for p in doc.paragraphs]
    if not paragraphs:
        return ExtractionResult(
            pages=[ExtractedPage(page_number=1, text="")],
            total_page_count=1,
            is_complete=True,
        )

    # Group ~40 paragraphs per logical page
    PARAS_PER_PAGE = 40
    pages: list[ExtractedPage] = []
    for i in range(0, len(paragraphs), PARAS_PER_PAGE):
        chunk = "\n".join(paragraphs[i : i + PARAS_PER_PAGE])
        chunk = _normalise_whitespace(chunk)
        pages.append(ExtractedPage(page_number=len(pages) + 1, text=chunk))

    return ExtractionResult(
        pages=pages,
        total_page_count=len(pages),
        is_complete=True,
        completeness_pct=100,
    )


# ---------------------------------------------------------------------------
# Plain-text extractor
# ---------------------------------------------------------------------------


def extract_txt(data: bytes) -> ExtractionResult:
    """
    Extract text from a plain-text file.

    Decoded as UTF-8 with fallback to latin-1. Returned as a single page.
    """
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = data.decode("latin-1")
        except UnicodeDecodeError:
            return ExtractionResult(
                pages=[],
                total_page_count=0,
                is_complete=False,
                failure_reason="Text file could not be decoded as UTF-8 or Latin-1.",
            )
    text = _normalise_whitespace(text)
    return ExtractionResult(
        pages=[ExtractedPage(page_number=1, text=text)],
        total_page_count=1,
        is_complete=True,
        completeness_pct=100,
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def extract_document(data: bytes, content_type: str) -> ExtractionResult:
    """
    Route file bytes to the appropriate extractor based on detected content type.

    content_type must be the *detected* MIME type (from magic bytes), never the
    client-supplied value.
    """
    if content_type == "application/pdf":
        return extract_pdf(data)
    elif content_type in {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    }:
        return extract_docx(data)
    elif content_type == "text/plain":
        return extract_txt(data)
    else:
        return ExtractionResult(
            pages=[],
            total_page_count=0,
            is_complete=False,
            failure_reason=f"No extractor available for content type: {content_type!r}",
        )


# ---------------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------------


def _normalise_whitespace(text: str) -> str:
    """
    Collapse multiple blank lines but preserve paragraph breaks.
    Does NOT strip the content — that is the caller's concern.
    """
    # Collapse 3+ consecutive newlines to 2 (preserve paragraph spacing)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse horizontal whitespace runs to a single space
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()
