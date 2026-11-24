"""Deterministic date normalisation for the case chronology.

The model supplies a human date string (``date_text``). This module converts it
into a sortable key and records its precision and ambiguity. It never invents a
date: if the text cannot be parsed, the key is empty and the chronology keeps the
original wording.

The default interpretation for numeric ``dd/mm/yyyy`` is day-first (the Indian
convention). When both components could be a day or a month, the date is flagged
as ambiguous rather than silently guessed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

MONTHS = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}
MONTH_PATTERN = "|".join(sorted(MONTHS, key=len, reverse=True))

_ISO = re.compile(r"\b(?P<y>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})\b")
_NUMERIC = re.compile(
    r"(?<!\d)(?P<a>\d{1,2})[./-](?P<b>\d{1,2})[./-](?P<y>\d{2,4})(?!\d)"
)
_DMY = re.compile(
    rf"(?<!\d)(?P<d>\d{{1,2}})(?:st|nd|rd|th)?\s+(?P<mon>{MONTH_PATTERN})\.?,?\s+(?P<y>\d{{4}})(?!\d)",
    re.IGNORECASE,
)
_MDY = re.compile(
    rf"(?P<mon>{MONTH_PATTERN})\.?\s+(?P<d>\d{{1,2}})(?:st|nd|rd|th)?,?\s+(?P<y>\d{{4}})(?!\d)",
    re.IGNORECASE,
)
_MY = re.compile(
    rf"(?P<mon>{MONTH_PATTERN})\.?,?\s+(?P<y>\d{{4}})(?!\d)",
    re.IGNORECASE,
)
_YEAR = re.compile(r"(?<!\d)(?P<y>(?:19|20)\d{2})(?!\d)")
_RELATIVE = re.compile(
    r"\b(?:same day|next day|previous day|following day|the day before|the day after|"
    r"yesterday|today|tomorrow|immediately|subsequently|thereafter|later)\b",
    re.IGNORECASE,
)


@dataclass(slots=True)
class DateInfo:
    sort_key: str
    precision: str
    ambiguous: bool = False
    note: str | None = None


def _valid(year: int, month: int, day: int) -> bool:
    try:
        date(year, month, day)
        return True
    except ValueError:
        return False


def _key(year: int, month: int = 0, day: int = 0) -> str:
    return f"{year:04d}-{month:02d}-{day:02d}"


def _normalise_year(raw: str) -> int:
    value = int(raw)
    if value < 100:
        return 2000 + value if value < 70 else 1900 + value
    return value


def normalise_date_text(raw: str | None) -> DateInfo:
    """Return a sortable, honest interpretation of a human date string."""
    text = (raw or "").strip()
    if not text:
        return DateInfo("", "unknown", note="No date text was supplied.")

    matches: list[tuple[str, DateInfo]] = []

    for match in _ISO.finditer(text):
        year, month, day = int(match["y"]), int(match["m"]), int(match["d"])
        if _valid(year, month, day):
            matches.append(
                (match.group(0), DateInfo(_key(year, month, day), "day"))
            )

    for match in _DMY.finditer(text):
        day, month, year = (
            int(match["d"]),
            MONTHS[match["mon"].lower()],
            _normalise_year(match["y"]),
        )
        if _valid(year, month, day):
            matches.append(
                (match.group(0), DateInfo(_key(year, month, day), "day"))
            )

    for match in _MDY.finditer(text):
        month, day, year = (
            MONTHS[match["mon"].lower()],
            int(match["d"]),
            _normalise_year(match["y"]),
        )
        if _valid(year, month, day):
            matches.append(
                (match.group(0), DateInfo(_key(year, month, day), "day"))
            )

    for match in _NUMERIC.finditer(text):
        first, second = int(match["a"]), int(match["b"])
        year = _normalise_year(match["y"])
        ambiguous = first <= 12 and second <= 12
        if first > 12 and second <= 12:
            day, month = first, second
        else:
            # Day-first is the default; if only the second value can be a
            # day, treat the input as month-first.
            day, month = (first, second) if second <= 12 else (second, first)
        if _valid(year, month, day):
            note = None
            if ambiguous:
                note = (
                    f"'{match.group(0)}' could be read as day/month or "
                    "month/day; day-first was used."
                )
            matches.append(
                (
                    match.group(0),
                    DateInfo(_key(year, month, day), "day", ambiguous, note),
                )
            )

    for match in _MY.finditer(text):
        month, year = MONTHS[match["mon"].lower()], _normalise_year(match["y"])
        matches.append(
            (match.group(0), DateInfo(_key(year, month), "month"))
        )

    for match in _YEAR.finditer(text):
        year = int(match["y"])
        matches.append((match.group(0), DateInfo(_key(year), "year")))

    if matches:
        # Prefer the most precise match. If several distinct dates are present,
        # flag the ambiguity instead of choosing silently.
        precision_rank = {"day": 3, "month": 2, "year": 1, "unknown": 0}
        matches.sort(key=lambda item: precision_rank[item[1].precision], reverse=True)
        best = matches[0][1]
        distinct = {
            info.sort_key for _, info in matches if info.precision == best.precision
        }
        if len(distinct) > 1:
            return DateInfo(
                best.sort_key,
                best.precision,
                ambiguous=True,
                note="Multiple candidate dates appear in the same date text.",
            )
        if any(info.ambiguous for _, info in matches):
            return DateInfo(
                best.sort_key,
                best.precision,
                ambiguous=True,
                note=next(
                    info.note
                    for _, info in matches
                    if info.ambiguous and info.note
                ),
            )
        return best

    if _RELATIVE.search(text):
        return DateInfo(
            "",
            "unknown",
            note="The date is relative to another event and needs a fixed date.",
        )

    return DateInfo("", "unknown", note="The date could not be normalised.")


def sort_key_or_max(sort_key: str) -> str:
    """Sort unknown dates last while preserving stability."""
    return sort_key or "9999-99-99"
