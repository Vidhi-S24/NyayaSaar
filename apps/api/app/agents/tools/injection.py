"""Deterministic prompt-injection controls for untrusted document text.

This is not a complete defence. It detects instruction-like phrases so the
workflow can add a visible limitation instead of silently trusting the text.
The prompt wrappers and verifier remain the primary controls.
"""

from __future__ import annotations

import re

# Structural tags used by our own prompts. Untrusted text must never be able to
# close or reopen one of these wrappers.
_STRUCTURAL_TAGS = (
    "untrusted_document",
    "untrusted_focus",
    "source",
    "sources",
    "source_index",
    "case_context",
    "analyst_focus",
    "required_schema",
    "verification_feedback",
    "case_analyst_draft",
    "case_extraction",
    "system",
    "assistant",
    "developer",
)

_CONTROL_CHARS = re.compile(r"[\x01-\x08\x0b\x0c\x0e-\x1f]")

_INSTRUCTION_PATTERNS = (
    re.compile(r"\bignore\s+(?:all\s+)?(?:the\s+)?(?:previous|prior|above)\s+instructions\b", re.I),
    re.compile(r"\bdisregard\s+(?:all\s+)?(?:the\s+)?(?:previous|prior|above)\s+instructions\b", re.I),
    re.compile(r"\byou\s+are\s+now\b", re.I),
    re.compile(r"\bsystem\s+prompt\b", re.I),
    re.compile(r"\bdeveloper\s+message\b", re.I),
    re.compile(r"\bdo\s+not\s+follow\s+(?:the\s+)?(?:rules|instructions)\b", re.I),
    re.compile(r"\bact\s+as\s+(?:an?\s+)?(?:lawyer|judge|system|assistant)\b", re.I),
    re.compile(r"\bexecute\s+(?:the\s+)?(?:following|this)\s+(?:command|code)\b", re.I),
    re.compile(r"<\s*/?\s*(?:system|assistant|developer)\s*>", re.I),
)


def sanitize_untrusted_text(text: str, *, max_chars: int | None = None) -> str:
    """Remove control characters and neutralise prompt-wrapper tags."""
    cleaned = (text or "").replace("\x00", "")
    cleaned = _CONTROL_CHARS.sub(" ", cleaned)

    # Prevent untrusted text from closing/opening our structural wrappers.
    for tag in _STRUCTURAL_TAGS:
        cleaned = cleaned.replace(f"<{tag}", f"&lt;{tag}")
        cleaned = cleaned.replace(f"</{tag}", f"&lt;/{tag}")

    if max_chars is not None:
        cleaned = cleaned[:max_chars]
    return cleaned


def wrap_untrusted(
    text: str,
    *,
    tag: str = "untrusted_document",
    max_chars: int | None = 8000,
) -> str:
    """Wrap sanitised untrusted text in an explicit structural boundary.

    The opening and closing tags are the only real tags in the returned string;
    any tag-like text inside ``text`` is escaped by ``sanitize_untrusted_text``.
    """
    safe_tag = re.sub(r"[^a-z0-9_]", "", (tag or "untrusted_document").lower())
    if not safe_tag:
        safe_tag = "untrusted_document"
    body = sanitize_untrusted_text(text, max_chars=max_chars)
    return f"<{safe_tag}>\n{body}\n</{safe_tag}>"


def find_instruction_like_text(text: str) -> list[str]:
    """Return the distinct instruction-like phrases found in untrusted text."""
    found: list[str] = []
    for pattern in _INSTRUCTION_PATTERNS:
        match = pattern.search(text or "")
        if match:
            normalized = " ".join(match.group(0).split())
            if normalized.lower() not in {item.lower() for item in found}:
                found.append(normalized)
    return found
