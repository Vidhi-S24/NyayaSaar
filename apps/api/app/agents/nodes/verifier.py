"""Deterministic verifier node.

No model is called here. Every claim is checked against the actual source
excerpts: unknown source markers are rejected, quotes must be real substrings of
the cited page, and verified quotes receive character offsets for the source
viewer. Unsupported claims are surfaced, not hidden.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from app.agents.context import WorkflowContext
from app.agents.schemas import (
    CASE_INTELLIGENCE_PROMPT_VERSION,
    CASE_INTELLIGENCE_RESULT_SCHEMA_VERSION,
    CASE_INTELLIGENCE_WORKFLOW_VERSION,
    CaseAnalysisDraft,
    CaseAnalysisResult,
    DraftAmount,
    DraftClaim,
    DraftEntity,
    DraftParty,
    DraftProceduralEvent,
    DraftSourceRef,
    DraftTimelineEvent,
    EvidenceAnalysisDraft,
    SourceManifestEntry,
    SourceStats,
    VerificationCategoryCount,
    VerificationSummary,
    VerifiedAmount,
    VerifiedClaim,
    VerifiedEntity,
    VerifiedEvidenceQuestion,
    VerifiedLegalIssue,
    VerifiedParty,
    VerifiedProceduralEvent,
    VerifiedSourceRef,
    VerifiedTimelineEvent,
    VerifiedUncertainty,
)
from app.agents.state import CaseAnalysisState
from app.agents.tools.dates import normalise_date_text
from app.agents.tools.injection import find_instruction_like_text
from app.agents.tools.sources import (
    SourceExcerpt,
    find_quote_span,
    quote_in_source,
    resolve_source,
    sources_from_state,
)

AUTHORITY_CITATION_PATTERN = re.compile(
    r"\b(?:AIR|SCC|SCR|CrLJ|CriLJ|MLJ|BomCR|KerLT)\b",
    re.IGNORECASE,
)

STANDARD_LIMITATIONS = [
    "No external legal authority database was consulted; authorities and legal "
    "issues must be researched separately.",
    "Legal issues are questions for professional review, not legal conclusions.",
    "AI-assisted output requires independent professional legal verification.",
]


def _unique(items: list[str], limit: int = 16) -> list[str]:
    """De-duplicate a string list while preserving insertion order."""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        cleaned = item.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            out.append(cleaned)
        if len(out) >= limit:
            break
    return out


def _normalise_source_id(raw: str) -> str:
    """Accept ``S1``, ``s1``, ``[S1]``, ``(S1)`` and return ``S1``."""
    value = (raw or "").strip()
    match = re.fullmatch(r"[\[\(]?\s*(S\d{1,3})\s*[\]\)]?", value, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return value.upper()


def _verify_ref(
    ref: DraftSourceRef, sources: list[SourceExcerpt]
) -> tuple[VerifiedSourceRef | None, bool]:
    source = resolve_source(sources, _normalise_source_id(ref.source_id))
    if source is None:
        return None, True
    span = find_quote_span(ref.quote, source.text)
    verified = bool(ref.quote) and (
        span is not None or quote_in_source(ref.quote, source.text)
    )
    return (
        VerifiedSourceRef(
            source_id=source.source_id,
            document_id=source.document_id,
            document_name=source.document_name,
            page_number=source.page_number,
            quote=ref.quote,
            quote_verified=verified,
            span_start=span[0] if span else None,
            span_end=span[1] if span else None,
        ),
        False,
    )


def _support(refs: list[VerifiedSourceRef]) -> str:
    if any(ref.quote_verified for ref in refs):
        return "supported"
    if refs:
        return "partially_supported"
    return "unsupported"


def _verify_refs(
    refs: list[DraftSourceRef], sources: list[SourceExcerpt]
) -> tuple[list[VerifiedSourceRef], int]:
    verified_refs: list[VerifiedSourceRef] = []
    invalid = 0
    for ref in refs:
        verified, is_invalid = _verify_ref(ref, sources)
        if is_invalid:
            invalid += 1
        elif verified is not None:
            verified_refs.append(verified)
    return verified_refs, invalid


def _verify_claim(
    claim: DraftClaim,
    claim_type: str,
    sources: list[SourceExcerpt],
) -> tuple[VerifiedClaim, int]:
    verified_refs, invalid = _verify_refs(claim.source_refs, sources)
    return (
        VerifiedClaim(
            claim=claim.claim,
            claim_type=claim_type,  # type: ignore[arg-type]
            sources=verified_refs,
            support=_support(verified_refs),  # type: ignore[arg-type]
            confidence=claim.confidence,
        ),
        invalid,
    )


def _verify_entity(
    entity: DraftEntity, sources: list[SourceExcerpt]
) -> tuple[VerifiedEntity, int]:
    verified_refs, invalid = _verify_refs(entity.source_refs, sources)
    return (
        VerifiedEntity(
            name=entity.name,
            entity_type=entity.entity_type,
            role=entity.role,
            sources=verified_refs,
            support=_support(verified_refs),  # type: ignore[arg-type]
            confidence=entity.confidence,
        ),
        invalid,
    )


def _verify_party(
    party: DraftParty, sources: list[SourceExcerpt]
) -> tuple[VerifiedParty, int]:
    verified_refs, invalid = _verify_refs(party.source_refs, sources)
    return (
        VerifiedParty(
            name=party.name,
            role=party.role,
            sources=verified_refs,
            support=_support(verified_refs),  # type: ignore[arg-type]
            confidence=party.confidence,
        ),
        invalid,
    )


def _verify_amount(
    amount: DraftAmount, sources: list[SourceExcerpt]
) -> tuple[VerifiedAmount, int]:
    verified_refs, invalid = _verify_refs(amount.source_refs, sources)
    return (
        VerifiedAmount(
            description=amount.description,
            amount_text=amount.amount_text,
            currency=amount.currency,
            sources=verified_refs,
            support=_support(verified_refs),  # type: ignore[arg-type]
            confidence=amount.confidence,
        ),
        invalid,
    )


def _verify_procedural_event(
    event: DraftProceduralEvent, sources: list[SourceExcerpt]
) -> tuple[VerifiedProceduralEvent, int]:
    verified_refs, invalid = _verify_refs(event.source_refs, sources)
    date_info = normalise_date_text(event.date_text)
    return (
        VerifiedProceduralEvent(
            stage=event.stage,
            description=event.description,
            date_text=event.date_text,
            date_sort_key=date_info.sort_key,
            date_precision=date_info.precision,  # type: ignore[arg-type]
            date_ambiguous=date_info.ambiguous,
            forum=event.forum,
            sources=verified_refs,
            support=_support(verified_refs),  # type: ignore[arg-type]
        ),
        invalid,
    )


def _verify_timeline_event(
    event: DraftTimelineEvent,
    sources: list[SourceExcerpt],
) -> tuple[VerifiedTimelineEvent, int]:
    verified_refs, invalid = _verify_refs(event.source_refs, sources)
    date_info = normalise_date_text(event.date_text)
    return (
        VerifiedTimelineEvent(
            date_text=event.date_text,
            date_sort_key=date_info.sort_key,
            date_precision=date_info.precision,  # type: ignore[arg-type]
            date_ambiguous=date_info.ambiguous,
            date_ambiguity_note=date_info.note,
            event=event.event,
            significance=event.significance,
            sources=verified_refs,
            support=_support(verified_refs),  # type: ignore[arg-type]
        ),
        invalid,
    )


def _verify_chronology_item(
    item: dict, sources: list[SourceExcerpt]
) -> tuple[VerifiedTimelineEvent, int]:
    refs = [
        DraftSourceRef.model_validate(ref)
        for ref in (item.get("source_refs") or [])
        if isinstance(ref, dict)
    ]
    verified_refs, invalid = _verify_refs(refs, sources)
    date_text = str(item.get("date_text", ""))
    date_info = normalise_date_text(date_text)
    return (
        VerifiedTimelineEvent(
            date_text=date_text,
            date_sort_key=str(item.get("date_sort_key") or date_info.sort_key),
            date_precision=str(  # type: ignore[arg-type]
                item.get("date_precision") or date_info.precision
            ),
            date_ambiguous=bool(
                item.get("date_ambiguous", date_info.ambiguous)
            ),
            date_ambiguity_note=(
                str(item.get("date_ambiguity_note"))
                if item.get("date_ambiguity_note")
                else date_info.note
            ),
            event=str(item.get("event", "")),
            significance=str(item.get("significance", "factual")),  # type: ignore[arg-type]
            sources=verified_refs,
            support=_support(verified_refs),  # type: ignore[arg-type]
        ),
        invalid,
    )


def verify_draft(
    draft: CaseAnalysisDraft,
    sources: list[SourceExcerpt],
    *,
    workflow_id: str,
    case_id: str,
    provider_name: str,
    model_name: str,
    is_mock: bool,
    retried: bool = False,
    source_notes: list[str] | None = None,
    evidence: EvidenceAnalysisDraft | None = None,
    chronology: list[dict] | None = None,
    source_stats: dict[str, int] | None = None,
    input_metadata: dict | None = None,
) -> CaseAnalysisResult:
    """Build a verified result from drafts and the real source excerpts."""
    tally: dict[str, list[int]] = {}

    def record(category: str, support: str) -> None:
        bucket = tally.setdefault(category, [0, 0, 0])
        if support == "supported":
            bucket[0] += 1
        elif support == "partially_supported":
            bucket[1] += 1
        else:
            bucket[2] += 1

    facts: list[VerifiedClaim] = []
    legal_issues: list[VerifiedClaim] = []
    inferences: list[VerifiedClaim] = []
    parties: list[VerifiedParty] = []
    entities: list[VerifiedEntity] = []
    amounts: list[VerifiedAmount] = []
    procedural_history: list[VerifiedProceduralEvent] = []
    issue_analysis: list[VerifiedLegalIssue] = []
    evidence_questions: list[VerifiedEvidenceQuestion] = []
    ambiguities: list[VerifiedUncertainty] = []
    timeline: list[VerifiedTimelineEvent] = []
    invalid_refs = 0

    for claim in draft.facts:
        verified, invalid = _verify_claim(claim, "fact", sources)
        facts.append(verified)
        invalid_refs += invalid
        record("facts", verified.support)

    for claim in draft.legal_issues:
        verified, invalid = _verify_claim(claim, "legal_issue", sources)
        legal_issues.append(verified)
        invalid_refs += invalid
        record("legal_issues", verified.support)

    for claim in draft.inferences:
        verified, invalid = _verify_claim(claim, "inference", sources)
        inferences.append(verified)
        invalid_refs += invalid
        record("inferences", verified.support)

    for party in draft.parties:
        verified_party, invalid = _verify_party(party, sources)
        parties.append(verified_party)
        invalid_refs += invalid
        record("parties", verified_party.support)

    for entity in draft.entities:
        verified_entity, invalid = _verify_entity(entity, sources)
        entities.append(verified_entity)
        invalid_refs += invalid
        record("entities", verified_entity.support)

    for amount in draft.amounts:
        verified_amount, invalid = _verify_amount(amount, sources)
        amounts.append(verified_amount)
        invalid_refs += invalid
        record("amounts", verified_amount.support)

    for event in draft.procedural_history:
        verified_event, invalid = _verify_procedural_event(event, sources)
        procedural_history.append(verified_event)
        invalid_refs += invalid
        record("procedural_history", verified_event.support)

    if chronology:
        for item in chronology:
            verified_event, invalid = _verify_chronology_item(item, sources)
            timeline.append(verified_event)
            invalid_refs += invalid
            record("timeline", verified_event.support)
    else:
        for event in draft.timeline:
            verified_event, invalid = _verify_timeline_event(event, sources)
            timeline.append(verified_event)
            invalid_refs += invalid
            record("timeline", verified_event.support)

    if evidence is not None:
        for issue in evidence.legal_issues:
            verified_refs, invalid = _verify_refs(issue.source_refs, sources)
            invalid_refs += invalid
            support = _support(verified_refs)
            issue_analysis.append(
                VerifiedLegalIssue(
                    question=issue.question,
                    why_it_matters=issue.why_it_matters,
                    issue_type=issue.issue_type,
                    sources=verified_refs,
                    support=support,  # type: ignore[arg-type]
                    confidence=issue.confidence,
                )
            )
            record("legal_issues", support)

        for question in evidence.evidence_questions:
            verified_refs, invalid = _verify_refs(question.source_refs, sources)
            invalid_refs += invalid
            support = _support(verified_refs)
            evidence_questions.append(
                VerifiedEvidenceQuestion(
                    question=question.question,
                    why_it_matters=question.why_it_matters,
                    evidence_needed=question.evidence_needed,
                    sources=verified_refs,
                    support=support,  # type: ignore[arg-type]
                )
            )
            record("evidence_questions", support)

        for ambiguity in evidence.ambiguities:
            verified_refs, invalid = _verify_refs(ambiguity.source_refs, sources)
            invalid_refs += invalid
            support = _support(verified_refs)
            ambiguities.append(
                VerifiedUncertainty(
                    statement=ambiguity.statement,
                    reason=ambiguity.reason,
                    severity=ambiguity.severity,
                    sources=verified_refs,
                    support=support,  # type: ignore[arg-type]
                )
            )
            record("ambiguities", support)

        for claim in evidence.inferences:
            verified, invalid = _verify_claim(claim, "inference", sources)
            inferences.append(verified)
            invalid_refs += invalid
            record("inferences", verified.support)

    detected_injection = any(
        source.instruction_like
        or bool(find_instruction_like_text(source.text))
        for source in sources
    )

    notes = list(source_notes or [])
    if source_stats and source_stats.get("duplicate_pages_skipped"):
        notes.append(
            f"{source_stats['duplicate_pages_skipped']} duplicate page(s) were not "
            "sent to the model twice."
        )
    if invalid_refs:
        notes.append(
            f"{invalid_refs} source reference(s) pointed to a document or page "
            "that was not supplied; they were rejected."
        )
    unsupported = sum(bucket[2] for bucket in tally.values())
    partial = sum(bucket[1] for bucket in tally.values())
    if unsupported:
        notes.append(
            f"{unsupported} statement(s) could not be supported by a verified "
            "source quote. Review them before relying on them."
        )
    if partial:
        notes.append(
            f"{partial} statement(s) cite a source but the quote could not be "
            "verified verbatim. Open the source before relying on them."
        )

    ambiguous_dates = sum(1 for event in timeline if event.date_ambiguous)
    if ambiguous_dates:
        notes.append(
            f"{ambiguous_dates} chronology entr{'y' if ambiguous_dates == 1 else 'ies'} "
            "use an ambiguous date; the original wording is preserved."
        )

    all_text = " ".join(
        [c.claim for c in facts]
        + [c.claim for c in legal_issues]
        + [c.claim for c in inferences]
        + [party.name for party in parties]
        + [entity.name for entity in entities]
        + [issue.question for issue in issue_analysis]
        + [question.question for question in evidence_questions]
        + [ambiguity.statement for ambiguity in ambiguities]
    )
    if AUTHORITY_CITATION_PATTERN.search(all_text):
        notes.append(
            "The model mentioned a case-citation-like string. No external legal "
            "database was consulted; it must not be treated as authority."
        )
    if detected_injection:
        notes.append(
            "Instruction-like text was detected in one or more source pages. It "
            "was treated strictly as evidence and ignored as an instruction."
        )

    limitations = list(draft.limitations)
    if evidence is not None:
        limitations.extend(evidence.limitations)
    limitations.extend(STANDARD_LIMITATIONS)
    if source_stats:
        if source_stats.get("short_pages"):
            limitations.append(
                "Some supplied pages contain very little text; they may be scans "
                "or partially extracted pages."
            )
        if source_stats.get("truncated_pages"):
            limitations.append(
                "Some page excerpts were truncated to fit the analysis budget."
            )
        if source_stats.get("ocr_required_documents"):
            limitations.append(
                f"{source_stats['ocr_required_documents']} document(s) appear to "
                "require OCR and were not analysed."
            )
        if source_stats.get("incomplete_extraction_documents"):
            limitations.append(
                f"{source_stats['incomplete_extraction_documents']} document(s) "
                "have incomplete text extraction."
            )
    if is_mock:
        limitations.insert(
            0,
            "Development fixture only — no AI model was called and this is not "
            "AI-generated legal analysis.",
        )

    manifest = [
        SourceManifestEntry(
            source_id=s.source_id,
            document_id=s.document_id,
            document_name=s.document_name,
            page_number=s.page_number,
            truncated=s.truncated,
            short=s.short,
        )
        for s in sources
    ]

    verified_spans = sum(
        1
        for refs in [
            *[claim.sources for claim in facts],
            *[claim.sources for claim in legal_issues],
            *[claim.sources for claim in inferences],
            *[entity.sources for entity in entities],
            *[party.sources for party in parties],
            *[amount.sources for amount in amounts],
            *[event.sources for event in procedural_history],
            *[event.sources for event in timeline],
            *[issue.sources for issue in issue_analysis],
            *[question.sources for question in evidence_questions],
            *[ambiguity.sources for ambiguity in ambiguities],
        ]
        for ref in refs
        if ref.quote_verified
    )
    unverified_quotes = sum(
        1
        for refs in [
            *[claim.sources for claim in facts],
            *[claim.sources for claim in legal_issues],
            *[claim.sources for claim in inferences],
            *[entity.sources for entity in entities],
            *[party.sources for party in parties],
            *[amount.sources for amount in amounts],
            *[event.sources for event in procedural_history],
            *[event.sources for event in timeline],
            *[issue.sources for issue in issue_analysis],
            *[question.sources for question in evidence_questions],
            *[ambiguity.sources for ambiguity in ambiguities],
        ]
        for ref in refs
        if ref.quote and not ref.quote_verified
    )

    categories = [
        VerificationCategoryCount(
            category=category,
            total=sum(bucket),
            supported=bucket[0],
            partially_supported=bucket[1],
            unsupported=bucket[2],
        )
        for category, bucket in tally.items()
    ]
    total_claims = sum(category.total for category in categories)
    supported = sum(category.supported for category in categories)

    stats_model = SourceStats(**{**(source_stats or {})})
    if not stats_model.instruction_like_sources:
        stats_model.instruction_like_sources = sum(
            1 for source in sources if source.instruction_like
        )

    return CaseAnalysisResult(
        workflow_id=workflow_id,
        case_id=case_id,
        generated_at=datetime.now(timezone.utc),
        provider=provider_name,
        model=model_name,
        is_mock=is_mock,
        workflow_version=CASE_INTELLIGENCE_WORKFLOW_VERSION,
        prompt_version=CASE_INTELLIGENCE_PROMPT_VERSION,
        result_schema_version=CASE_INTELLIGENCE_RESULT_SCHEMA_VERSION,
        insufficient_sources=False,
        summary=draft.summary,
        parties=parties,
        entities=entities,
        amounts=amounts,
        facts=facts,
        procedural_history=procedural_history,
        legal_issues=legal_issues,
        issue_analysis=issue_analysis,
        evidence_questions=evidence_questions,
        ambiguities=ambiguities,
        timeline=timeline,
        inferences=inferences,
        unverified_hypotheses=_unique(
            list(draft.unverified_hypotheses)
            + list(evidence.unverified_hypotheses if evidence else []),
            12,
        ),
        missing_information=_unique(
            list(draft.missing_information)
            + list(evidence.missing_information if evidence else []),
            12,
        ),
        limitations=_unique(limitations, 16),
        verification=VerificationSummary(
            total_claims=total_claims,
            supported=supported,
            partially_supported=partial,
            unsupported=unsupported,
            invalid_source_refs=invalid_refs,
            verified_spans=verified_spans,
            unverified_quotes=unverified_quotes,
            retried=retried,
            categories=categories,
            notes=_unique(notes, 16),
        ),
        source_manifest=manifest,
        source_stats=stats_model,
        professional_review_required=True,
        input_metadata=input_metadata or {},
    )


def _feedback_from_result(
    result: CaseAnalysisResult, *, extraction_only: bool = False
) -> list[str]:
    feedback: list[str] = []
    groups = [
        result.parties,
        result.facts,
        result.entities,
        result.amounts,
        result.procedural_history,
        result.timeline,
    ]
    if not extraction_only:
        groups.extend(
            [
                result.issue_analysis,
                result.evidence_questions,
                result.ambiguities,
                result.inferences,
            ]
        )
    for group in groups:
        for item in group:
            if getattr(item, "support", "supported") != "supported":
                text = (
                    getattr(item, "claim", None)
                    or getattr(item, "question", None)
                    or getattr(item, "event", None)
                    or getattr(item, "name", None)
                    or getattr(item, "statement", None)
                    or getattr(item, "description", None)
                    or ""
                )
                if text:
                    feedback.append(str(text)[:240])
    return feedback[:10]


def make_verifier_node(ctx: WorkflowContext):
    async def verifier(state: CaseAnalysisState) -> dict:
        await ctx.report_step("verifier", 86, "Checking every statement against source text")

        draft_data = state.get("extraction_draft") or state.get("draft")
        if not draft_data:
            return {
                "status": "failed",
                "current_step": "invalid_model_output",
                "progress": 100,
                "outcome": "invalid_model_output",
                "errors": [
                    {
                        "code": "invalid_model_output",
                        "message": "The analysis draft was missing.",
                    }
                ],
            }

        try:
            draft = CaseAnalysisDraft.model_validate(draft_data)
            evidence_data = state.get("evidence_draft")
            evidence = (
                EvidenceAnalysisDraft.model_validate(evidence_data)
                if evidence_data
                else None
            )
        except Exception:
            return {
                "status": "failed",
                "current_step": "invalid_model_output",
                "progress": 100,
                "outcome": "invalid_model_output",
                "errors": [
                    {
                        "code": "invalid_model_output",
                        "message": "The analysis draft did not match the schema.",
                    }
                ],
            }

        sources = sources_from_state(state.get("sources") or [])

        retry_count = int(state.get("retry_count", 0))
        result = verify_draft(
            draft,
            sources,
            workflow_id=str(state.get("workflow_id", "")),
            case_id=str(state.get("case_id", "")),
            provider_name=str(state.get("provider_name", "unknown")),
            model_name=str(state.get("model_name", "unknown")),
            is_mock=bool(state.get("is_mock", False)),
            retried=retry_count > 0,
            source_notes=state.get("notes") or [],
            evidence=evidence,
            chronology=state.get("chronology"),
            source_stats=state.get("source_stats") or {},
            input_metadata={
                "source_count": len(sources),
                "documents_analyzed": len(
                    {source.document_id for source in sources}
                ),
                "focus_supplied": bool(
                    (state.get("case_context") or {}).get("focus")
                ),
                "llm_calls": int(state.get("llm_calls", 0)),
                "retry_count": retry_count,
            },
        )

        usage = state.get("token_usage") or {}
        budget_exhausted = bool(state.get("token_budget_exhausted")) or (
            int(usage.get("total", 0)) >= ctx.max_total_tokens
        )

        if (
            (
                result.verification.unsupported > 0
                or result.verification.partially_supported > 0
            )
            and retry_count < ctx.max_verifier_retries
            and not budget_exhausted
        ):
            extraction_categories = {
                "parties",
                "facts",
                "entities",
                "amounts",
                "procedural_history",
                "timeline",
            }
            extraction_issue = any(
                category.total > category.supported
                for category in result.verification.categories
                if category.category in extraction_categories
            )
            target = "case_analyst" if extraction_issue else "evidence_analyst"
            feedback = _feedback_from_result(
                result, extraction_only=extraction_issue
            )
            return {
                "needs_revision": True,
                "retry_count": retry_count + 1,
                "revision_target": target,
                "verification_feedback": feedback,
                "current_step": target,
                "progress": 40 if target == "case_analyst" else 60,
                "result": None,
                "notes": list(state.get("notes") or [])
                + [f"The verifier requested one revision from {target}."],
            }

        return {
            "result": result.model_dump(mode="json"),
            "status": "running",
            "current_step": "finalize",
            "progress": 94,
            "needs_revision": False,
            "revision_target": None,
            "verification_feedback": [],
        }

    return verifier
