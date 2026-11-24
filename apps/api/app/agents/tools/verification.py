"""Deterministic citation resolution for the extended Stage 6 workflows.

The model only sees source markers (``S1``, ``S2`` ...). This module maps those
markers back to real ``document_id``/``page_number`` values and checks the
model-supplied quote against the analysed excerpt. Nothing here calls a model.

A reference that cannot be mapped is left with empty document fields; the UI
must show it as unresolved rather than inventing a page.
"""

from __future__ import annotations

from typing import Any

from app.agents.schemas_extended import (
    AdvocateResult,
    ContradictionResult,
    ExtendedVerification,
    JudgeResult,
    PrecedentResult,
    SourceRef,
)


def _normalise(text: str) -> str:
    return " ".join((text or "").split()).casefold()


def _source_index(sources: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for source in sources:
        marker = str(source.get("source_id", "")).strip().upper()
        if marker:
            index[marker] = source
    return index


class _Counter:
    __slots__ = ("total", "verified", "unresolved", "unverified_quotes")

    def __init__(self) -> None:
        self.total = 0
        self.verified = 0
        self.unresolved = 0
        self.unverified_quotes = 0


def _resolve_ref(
    ref: SourceRef,
    by_id: dict[str, dict[str, Any]],
    counter: _Counter,
) -> SourceRef:
    counter.total += 1
    source = by_id.get((ref.source_id or "").strip().upper())
    if source is None:
        ref.quote_verified = False
        counter.unresolved += 1
        return ref

    ref.document_id = str(source.get("document_id", ""))
    ref.document_name = str(source.get("document_name", ""))
    page = source.get("page_number")
    ref.page_number = int(page) if page is not None else None

    quote = (ref.quote or "").strip()
    if quote and _normalise(quote) in _normalise(str(source.get("text", ""))):
        ref.quote_verified = True
        counter.verified += 1
    else:
        ref.quote_verified = False
        counter.unverified_quotes += 1
    return ref


def _resolve_refs(
    refs: list[SourceRef],
    by_id: dict[str, dict[str, Any]],
    counter: _Counter,
) -> list[SourceRef]:
    return [_resolve_ref(ref, by_id, counter) for ref in refs]


def _summary(counter: _Counter) -> ExtendedVerification:
    notes: list[str] = []
    if counter.unresolved:
        notes.append(
            f"{counter.unresolved} source reference(s) could not be matched to a "
            "loaded page and were left unresolved."
        )
    if counter.unverified_quotes:
        notes.append(
            f"{counter.unverified_quotes} quoted excerpt(s) were not found verbatim "
            "in the cited page; do not rely on them without checking."
        )
    if counter.total and not counter.verified and not counter.unverified_quotes:
        notes.append("No quoted excerpts were supplied for verification.")
    return ExtendedVerification(
        total_source_refs=counter.total,
        verified_quotes=counter.verified,
        unresolved_refs=counter.unresolved,
        notes=notes,
    )


def resolve_contradiction_result(
    result: ContradictionResult, sources: list[dict[str, Any]]
) -> ContradictionResult:
    by_id = _source_index(sources)
    counter = _Counter()
    for item in result.contradictions:
        _resolve_ref(item.document_a_ref, by_id, counter)
        _resolve_ref(item.document_b_ref, by_id, counter)
    for gap in result.gaps:
        gap.source_refs = _resolve_refs(gap.source_refs, by_id, counter)
    for assertion in result.unsupported_assertions:
        assertion.source_refs = _resolve_refs(assertion.source_refs, by_id, counter)
    for conflict in result.timeline_conflicts:
        if conflict.source_a_ref is not None:
            _resolve_ref(conflict.source_a_ref, by_id, counter)
        if conflict.source_b_ref is not None:
            _resolve_ref(conflict.source_b_ref, by_id, counter)
    result.verification = _summary(counter)
    return result


def resolve_advocate_result(
    result: AdvocateResult, sources: list[dict[str, Any]]
) -> AdvocateResult:
    by_id = _source_index(sources)
    counter = _Counter()
    for argument in [*result.claimant_arguments, *result.respondent_arguments]:
        argument.supporting_sources = _resolve_refs(
            argument.supporting_sources, by_id, counter
        )
        argument.opposing_sources = _resolve_refs(
            argument.opposing_sources, by_id, counter
        )
    for gap in result.evidentiary_gaps:
        gap.source_refs = _resolve_refs(gap.source_refs, by_id, counter)
    result.verification = _summary(counter)
    return result


def resolve_judge_result(
    result: JudgeResult, sources: list[dict[str, Any]]
) -> JudgeResult:
    by_id = _source_index(sources)
    counter = _Counter()
    for group in (
        result.issue_coverage,
        result.reasoning_consistency,
        result.source_support_audit,
        result.citation_integrity,
        result.unresolved_questions,
    ):
        for item in group:
            item.source_refs = _resolve_refs(item.source_refs, by_id, counter)
    result.verification = _summary(counter)
    return result


def resolve_precedent_result(
    result: PrecedentResult, sources: list[dict[str, Any]]
) -> PrecedentResult:
    # Precedent authorities are corpus records, not document excerpts. There is
    # no document citation to resolve; the corpus provider supplies provenance.
    result.verification = ExtendedVerification(
        notes=[
            "Authorities come from the configured corpus only; they are not "
            "document excerpts from this case."
        ]
        if result.corpus_configured
        else ["No authority corpus is configured; no real authorities were searched."]
    )
    return result
