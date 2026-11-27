"""Deterministic verifier node for Stage 9 — Precedent Explorer.

No model is called here. Verifies every DraftAuthority's source_id against
extracted document sources and retrieved legal records, flags invented markers,
checks citation format, builds VerificationSummary, and triggers bounded revision
if unsupported items can be repaired within budget.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from app.agents.context import WorkflowContext
from app.agents.nodes.verifier import (
    AUTHORITY_CITATION_PATTERN,
    _normalise_source_id,
    _support,
    _unique,
    _verify_ref,
)
from app.agents.schemas import (
    DraftSourceRef,
    SourceManifestEntry,
    SourceStats,
    VerificationCategoryCount,
    VerificationSummary,
    VerifiedSourceRef,
)
from app.agents.schemas_precedent import (
    PRECEDENT_PROMPT_VERSION,
    PRECEDENT_RESULT_SCHEMA_VERSION,
    PRECEDENT_WORKFLOW_VERSION,
    PrecedentResult,
    PrecedentSearchDraft,
    VerifiedAuthority,
    VerifiedCitationPair,
    VerifiedConflict,
)
from app.agents.state import CaseAnalysisState
from app.agents.tools.injection import find_instruction_like_text
from app.agents.tools.sources import SourceExcerpt, sources_from_state

logger = logging.getLogger("nyayasaar.agents.precedent_verifier")

STANDARD_PRECEDENT_LIMITATIONS = [
    "AI-assisted legal research requires independent professional verification.",
    "Authorities sourced from configured corpus only; corpus coverage may be incomplete.",
    "Potential conflicts are analytical flags for human review — not legal determinations.",
    "Fixture authorities are NOT real legal authorities and must NOT be cited.",
]

# Pattern to match retrieved record markers R1, R2…
_RECORD_MARKER_RE = re.compile(r"^[Rr]\d{1,3}$")


def _build_retrieved_source_map(state: CaseAnalysisState) -> dict[str, dict]:
    """Build an Rn→record dict from the retrieved_records stored in case_context."""
    retrieved = (state.get("case_context") or {}).get("retrieved_records") or []
    return {f"R{idx}": rec for idx, rec in enumerate(retrieved, start=1)}


def _verify_authority_ref(
    source_id: str,
    quote: str,
    doc_sources: list[SourceExcerpt],
    record_map: dict[str, dict],
    rejected: list[str],
) -> VerifiedSourceRef | None:
    """Verify a source reference — either a document source (Sn) or a retrieved record (Rn)."""
    norm = _normalise_source_id(source_id)
    if _RECORD_MARKER_RE.match(norm):
        # Retrieved legal record reference
        rec = record_map.get(norm)
        if rec is None:
            rejected.append(norm)
            return None
        summary_text = str(rec.get("summary") or "").casefold()
        quote_clean = quote.strip()[:160]
        quote_verified = (
            True
            if not quote_clean
            else quote_clean.casefold() in summary_text
        )
        return VerifiedSourceRef(
            source_id=norm,
            document_id=str(rec.get("id", "")),
            document_name=rec.get("title", norm),
            page_number=0,
            quote=quote_clean,
            quote_verified=quote_verified,
            span_start=None,
            span_end=None,
        )
    else:
        # Document source reference (Sn)
        draft_ref = DraftSourceRef(source_id=source_id, quote=quote)
        vref, was_unknown = _verify_ref(draft_ref, doc_sources)
        if was_unknown:
            rejected.append(norm)
            return None
        return vref


def verify_precedent_draft(
    state: CaseAnalysisState,
    *,
    max_verifier_retries: int = 1,
    budget_exceeded: bool = False,
) -> dict:
    raw_draft = state.get("draft")
    if not raw_draft:
        return {
            "status": "failed",
            "current_step": "verifier_missing_draft",
            "progress": 100,
            "outcome": "invalid_model_output",
            "errors": [
                {
                    "code": "invalid_model_output",
                    "message": "Precedent verification had no draft to check.",
                }
            ],
        }

    draft = PrecedentSearchDraft.model_validate(raw_draft)
    doc_sources = sources_from_state(state.get("sources") or [])
    record_map = _build_retrieved_source_map(state)
    rejected_markers: list[str] = []
    notes = list(state.get("notes") or [])

    # --- Verify authorities ---
    verified_authorities: list[VerifiedAuthority] = []
    for idx, auth in enumerate(draft.authorities, start=1):
        auth_id = f"A{idx}"
        vref = _verify_authority_ref(
            auth.source_id,
            "",  # no quote needed for authority provenance check
            doc_sources,
            record_map,
            rejected_markers,
        )
        support = _support([vref] if vref else [])
        verified_authorities.append(
            VerifiedAuthority(
                authority_id=auth_id,
                citation_text=auth.citation_text,
                title=auth.title,
                court=auth.court,
                jurisdiction=auth.jurisdiction,
                decision_date=auth.decision_date,
                holding_summary=auth.holding_summary,
                source_id=auth.source_id,
                source_provider=auth.source_provider,
                is_fixture=auth.is_fixture,
                relevance_note=auth.relevance_note,
                verified_ref=vref,
                support=support,  # type: ignore[arg-type]
            )
        )

    # --- Verify citation pairs ---
    verified_pairs: list[VerifiedCitationPair] = []
    for pair in draft.citation_pairs:
        vref = (
            _verify_authority_ref(
                pair.source_ref.source_id,
                pair.source_ref.quote or "",
                doc_sources,
                record_map,
                rejected_markers,
            )
            if pair.source_ref is not None
            else None
        )
        support = _support([vref] if vref else [])
        verified_pairs.append(
            VerifiedCitationPair(
                from_citation=pair.from_citation,
                to_citation=pair.to_citation,
                relationship_type=pair.relationship_type,
                supporting_passage=pair.supporting_passage,
                confidence=pair.confidence,
                verified_ref=vref,
                support=support,  # type: ignore[arg-type]
            )
        )

    # --- Verify conflicts ---
    verified_conflicts: list[VerifiedConflict] = []
    for conflict in draft.potential_conflicts:
        vref_a = (
            _verify_authority_ref(
                conflict.source_a_ref.source_id,
                conflict.source_a_ref.quote or "",
                doc_sources,
                record_map,
                rejected_markers,
            )
            if conflict.source_a_ref is not None
            else None
        )
        vref_b = (
            _verify_authority_ref(
                conflict.source_b_ref.source_id,
                conflict.source_b_ref.quote or "",
                doc_sources,
                record_map,
                rejected_markers,
            )
            if conflict.source_b_ref is not None
            else None
        )
        support = _support([r for r in [vref_a, vref_b] if r is not None])
        verified_conflicts.append(
            VerifiedConflict(
                title=conflict.title,
                interpretation_a=conflict.interpretation_a,
                interpretation_b=conflict.interpretation_b,
                source_a_verified=vref_a,
                source_b_verified=vref_b,
                model_note=conflict.model_note,
                support=support,  # type: ignore[arg-type]
            )
        )

    # --- Check for authority citation pattern hallucination ---
    all_text = " ".join(
        [draft.summary]
        + [a.holding_summary for a in draft.authorities]
        + [c.model_note for c in draft.potential_conflicts]
    )
    if AUTHORITY_CITATION_PATTERN.search(all_text):
        notes.append(
            "Output contained reporter-style citation patterns; "
            "only retrieved corpus records were consulted in this workflow."
        )

    if rejected_markers:
        notes.append(
            "Ignored unknown source marker(s): "
            + ", ".join(sorted(set(rejected_markers)))
        )

    # --- Injection detection ---
    injection_hits = [
        f"{s.source_id} ({s.document_name} p.{s.page_number})"
        for s in doc_sources
        if find_instruction_like_text(s.text)
    ]
    if injection_hits:
        notes.append(
            "Instruction-like text detected in uploaded source(s) and treated "
            "as untrusted data: " + ", ".join(injection_hits[:4])
        )

    # --- Retry logic ---
    unsupported_auths = [a for a in verified_authorities if a.support == "unsupported" and not a.is_fixture]
    retry_count = int(state.get("retry_count", 0))
    can_retry = (
        retry_count < max_verifier_retries
        and not bool(state.get("token_budget_exhausted"))
        and not budget_exceeded
        and not bool(state.get("is_mock"))
    )
    if (rejected_markers or unsupported_auths) and can_retry:
        feedback: list[str] = []
        if rejected_markers:
            feedback.append(
                "Only cite source markers that exist in the prompt: Sn for case sources, Rn for retrieved records."
            )
        if unsupported_auths:
            feedback.append(
                "Attach valid source_id references for authorities: "
                + ", ".join(a.authority_id for a in unsupported_auths[:4])
            )
        return {
            "retry_count": retry_count + 1,
            "needs_revision": True,
            "revision_target": "precedent_analyst",
            "verification_feedback": feedback,
            "notes": _unique(notes),
            "status": "running",
            "current_step": "precedent_analyst",
            "progress": 60,
        }

    # --- Build verification summary ---
    a_supported = sum(1 for a in verified_authorities if a.support == "supported")
    a_partial = sum(1 for a in verified_authorities if a.support == "partially_supported")
    a_unsupported = sum(1 for a in verified_authorities if a.support == "unsupported")
    auth_counts = VerificationCategoryCount(
        category="authorities",
        total=len(verified_authorities),
        supported=a_supported,
        partially_supported=a_partial,
        unsupported=a_unsupported,
    )
    p_supported = sum(1 for p in verified_pairs if p.support == "supported")
    p_partial = sum(1 for p in verified_pairs if p.support == "partially_supported")
    p_unsupported = sum(1 for p in verified_pairs if p.support == "unsupported")
    pair_counts = VerificationCategoryCount(
        category="citation_pairs",
        total=len(verified_pairs),
        supported=p_supported,
        partially_supported=p_partial,
        unsupported=p_unsupported,
    )
    all_refs = (
        [a.verified_ref for a in verified_authorities if a.verified_ref]
        + [p.verified_ref for p in verified_pairs if p.verified_ref]
        + [c.source_a_verified for c in verified_conflicts if c.source_a_verified]
        + [c.source_b_verified for c in verified_conflicts if c.source_b_verified]
    )
    verification = VerificationSummary(
        total_claims=auth_counts.total + pair_counts.total,
        supported=a_supported + p_supported,
        partially_supported=a_partial + p_partial,
        unsupported=a_unsupported + p_unsupported,
        invalid_source_refs=len(rejected_markers),
        verified_spans=sum(1 for r in all_refs if r.span_start is not None),
        unverified_quotes=sum(1 for r in all_refs if r.quote and not r.quote_verified),
        retried=retry_count > 0,
        categories=[auth_counts, pair_counts],
        notes=_unique(notes),
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
        for s in doc_sources
    ]
    stats = SourceStats(**(state.get("source_stats") or {}))
    case_ctx = state.get("case_context") or {}

    # Determine if corpus was actually configured (retrieved_records present).
    retrieved = case_ctx.get("retrieved_records") or []
    corpus_configured = len(retrieved) > 0

    result = PrecedentResult(
        workflow_id=str(state.get("workflow_id", "")),
        case_id=str(state.get("case_id", "")),
        generated_at=datetime.now(timezone.utc),
        provider=str(state.get("provider_name", "none")),
        model=str(state.get("model_name", "none")),
        is_mock=bool(state.get("is_mock", False)),
        workflow_version=PRECEDENT_WORKFLOW_VERSION,
        prompt_version=PRECEDENT_PROMPT_VERSION,
        result_schema_version=PRECEDENT_RESULT_SCHEMA_VERSION,
        corpus_configured=corpus_configured,
        insufficient_sources=False,
        query_used=str(case_ctx.get("focus") or case_ctx.get("title") or "")[:200],
        authorities=verified_authorities,
        citation_pairs=verified_pairs,
        potential_conflicts=verified_conflicts,
        summary=draft.summary,
        limitations=_unique(list(draft.limitations) + STANDARD_PRECEDENT_LIMITATIONS),
        verification=verification,
        source_manifest=manifest,
        source_stats=stats,
        professional_review_required=True,
        input_metadata={
            "source_count": len(doc_sources),
            "retrieved_records": len(retrieved),
            "documents_analyzed": int(stats.documents_analyzed),
            "focus_supplied": bool(case_ctx.get("focus")),
            "corpus_configured": corpus_configured,
        },
    )

    return {
        "result": result.model_dump(mode="json"),
        "needs_revision": False,
        "revision_target": None,
        "status": "running",
        "current_step": "finalize",
        "progress": 95,
        "outcome": "completed",
        "notes": _unique(notes),
    }


def make_precedent_verifier_node(ctx: WorkflowContext):
    async def precedent_verifier(state: CaseAnalysisState) -> dict:
        await ctx.report_step(
            "precedent_verifier",
            85,
            "Verifying authority references and source passages",
        )
        return verify_precedent_draft(
            state,
            max_verifier_retries=ctx.max_verifier_retries,
            budget_exceeded=ctx.budget_exceeded_code(state) is not None,
        )

    return precedent_verifier
