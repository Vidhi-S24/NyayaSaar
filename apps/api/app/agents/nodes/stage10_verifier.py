"""Deterministic verifier nodes for Stage 10 (Advocate Mode & Judge/Clerk Mode).

No model is called here. Verifies every Sn (case document) and Rn (retrieved
legal record) source reference, flags invented markers, checks verbatim quotes,
enforces mandatory disclaimers/limitations, and triggers bounded revision when
repairable within budget.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.agents.context import WorkflowContext
from app.agents.nodes.precedent_verifier import (
    _build_retrieved_source_map,
    _verify_authority_ref,
)
from app.agents.nodes.verifier import _support, _unique
from app.agents.schemas import (
    SourceManifestEntry,
    SourceStats,
    VerificationCategoryCount,
    VerificationSummary,
    VerifiedSourceRef,
)
from app.agents.schemas_stage10 import (
    ADVOCATE_PROMPT_VERSION,
    ADVOCATE_RESULT_SCHEMA_VERSION,
    ADVOCATE_WORKFLOW_VERSION,
    JUDGE_PROMPT_VERSION,
    JUDGE_RESULT_SCHEMA_VERSION,
    JUDGE_WORKFLOW_VERSION,
    AdvocateDraft,
    AdvocateResult,
    DraftAdvocateSourceRef,
    JudgeDraft,
    JudgeResult,
    VerifiedAdvocateArgument,
    VerifiedAdvocateGap,
    VerifiedJudgeAuditItem,
)
from app.agents.state import CaseAnalysisState
from app.agents.tools.injection import find_instruction_like_text
from app.agents.tools.sources import SourceExcerpt, sources_from_state

logger = logging.getLogger("nyayasaar.agents.stage10_verifier")

ADVOCATE_REQUIRED_LIMITATIONS = [
    "Arguments derived from uploaded case documents and configured corpus records only.",
    "Research tool only — does not constitute legal advice or replace qualified counsel.",
    "Professional legal review required before any reliance.",
]

JUDGE_REQUIRED_LIMITATIONS = [
    "Audit limited to uploaded case documents and configured corpus records.",
    "Reasoning-audit assistant only — not a judicial decision and not legal advice.",
    "Professional legal review required before any reliance.",
]


def _verify_ref_list(
    raw_refs: list[DraftAdvocateSourceRef],
    doc_sources: list[SourceExcerpt],
    record_map: dict[str, dict],
    rejected: list[str],
) -> list[VerifiedSourceRef]:
    verified: list[VerifiedSourceRef] = []
    for ref in raw_refs:
        if not ref.source_id.strip():
            continue
        vref = _verify_authority_ref(
            ref.source_id,
            ref.quote,
            doc_sources,
            record_map,
            rejected,
        )
        if vref is not None:
            verified.append(vref)
    return verified


def _build_manifest(
    doc_sources: list[SourceExcerpt],
    record_map: dict[str, dict],
) -> tuple[list[SourceManifestEntry], list[str], int]:
    injection_notes: list[str] = []
    flagged_count = 0
    manifest: list[SourceManifestEntry] = []
    for src in doc_sources:
        flags = find_instruction_like_text(src.text)
        if flags:
            flagged_count += 1
            injection_notes.append(
                f"Source {src.source_id} ({src.document_name} p.{src.page_number}) "
                "contained instruction-like text that was treated as untrusted."
            )
        manifest.append(
            SourceManifestEntry(
                source_id=src.source_id,
                document_id=src.document_id,
                document_name=src.document_name,
                page_number=src.page_number,
                truncated=len(src.text) > 2000,
                short=len(src.text) < 120,
            )
        )
    for rid, rec in record_map.items():
        manifest.append(
            SourceManifestEntry(
                source_id=rid,
                document_id=str(rec.get("id", rid)),
                document_name=f"{rec.get('title', rid)} ({rec.get('citation', '')})".strip(),
                page_number=0,
                truncated=False,
                short=False,
            )
        )
    return manifest, injection_notes, flagged_count


def _tally_support(counts: dict[str, int], support: str) -> None:
    counts[support] = counts.get(support, 0) + 1


def _normalise_authority(value: str) -> str:
    return " ".join(str(value or "").casefold().split())


def _verify_authority_refs(
    refs: list[str],
    record_map: dict[str, dict],
    rejected_authorities: list[str],
) -> list[str]:
    """Keep only authority strings that match a retrieved corpus record.

    The model is never allowed to introduce a free-text citation that was not
    present in the configured corpus. Unknown strings are dropped and recorded
    for the verification notes.
    """
    allowed: set[str] = set()
    for rec in record_map.values():
        for key in ("citation", "title"):
            value = _normalise_authority(str(rec.get(key) or ""))
            if value:
                allowed.add(value)
    verified: list[str] = []
    for ref in refs:
        cleaned = str(ref or "").strip()
        if not cleaned:
            continue
        if _normalise_authority(cleaned) in allowed:
            verified.append(cleaned)
        else:
            rejected_authorities.append(cleaned)
    return verified


# ---------------------------------------------------------------------------
# Advocate Mode Verifier
# ---------------------------------------------------------------------------


def verify_advocate_draft(
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
                    "message": "The Advocate Mode analyst did not return a structured draft.",
                }
            ],
        }

    draft = AdvocateDraft.model_validate(raw_draft)
    doc_sources = sources_from_state(state.get("sources") or [])
    record_map = _build_retrieved_source_map(state)
    rejected: list[str] = []
    rejected_authorities: list[str] = []
    counts = {
        "supported": 0,
        "partially_supported": 0,
        "unsupported": 0,
    }

    def _verify_args(items, prefix: str) -> list[VerifiedAdvocateArgument]:
        out: list[VerifiedAdvocateArgument] = []
        for idx, item in enumerate(items, start=1):
            supp_refs = _verify_ref_list(
                item.supporting_sources, doc_sources, record_map, rejected
            )
            opp_refs = _verify_ref_list(
                item.opposing_sources, doc_sources, record_map, rejected
            )
            support = _support(supp_refs)
            _tally_support(counts, support)

            tier = item.tier
            gap_flag = item.evidentiary_gap
            gap_desc = item.gap_description
            if not supp_refs:
                tier = "speculative"
                gap_flag = True
                if not gap_desc:
                    gap_desc = "No verified supporting source passage was linked."

            out.append(
                VerifiedAdvocateArgument(
                    argument_id=item.argument_id or f"{prefix}{idx}",
                    side=item.side,
                    issue=item.issue,
                    claim=item.claim,
                    reasoning=item.reasoning,
                    tier=tier,
                    strength=item.strength if supp_refs else "low",
                    supporting_sources=supp_refs,
                    opposing_sources=opp_refs,
                    authority_refs=_verify_authority_refs(
                        item.authority_refs, record_map, rejected_authorities
                    ),
                    counterarguments=list(item.counterarguments),
                    evidentiary_gap=gap_flag,
                    gap_description=gap_desc,
                    support=support,
                )
            )
        return out

    claimant_args = _verify_args(draft.claimant_arguments, "A-C")
    respondent_args = _verify_args(draft.respondent_arguments, "A-R")

    gaps: list[VerifiedAdvocateGap] = []
    for g in draft.evidentiary_gaps:
        refs = _verify_ref_list(g.source_refs, doc_sources, record_map, rejected)
        gaps.append(
            VerifiedAdvocateGap(
                description=g.description,
                missing_evidence_type=g.missing_evidence_type,
                affected_claim=g.affected_claim,
                source_refs=refs,
            )
        )

    retries = int(state.get("verifier_retries") or 0)
    llm_calls = int(state.get("llm_calls") or 0)
    max_calls = int(state.get("max_llm_calls") or 4)
    rejected_unique = _unique(rejected)

    if (
        rejected_unique
        and retries < max_verifier_retries
        and llm_calls < max_calls
        and not budget_exceeded
        and not bool(state.get("is_mock", False))
    ):
        feedback = [
            f"Unknown source ID(s) rejected: {', '.join(rejected_unique)}. "
            "Use ONLY provided S1..Sn or R1..Rn markers."
        ]
        return {
            "verifier_retries": retries + 1,
            "revision_needed": True,
            "revision_target": "advocate_analyst",
            "revision_feedback": feedback,
            "current_step": "advocate_verifier",
            "progress": 75,
        }

    manifest, injection_notes, flagged_count = _build_manifest(doc_sources, record_map)
    notes = list(state.get("notes") or []) + injection_notes
    if rejected_unique:
        notes.append(
            f"Dropped {len(rejected_unique)} unknown source marker(s): {', '.join(rejected_unique)}."
        )
    if rejected_authorities:
        notes.append(
            "Dropped "
            f"{len(rejected_authorities)} unverified authority reference(s) not found "
            f"in the configured corpus: {', '.join(_unique(rejected_authorities))}."
        )

    total_claims = sum(counts.values())
    all_refs = [
        ref
        for arg in [*claimant_args, *respondent_args]
        for ref in [*arg.supporting_sources, *arg.opposing_sources]
    ]
    verification = VerificationSummary(
        total_claims=total_claims,
        supported=counts["supported"],
        partially_supported=counts["partially_supported"],
        unsupported=counts["unsupported"],
        invalid_source_refs=len(rejected_unique),
        verified_spans=sum(1 for ref in all_refs if ref.quote_verified),
        unverified_quotes=sum(1 for ref in all_refs if not ref.quote_verified),
        categories=[
            VerificationCategoryCount(
                category="claimant_arguments",
                total=len(claimant_args),
                supported=sum(1 for a in claimant_args if a.support == "supported"),
                partially_supported=sum(
                    1 for a in claimant_args if a.support == "partially_supported"
                ),
                unsupported=sum(
                    1 for a in claimant_args if a.support == "unsupported"
                ),
            ),
            VerificationCategoryCount(
                category="respondent_arguments",
                total=len(respondent_args),
                supported=sum(1 for a in respondent_args if a.support == "supported"),
                partially_supported=sum(
                    1 for a in respondent_args if a.support == "partially_supported"
                ),
                unsupported=sum(
                    1 for a in respondent_args if a.support == "unsupported"
                ),
            ),
        ],
        notes=_unique(notes),
    )

    limitations = list(draft.limitations or [])
    for req in ADVOCATE_REQUIRED_LIMITATIONS:
        if req not in limitations:
            limitations.append(req)

    stats = SourceStats(**(state.get("source_stats") or {}))
    case_ctx = state.get("case_context") or {}
    preferred_side = str(case_ctx.get("preferred_side") or "both")
    if preferred_side not in ("both", "claimant", "respondent"):
        preferred_side = "both"

    result = AdvocateResult(
        workflow_id=str(state.get("workflow_id", "")),
        case_id=str(state.get("case_id", "")),
        generated_at=datetime.now(timezone.utc),
        provider=str(state.get("provider_name", "none")),
        model=str(state.get("model_name", "none")),
        is_mock=bool(state.get("is_mock", False)),
        workflow_version=ADVOCATE_WORKFLOW_VERSION,
        prompt_version=ADVOCATE_PROMPT_VERSION,
        result_schema_version=ADVOCATE_RESULT_SCHEMA_VERSION,
        insufficient_sources=False,
        preferred_side=preferred_side,  # type: ignore[arg-type]
        selected_issue=draft.selected_issue,
        summary=draft.summary or "No summary produced.",
        relevant_facts=list(draft.relevant_facts),
        claimant_arguments=claimant_args,
        respondent_arguments=respondent_args,
        evidentiary_gaps=gaps,
        unresolved_questions=list(draft.unresolved_questions),
        strengths=list(draft.strengths),
        weaknesses=list(draft.weaknesses),
        verification=verification,
        source_manifest=manifest,
        source_stats=stats,
        limitations=limitations,
        professional_review_required=True,
        input_metadata={
            "source_count": len(doc_sources),
            "retrieved_record_count": len(record_map),
            "documents_analyzed": int(stats.documents_analyzed),
            "preferred_side": preferred_side,
        },
    )

    return {
        "result": result.model_dump(mode="json"),
        "revision_needed": False,
        "current_step": "advocate_verifier",
        "progress": 90,
    }


def make_advocate_verifier_node(ctx: WorkflowContext):
    async def advocate_verifier(state: CaseAnalysisState) -> dict:
        await ctx.report_step(
            "advocate_verifier",
            85,
            "Verifying argument source references and evidentiary gaps",
        )
        return verify_advocate_draft(
            state,
            max_verifier_retries=ctx.settings.agent_max_verifier_retries,
        )

    return advocate_verifier


# ---------------------------------------------------------------------------
# Judge / Clerk Mode Verifier
# ---------------------------------------------------------------------------


def verify_judge_draft(
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
                    "message": "The Judge/Clerk analyst did not return a structured draft.",
                }
            ],
        }

    draft = JudgeDraft.model_validate(raw_draft)
    doc_sources = sources_from_state(state.get("sources") or [])
    record_map = _build_retrieved_source_map(state)
    rejected: list[str] = []
    counts = {
        "supported": 0,
        "partially_supported": 0,
        "unsupported": 0,
    }

    def _verify_items(items, prefix: str) -> list[VerifiedJudgeAuditItem]:
        out: list[VerifiedJudgeAuditItem] = []
        for idx, item in enumerate(items, start=1):
            refs = _verify_ref_list(item.source_refs, doc_sources, record_map, rejected)
            support = _support(refs)
            _tally_support(counts, support)
            out.append(
                VerifiedJudgeAuditItem(
                    audit_id=item.audit_id or f"{prefix}{idx}",
                    item=item.item,
                    finding=item.finding,
                    status=item.status,
                    severity=item.severity,
                    opposing_considered=item.opposing_considered,
                    source_refs=refs,
                    support=support,
                )
            )
        return out

    issue_coverage = _verify_items(draft.issue_coverage, "J-IC")
    reasoning_consistency = _verify_items(draft.reasoning_consistency, "J-RC")
    source_support_audit = _verify_items(draft.source_support_audit, "J-SS")
    citation_integrity = _verify_items(draft.citation_integrity, "J-CI")
    opposing_audit = _verify_items(draft.opposing_consideration_audit, "J-OC")
    unresolved_questions = _verify_items(draft.unresolved_questions, "J-UQ")

    retries = int(state.get("verifier_retries") or 0)
    llm_calls = int(state.get("llm_calls") or 0)
    max_calls = int(state.get("max_llm_calls") or 4)
    rejected_unique = _unique(rejected)

    if (
        rejected_unique
        and retries < max_verifier_retries
        and llm_calls < max_calls
        and not budget_exceeded
        and not bool(state.get("is_mock", False))
    ):
        feedback = [
            f"Unknown source ID(s) rejected: {', '.join(rejected_unique)}. "
            "Use ONLY provided S1..Sn or R1..Rn markers."
        ]
        return {
            "verifier_retries": retries + 1,
            "revision_needed": True,
            "revision_target": "judge_analyst",
            "revision_feedback": feedback,
            "current_step": "judge_verifier",
            "progress": 75,
        }

    manifest, injection_notes, flagged_count = _build_manifest(doc_sources, record_map)
    notes = list(state.get("notes") or []) + injection_notes
    if rejected_unique:
        notes.append(
            f"Dropped {len(rejected_unique)} unknown source marker(s): {', '.join(rejected_unique)}."
        )

    def _cat_count(
        category: str, items: list[VerifiedJudgeAuditItem]
    ) -> VerificationCategoryCount:
        return VerificationCategoryCount(
            category=category,
            total=len(items),
            supported=sum(1 for i in items if i.support == "supported"),
            partially_supported=sum(1 for i in items if i.support == "partially_supported"),
            unsupported=sum(1 for i in items if i.support == "unsupported"),
        )

    all_refs = [
        ref
        for items in (
            issue_coverage,
            reasoning_consistency,
            source_support_audit,
            citation_integrity,
            opposing_audit,
            unresolved_questions,
        )
        for item in items
        for ref in item.source_refs
    ]
    verification = VerificationSummary(
        total_claims=sum(counts.values()),
        supported=counts["supported"],
        partially_supported=counts["partially_supported"],
        unsupported=counts["unsupported"],
        invalid_source_refs=len(rejected_unique),
        verified_spans=sum(1 for ref in all_refs if ref.quote_verified),
        unverified_quotes=sum(1 for ref in all_refs if not ref.quote_verified),
        categories=[
            _cat_count("issue_coverage", issue_coverage),
            _cat_count("reasoning_consistency", reasoning_consistency),
            _cat_count("source_support_audit", source_support_audit),
            _cat_count("citation_integrity", citation_integrity),
            _cat_count("opposing_consideration_audit", opposing_audit),
            _cat_count("unresolved_questions", unresolved_questions),
        ],
        notes=_unique(notes),
    )

    limitations = list(draft.limitations or [])
    for req in JUDGE_REQUIRED_LIMITATIONS:
        if req not in limitations:
            limitations.append(req)

    stats = SourceStats(**(state.get("source_stats") or {}))
    result = JudgeResult(
        workflow_id=str(state.get("workflow_id", "")),
        case_id=str(state.get("case_id", "")),
        generated_at=datetime.now(timezone.utc),
        provider=str(state.get("provider_name", "none")),
        model=str(state.get("model_name", "none")),
        is_mock=bool(state.get("is_mock", False)),
        workflow_version=JUDGE_WORKFLOW_VERSION,
        prompt_version=JUDGE_PROMPT_VERSION,
        result_schema_version=JUDGE_RESULT_SCHEMA_VERSION,
        insufficient_sources=False,
        summary=draft.summary or "No audit summary produced.",
        issue_coverage=issue_coverage,
        reasoning_consistency=reasoning_consistency,
        source_support_audit=source_support_audit,
        citation_integrity=citation_integrity,
        opposing_consideration_audit=opposing_audit,
        unresolved_questions=unresolved_questions,
        overall_assessment=draft.overall_assessment,
        verification=verification,
        source_manifest=manifest,
        source_stats=stats,
        limitations=limitations,
        professional_review_required=True,
        input_metadata={
            "source_count": len(doc_sources),
            "retrieved_record_count": len(record_map),
            "documents_analyzed": int(stats.documents_analyzed),
        },
    )

    return {
        "result": result.model_dump(mode="json"),
        "revision_needed": False,
        "current_step": "judge_verifier",
        "progress": 90,
    }


def make_judge_verifier_node(ctx: WorkflowContext):
    async def judge_verifier(state: CaseAnalysisState) -> dict:
        await ctx.report_step(
            "judge_verifier",
            85,
            "Verifying audit source references and citation integrity",
        )
        return verify_judge_draft(
            state,
            max_verifier_retries=ctx.settings.agent_max_verifier_retries,
        )

    return judge_verifier
