"""Deterministic date normalisation tests for the case chronology."""

from __future__ import annotations

from app.agents.tools.dates import normalise_date_text, sort_key_or_max


def test_iso_date_is_day_precision():
    info = normalise_date_text("2024-05-01")
    assert info.sort_key == "2024-05-01"
    assert info.precision == "day"
    assert info.ambiguous is False


def test_day_month_name_is_day_precision():
    info = normalise_date_text("1 May 2024")
    assert info.sort_key == "2024-05-01"
    assert info.precision == "day"


def test_month_first_name_is_day_precision():
    info = normalise_date_text("May 1, 2024")
    assert info.sort_key == "2024-05-01"
    assert info.precision == "day"


def test_ambiguous_numeric_date_is_flagged_not_guessed():
    info = normalise_date_text("05/06/2024")
    # Day-first is the documented default, but the ambiguity must be visible.
    assert info.sort_key == "2024-06-05"
    assert info.precision == "day"
    assert info.ambiguous is True
    assert info.note and "day-first" in info.note


def test_unambiguous_numeric_date_is_not_flagged():
    info = normalise_date_text("25/12/2024")
    assert info.sort_key == "2024-12-25"
    assert info.ambiguous is False


def test_month_and_year_precision():
    month = normalise_date_text("May 2024")
    assert month.sort_key == "2024-05-00"
    assert month.precision == "month"

    year = normalise_date_text("2024")
    assert year.sort_key == "2024-00-00"
    assert year.precision == "year"


def test_conflicting_dates_in_one_string_are_ambiguous():
    info = normalise_date_text("1 May 2024 or 2 May 2024")
    assert info.ambiguous is True
    assert info.note == "Multiple candidate dates appear in the same date text."


def test_relative_date_is_not_invented():
    info = normalise_date_text("the next day")
    assert info.sort_key == ""
    assert info.precision == "unknown"
    assert info.note and "relative" in info.note.lower()


def test_empty_and_unparseable_dates_are_unknown():
    assert normalise_date_text("").sort_key == ""
    assert normalise_date_text(None).sort_key == ""
    info = normalise_date_text("sometime during the dispute")
    assert info.sort_key == ""
    assert info.precision == "unknown"


def test_sort_key_places_unknown_last():
    assert sort_key_or_max("") == "9999-99-99"
    assert sort_key_or_max("2024-05-01") == "2024-05-01"
