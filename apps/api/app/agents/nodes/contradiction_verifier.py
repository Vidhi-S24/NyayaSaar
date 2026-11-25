"""Deterministic verifier node for Stage 8 — Contradiction & Gap Hunter.

No model is called here. Checks every finding's Side A and Side B source
references and timeline entries against actual extracted document excerpts,
assigns quote spans, flags invented source markers or authority-like citations,
and triggers bounded revision if unsupported items can be repaired within budget.
"""

from __future__ import annotations

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
    SourceManifestEntry,
    SourceStats,
    VerificationCategoryCount,
    VerificationSummary,
    VerifiedSourceRef,
    VerifiedTimelineEvent,
)
from app.agents.schemas_contradiction import (
    CONTRADICTION_PROMPT_VERSION,
    CONTRADICTION_RESULT_SCHEMA_VERSION,
    CONTRADICTION_WORKFLOW_VERSION,
    ContradictionAnalysisDraft,
    ContradictionResult,
    VerifiedContradictionFinding,
)
from app.agents.state import CaseAnalysisState
from app.agents.tools.dates import normalise_date_text
from app.agents.tools.injection import find_instruction_like_text
from app.agents.tools.sources import sources_from_state

STANDARD_CONTRADICTION_LIMITATIONS = [
    "Potential contradictions and inconsistencies are analytical flags for human review, not proof of dishonesty or wrongdoing.",
    "Analysis is limited to the selected uploaded documents; missing or poor OCR pages may hide relevant context.",
    "AI-assisted output requires independent professional legal verification.",
]


def _verify_refs(
    raw_refs,
    sources,
    rejected: list[str],
) -> list[VerifiedSourceRef]:
    verified: list[VerifiedSourceRef] = []
    for ref in raw_refs:
        vref, was_unknown = _verify_ref(ref, sources)
        if was_unknown:
            rejected.append(_normalise_source_id(ref.source_id))
        elif vref is not None:
            verified.append(vref)
    return verified


