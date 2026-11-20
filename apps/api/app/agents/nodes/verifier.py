"""Deterministic verifier node.

No model is called here. Every claim is checked against the actual source
excerpts: unknown source markers are rejected, and quotes must be real
substrings of the cited page. Unsupported claims are surfaced, not hidden.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from app.agents.context import WorkflowContext
from app.agents.schemas import (
    CaseAnalysisDraft,
    CaseAnalysisResult,
    DraftClaim,
    DraftSourceRef,
    DraftTimelineEvent,
    SourceManifestEntry,
    VerificationSummary,
    VerifiedClaim,
    VerifiedSourceRef,
    VerifiedTimelineEvent,
)
from app.agents.state import CaseAnalysisState
from app.agents.tools.sources import (
    SourceExcerpt,
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
    "AI-assisted output requires independent professional legal verification.",
]


def _unique(items: list[str], limit: int = 12) -> list[str]:
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


def _verify_ref(ref: DraftSourceRef, sources: list[SourceExcerpt]) -> tuple[VerifiedSourceRef | None, bool]:
    source = resolve_source(sources, _normalise_source_id(ref.source_id))
    if source is None:
        return None, True
    return (
        VerifiedSourceRef(
            source_id=source.source_id,
            document_id=source.document_id,
            document_name=source.document_name,
            page_number=source.page_number,
            quote=ref.quote,
            quote_verified=quote_in_source(ref.quote, source.text),
        ),
        False,
    )


def _support(refs: list[VerifiedSourceRef]) -> str:
    if any(ref.quote_verified for ref in refs):
        return "supported"
    if refs:
        return "partially_supported"
    return "unsupported"


def _verify_claim(
    claim: DraftClaim,
    claim_type: str,
    sources: list[SourceExcerpt],
) -> tuple[VerifiedClaim, int]:
    verified_refs: list[VerifiedSourceRef] = []
    invalid = 0
    for ref in claim.source_refs:
        verified, is_invalid = _verify_ref(ref, sources)
        if is_invalid:
            invalid += 1
        elif verified is not None:
            verified_refs.append(verified)

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


def _verify_timeline_event(
    event: DraftTimelineEvent,
    sources: list[SourceExcerpt],
) -> tuple[VerifiedTimelineEvent, int]:
    verified_refs: list[VerifiedSourceRef] = []
    invalid = 0
    for ref in event.source_refs:
        verified, is_invalid = _verify_ref(ref, sources)
        if is_invalid:
            invalid += 1
        elif verified is not None:
            verified_refs.append(verified)
    return (
        VerifiedTimelineEvent(
            date_text=event.date_text,
            event=event.event,
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
) -> CaseAnalysisResult:
    """Build a verified result from a draft and the real source excerpts."""
    facts: list[VerifiedClaim] = []
    legal_issues: list[VerifiedClaim] = []
    inferences: list[VerifiedClaim] = []
    timeline: list[VerifiedTimelineEvent] = []

    supported = 0
    partial = 0
    unsupported = 0
    invalid_refs = 0

    def tally(claim: VerifiedClaim) -> None:
        nonlocal supported, partial, unsupported
        if claim.support == "supported":
            supported += 1
        elif claim.support == "partially_supported":
            partial += 1
        else:
            unsupported += 1

    for claim in draft.facts:
        verified, invalid = _verify_claim(claim, "fact", sources)
        facts.append(verified)
        invalid_refs += invalid
        tally(verified)

    for claim in draft.legal_issues:
        verified, invalid = _verify_claim(claim, "legal_issue", sources)
        legal_issues.append(verified)
        invalid_refs += invalid
        tally(verified)

    for claim in draft.inferences:
        verified, invalid = _verify_claim(claim, "inference", sources)
        inferences.append(verified)
        invalid_refs += invalid
        tally(verified)

    for event in draft.timeline:
        verified_event, invalid = _verify_timeline_event(event, sources)
        timeline.append(verified_event)
        invalid_refs += invalid
        if verified_event.support == "supported":
            supported += 1
        elif verified_event.support == "partially_supported":
            partial += 1
        else:
            unsupported += 1

    notes = list(source_notes or [])
    if invalid_refs:
        notes.append(
            f"{invalid_refs} source reference(s) pointed to a document or page "
            "that was not supplied; they were rejected."
        )
    if unsupported:
        notes.append(
            f"{unsupported} claim(s) could not be supported by a verified source "
            "quote. Review them before relying on them."
        )

    all_text = " ".join(
        [c.claim for c in facts]
        + [c.claim for c in legal_issues]
        + [c.claim for c in inferences]
    )
    if AUTHORITY_CITATION_PATTERN.search(all_text):
        notes.append(
            "The model mentioned a case-citation-like string. No external legal "
            "database was consulted; it must not be treated as authority."
        )

    limitations = list(draft.limitations)
    limitations.extend(STANDARD_LIMITATIONS)
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
        )
        for s in sources
    ]

    return CaseAnalysisResult(
        workflow_id=workflow_id,
        case_id=case_id,
        generated_at=datetime.now(timezone.utc),
        provider=provider_name,
        model=model_name,
        is_mock=is_mock,
        insufficient_sources=False,
        summary=draft.summary,
        parties=draft.parties,
        facts=facts,
        legal_issues=legal_issues,
        timeline=timeline,
        inferences=inferences,
        unverified_hypotheses=_unique(draft.unverified_hypotheses, 10),
        missing_information=_unique(draft.missing_information, 10),
        limitations=_unique(limitations, 12),
        verification=VerificationSummary(
            total_claims=len(facts) + len(legal_issues) + len(inferences) + len(timeline),
            supported=supported,
            partially_supported=partial,
            unsupported=unsupported,
            invalid_source_refs=invalid_refs,
            retried=retried,
            notes=_unique(notes, 12),
        ),
        source_manifest=manifest,
    )


def _feedback_from_result(result: CaseAnalysisResult) -> list[str]:
    feedback: list[str] = []
    for claim in result.facts + result.legal_issues + result.inferences:
        if claim.support != "supported":
            feedback.append(claim.claim[:240])
    for event in result.timeline:
        if event.support != "supported":
            feedback.append(event.event[:240])
    return feedback[:8]


def make_verifier_node(ctx: WorkflowContext):
    async def verifier(state: CaseAnalysisState) -> dict:
        await ctx.report_step("verifier", 75, "Checking claims against source text")

        draft_data = state.get("draft")
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
            return {
                "needs_revision": True,
                "retry_count": retry_count + 1,
                "verification_feedback": _feedback_from_result(result),
                "current_step": "case_analyst",
                "progress": 60,
                "result": None,
                "notes": list(state.get("notes") or [])
                + ["The verifier requested one revision for unsupported claims."],
            }

        return {
            "result": result.model_dump(mode="json"),
            "status": "running",
            "current_step": "finalize",
            "progress": 90,
            "needs_revision": False,
            "verification_feedback": [],
        }

    return verifier