def verify_contradiction_draft(
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
                    "message": "Contradiction verification had no draft to check.",
                }
            ],
        }

    draft = ContradictionAnalysisDraft.model_validate(raw_draft)
    sources = sources_from_state(state.get("sources") or [])
    rejected_markers: list[str] = []
    notes = list(state.get("notes") or [])

    verified_findings: list[VerifiedContradictionFinding] = []
    for idx, item in enumerate(draft.findings, start=1):
        fid = (item.finding_id or "").strip() or f"F{idx}"
        side_a = _verify_refs(item.side_a_refs, sources, rejected_markers)
        side_b = _verify_refs(item.side_b_refs, sources, rejected_markers)
        combined = side_a + side_b
        support = _support(combined)

        if item.date_text:
            dt = normalise_date_text(item.date_text)
            sort_key = dt.sort_key
        else:
            sort_key = "9999-99-99"

        verified_findings.append(
            VerifiedContradictionFinding(
                finding_id=fid,
                category=item.category,
                dimension=item.dimension,
                severity=item.severity,
                title=item.title,
                observed_evidence_summary=item.observed_evidence_summary,
                model_interpretation=item.model_interpretation,
                side_a_label=item.side_a_label,
                side_a_sources=side_a,
                side_b_label=item.side_b_label,
                side_b_sources=side_b,
                support=support,  # type: ignore[arg-type]
                issue_tag=item.issue_tag,
                date_text=item.date_text,
                date_sort_key=sort_key,
            )
        )

    verified_timeline: list[VerifiedTimelineEvent] = []
    for ev in draft.timeline:
        refs = _verify_refs(ev.source_refs, sources, rejected_markers)
        dt = normalise_date_text(ev.date_text)
        verified_timeline.append(
            VerifiedTimelineEvent(
                date_text=ev.date_text,
                date_sort_key=dt.sort_key,
                date_precision=dt.precision,
                date_ambiguous=dt.ambiguous,
                date_ambiguity_note=dt.note,
                event=ev.event,
                significance=ev.significance,
                sources=refs,
                support=_support(refs),  # type: ignore[arg-type]
            )
        )
    verified_timeline.sort(key=lambda e: (e.date_sort_key, e.date_text))

    # Flag any authority-like citations generated by the model
    all_text = " ".join(
        [draft.summary]
        + [
            f"{f.title} {f.observed_evidence_summary} {f.model_interpretation}"
            for f in verified_findings
        ]
    )
    if AUTHORITY_CITATION_PATTERN.search(all_text):
        notes.append(
            "Output contained reporter-style citation patterns; external "
            "legal authorities were not consulted in this workflow."
        )

    if rejected_markers:
        notes.append(
            "Ignored unknown source marker(s): "
            + ", ".join(sorted(set(rejected_markers)))
        )

    injection_hits = [
        f"{s.source_id} ({s.document_name} p.{s.page_number})"
        for s in sources
        if find_instruction_like_text(s.text)
    ]
    if injection_hits:
        notes.append(
            "Instruction-like text detected in uploaded source(s) and treated "
            "as untrusted data: " + ", ".join(injection_hits[:4])
        )

    unsupported_findings = [
        f for f in verified_findings if f.support == "unsupported"
    ]
    retry_count = int(state.get("retry_count", 0))
    can_retry = (
        retry_count < max_verifier_retries
        and not bool(state.get("token_budget_exhausted"))
        and not budget_exceeded
        and not bool(state.get("is_mock"))
    )
    if (rejected_markers or unsupported_findings) and can_retry:
        feedback: list[str] = []
        if rejected_markers:
            feedback.append(
                "Do not invent source markers; only cite S1..Sn from the prompt."
            )
        if unsupported_findings:
            feedback.append(
                "Attach valid source_refs with verbatim quotes (<=160 chars) for findings: "
                + ", ".join(f.finding_id for f in unsupported_findings[:4])
            )
        return {
            "retry_count": retry_count + 1,
            "needs_revision": True,
            "revision_target": "contradiction_analyst",
            "verification_feedback": feedback,
            "notes": _unique(notes),
            "status": "running",
            "current_step": "contradiction_analyst",
            "progress": 60,
        }

    # Build verification summary
    f_supported = sum(1 for f in verified_findings if f.support == "supported")
    f_partial = sum(1 for f in verified_findings if f.support == "partially_supported")
    f_unsupported = len(unsupported_findings)
    cat_counts = VerificationCategoryCount(
        category="findings",
        total=len(verified_findings),
        supported=f_supported,
        partially_supported=f_partial,
        unsupported=f_unsupported,
    )
    t_supported = sum(1 for e in verified_timeline if e.support == "supported")
    t_partial = sum(1 for e in verified_timeline if e.support == "partially_supported")
    t_unsupported = sum(1 for e in verified_timeline if e.support == "unsupported")
    tl_counts = VerificationCategoryCount(
        category="timeline",
        total=len(verified_timeline),
        supported=t_supported,
        partially_supported=t_partial,
        unsupported=t_unsupported,
    )
    all_refs = [
        ref
        for f in verified_findings
        for ref in (f.side_a_sources + f.side_b_sources)
    ] + [ref for ev in verified_timeline for ref in ev.sources]
    verification = VerificationSummary(
        total_claims=cat_counts.total + tl_counts.total,
        supported=f_supported + t_supported,
        partially_supported=f_partial + t_partial,
        unsupported=f_unsupported + t_unsupported,
        invalid_source_refs=len(rejected_markers),
        verified_spans=sum(1 for r in all_refs if r.span_start is not None),
        unverified_quotes=sum(1 for r in all_refs if r.quote and not r.quote_verified),
        retried=retry_count > 0,
        categories=[cat_counts, tl_counts],
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
        for s in sources
    ]
    stats = SourceStats(**(state.get("source_stats") or {}))
    case_ctx = state.get("case_context") or {}

    result = ContradictionResult(
        workflow_id=str(state.get("workflow_id", "")),
        case_id=str(state.get("case_id", "")),
        generated_at=datetime.now(timezone.utc),
        provider=str(state.get("provider_name", "none")),
        model=str(state.get("model_name", "none")),
        is_mock=bool(state.get("is_mock", False)),
        workflow_version=CONTRADICTION_WORKFLOW_VERSION,
        prompt_version=CONTRADICTION_PROMPT_VERSION,
        result_schema_version=CONTRADICTION_RESULT_SCHEMA_VERSION,
        insufficient_sources=False,
        summary=draft.summary,
        findings=verified_findings,
        timeline=verified_timeline,
        missing_information=_unique(draft.missing_information),
        limitations=_unique(
            list(draft.limitations) + STANDARD_CONTRADICTION_LIMITATIONS
        ),
        verification=verification,
        source_manifest=manifest,
        source_stats=stats,
        professional_review_required=True,
        input_metadata={
            "source_count": len(sources),
            "documents_analyzed": int(stats.documents_analyzed),
            "focus_supplied": bool(case_ctx.get("focus")),
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


def make_contradiction_verifier_node(ctx: WorkflowContext):
    async def contradiction_verifier(state: CaseAnalysisState) -> dict:
        await ctx.report_step(
            "contradiction_verifier",
            85,
            "Verifying source passages, dates, and spans",
        )
        return verify_contradiction_draft(
            state,
            max_verifier_retries=ctx.max_verifier_retries,
            budget_exceeded=ctx.budget_exceeded_code(state) is not None,
        )

    return contradiction_verifier
