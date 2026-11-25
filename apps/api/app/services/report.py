"""Downloadable Case Intelligence report rendering.

Reports are generated from the persisted, verified result. No model is called
and no new facts are introduced. All model/document text is HTML-escaped before
it reaches the document.

The HTML report is a self-contained, print-ready document (use the browser's
"Print / Save as PDF"). Markdown is offered as a durable text export.
"""

from __future__ import annotations

import html
import re
from datetime import timezone

from app.agents.schemas import (
    CaseAnalysisResult,
    VerifiedClaim,
    VerifiedSourceRef,
    VerificationCategoryCount,
)
from app.db.models.case import Case
from app.db.models.workflow import WorkflowRun

SUPPORT_LABELS = {
    "supported": "Supported by source",
    "partially_supported": "Source cited, quote unverified",
    "unsupported": "Unsupported / no verified source",
}


def slugify_filename(value: str, *, max_length: int = 48) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value or "").strip("-").lower()
    if not cleaned:
        cleaned = "case"
    return cleaned[:max_length].rstrip("-")


def report_filename(case: Case, run: WorkflowRun, extension: str) -> str:
    return (
        f"nyayasaar-case-intelligence-{slugify_filename(case.title)}-"
        f"{run.id[:8]}.{extension}"
    )


def _e(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _source_links(refs: list[VerifiedSourceRef]) -> str:
    if not refs:
        return '<span class="muted">No verified source</span>'
    parts = []
    for ref in refs:
        verified = "verified quote" if ref.quote_verified else "quote unverified"
        parts.append(
            f'<span class="source">{_e(ref.document_name)} · p.{ref.page_number} · '
            f"{_e(verified)}</span>"
        )
    return " ".join(parts)


def _badge(support: str) -> str:
    css = {
        "supported": "ok",
        "partially_supported": "warn",
        "unsupported": "bad",
    }.get(support, "muted")
    return f'<span class="badge {css}">{_e(SUPPORT_LABELS.get(support, support))}</span>'


def _claim_list_html(claims: list[VerifiedClaim], *, empty: str) -> str:
    if not claims:
        return f'<p class="muted">{_e(empty)}</p>'
    items = []
    for claim in claims:
        items.append(
            "<li>"
            f'<div class="claim-head"><span>{_e(claim.claim)}</span>{_badge(claim.support)}</div>'
            f'<div class="sources">{_source_links(claim.sources)}</div>'
            "</li>"
        )
    return "<ol>" + "".join(items) + "</ol>"


def _category_rows(categories: list[VerificationCategoryCount]) -> str:
    if not categories:
        return '<tr><td colspan="4" class="muted">No statements were verified.</td></tr>'
    rows = []
    for category in categories:
        label = category.category.replace("_", " ").title()
        rows.append(
            "<tr>"
            f"<td>{_e(label)}</td><td>{category.supported}</td>"
            f"<td>{category.partially_supported}</td><td>{category.unsupported}</td>"
            "</tr>"
        )
    return "".join(rows)


def render_case_report_html(
    case: Case, run: WorkflowRun, result: CaseAnalysisResult
) -> str:
    generated = result.generated_at
    if generated.tzinfo is not None:
        generated = generated.astimezone(timezone.utc)
    generated_text = generated.strftime("%d %B %Y, %H:%M UTC")
    title = f"Case Intelligence Report — {case.title}"

    facts = _claim_list_html(result.facts, empty="No facts were extracted.")
    parties = (
        "<ul>"
        + "".join(
            f"<li><strong>{_e(party.name)}</strong>"
            f"{' · ' + _e(party.role) if party.role else ''} "
            f"{_badge(party.support)}"
            f'<div class="sources">{_source_links(party.sources)}</div></li>'
            for party in result.parties
        )
        + "</ul>"
        if result.parties
        else '<p class="muted">No parties were extracted.</p>'
    )
    entities = (
        "<ul>"
        + "".join(
            f"<li><strong>{_e(entity.name)}</strong> "
            f'<span class="muted">({_e(entity.entity_type.replace("_", " "))}'
            f"{' · ' + _e(entity.role) if entity.role else ''})</span> "
            f"{_badge(entity.support)}<div class=\"sources\">{_source_links(entity.sources)}</div></li>"
            for entity in result.entities
        )
        + "</ul>"
        if result.entities
        else '<p class="muted">No named entities were extracted.</p>'
    )
    amounts = (
        "<ul>"
        + "".join(
            f"<li><strong>{_e(amount.amount_text)}</strong> — {_e(amount.description)} "
            f"{_badge(amount.support)}<div class=\"sources\">{_source_links(amount.sources)}</div></li>"
            for amount in result.amounts
        )
        + "</ul>"
        if result.amounts
        else '<p class="muted">No amounts were extracted.</p>'
    )
    procedural = (
        "<ol>"
        + "".join(
            f"<li><strong>{_e(event.stage)}</strong>"
            f"{' · ' + _e(event.date_text) if event.date_text else ''} "
            f"{_badge(event.support)}<div>{_e(event.description)}</div>"
            f'<div class="sources">{_source_links(event.sources)}</div></li>'
            for event in result.procedural_history
        )
        + "</ol>"
        if result.procedural_history
        else '<p class="muted">No procedural history was extracted.</p>'
    )
    timeline = (
        "<ol class=\"timeline\">"
        + "".join(
            f"<li><div class=\"date\">{_e(event.date_text)}"
            f"{' · ambiguous date' if event.date_ambiguous else ''}</div>"
            f"<div>{_e(event.event)}</div>{_badge(event.support)}"
            f'<div class="sources">{_source_links(event.sources)}</div></li>'
            for event in result.timeline
        )
        + "</ol>"
        if result.timeline
        else '<p class="muted">No dated events were extracted.</p>'
    )
    issues = (
        "<ol>"
        + "".join(
            f"<li><div class=\"claim-head\"><strong>{_e(issue.question)}</strong>{_badge(issue.support)}</div>"
            f"<p>{_e(issue.why_it_matters)}</p>"
            f'<div class="sources">{_source_links(issue.sources)}</div></li>'
            for issue in result.issue_analysis
        )
        + "</ol>"
        if result.issue_analysis
        else '<p class="muted">No potential legal issues were identified.</p>'
    )
    evidence_questions = (
        "<ol>"
        + "".join(
            f"<li><strong>{_e(question.question)}</strong> {_badge(question.support)}"
            f"<p>{_e(question.why_it_matters)}</p>"
            f"<p class=\"muted\"><strong>Evidence needed:</strong> {_e(question.evidence_needed)}</p>"
            f'<div class="sources">{_source_links(question.sources)}</div></li>'
            for question in result.evidence_questions
        )
        + "</ol>"
        if result.evidence_questions
        else '<p class="muted">No evidence questions were identified.</p>'
    )
    ambiguities = (
        "<ol>"
        + "".join(
            f"<li><strong>{_e(item.statement)}</strong> "
            f'<span class="badge warn">{_e(item.severity)} severity</span>'
            f"<p>{_e(item.reason)}</p>"
            f'<div class="sources">{_source_links(item.sources)}</div></li>'
            for item in result.ambiguities
        )
        + "</ol>"
        if result.ambiguities
        else '<p class="muted">No ambiguity was recorded.</p>'
    )
    inferences = _claim_list_html(
        result.inferences, empty="No separate model inferences were recorded."
    )
    hypotheses = (
        "<ul>"
        + "".join(f"<li>{_e(item)}</li>" for item in result.unverified_hypotheses)
        + "</ul>"
        if result.unverified_hypotheses
        else '<p class="muted">None recorded.</p>'
    )
    missing = (
        "<ul>"
        + "".join(f"<li>{_e(item)}</li>" for item in result.missing_information)
        + "</ul>"
        if result.missing_information
        else '<p class="muted">None recorded.</p>'
    )
    limitations = (
        "<ul>"
        + "".join(f"<li>{_e(item)}</li>" for item in result.limitations)
        + "</ul>"
        if result.limitations
        else '<p class="muted">None recorded.</p>'
    )
    notes = (
        "<ul>"
        + "".join(
            f"<li>{_e(item)}</li>"
            for item in [*result.verification.notes, *result.limitations]
        )
        + "</ul>"
    )
    manifest = (
        "<details><summary>Sources supplied to the analysts</summary><ul>"
        + "".join(
            f"<li><code>{_e(source.source_id)}</code> · {_e(source.document_name)} "
            f"· page {source.page_number}"
            f"{' · truncated' if source.truncated else ''}"
            f"{' · short page' if source.short else ''}</li>"
            for source in result.source_manifest
        )
        + "</ul></details>"
        if result.source_manifest
        else '<p class="muted">No sources were supplied.</p>'
    )
    stats = result.source_stats
    fixture = (
        '<p class="banner bad"><strong>Development fixture:</strong> no AI model '
        "was called. This report is not AI-generated legal analysis.</p>"
        if result.is_mock
        else ""
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(title)}</title>
<style>
  :root {{ --ink:#131c3a; --muted:#5c6478; --rule:#d8d3c4; --paper:#fdfcf8; --teal:#106a6a; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:var(--paper); color:var(--ink);
    font-family: Georgia, 'Times New Roman', serif; line-height:1.55; }}
  main {{ max-width: 900px; margin: 0 auto; padding: 48px 28px 80px; }}
  h1,h2,h3 {{ font-family: Georgia, 'Times New Roman', serif; line-height:1.2; }}
  h1 {{ font-size: 30px; margin:0 0 6px; }}
  h2 {{ font-size: 18px; margin:34px 0 10px; border-bottom:1px solid var(--rule); padding-bottom:6px; }}
  .kicker {{ font-family: ui-sans-serif, system-ui, sans-serif; font-size:11px; letter-spacing:.14em;
    text-transform:uppercase; color:var(--teal); font-weight:700; }}
  .meta {{ font-family: ui-sans-serif, system-ui, sans-serif; font-size:12px; color:var(--muted); }}
  .banner {{ font-family: ui-sans-serif, system-ui, sans-serif; font-size:12px; padding:10px 12px;
    border:1px solid #e5c98b; background:#fff8e6; margin:14px 0; }}
  .banner.bad {{ border-color:#e3b6b6; background:#fdf0f0; }}
  .badge {{ display:inline-block; font-family: ui-sans-serif, system-ui, sans-serif; font-size:9px;
    text-transform:uppercase; letter-spacing:.06em; padding:2px 6px; border:1px solid var(--rule);
    border-radius:99px; margin-left:6px; white-space:nowrap; }}
  .badge.ok {{ color:#0c4e4e; border-color:#a8e3e3; background:#f0fafa; }}
  .badge.warn {{ color:#7a4d00; border-color:#e5c98b; background:#fff8e6; }}
  .badge.bad {{ color:#8a1f1f; border-color:#e3b6b6; background:#fdf0f0; }}
  .muted {{ color:var(--muted); }}
  .sources {{ font-family: ui-sans-serif, system-ui, sans-serif; font-size:10px; color:var(--muted); margin-top:4px; }}
  .source {{ display:inline-block; border:1px solid var(--rule); border-radius:4px; padding:1px 5px; margin:2px 4px 2px 0; }}
  .claim-head {{ display:flex; gap:8px; align-items:flex-start; justify-content:space-between; }}
  li {{ margin:10px 0; }}
  .timeline .date {{ font-family: ui-sans-serif, system-ui, sans-serif; font-size:11px; font-weight:700; color:var(--teal); }}
  table {{ border-collapse:collapse; width:100%; font-family: ui-sans-serif, system-ui, sans-serif; font-size:12px; }}
  th,td {{ border:1px solid var(--rule); padding:6px 8px; text-align:left; }}
  th {{ background:#f5f0e4; }}
  .footer {{ margin-top:48px; border-top:1px solid var(--rule); padding-top:12px; font-family: ui-sans-serif, system-ui, sans-serif; font-size:10px; color:var(--muted); }}
  code {{ font-family: ui-monospace, Consolas, monospace; font-size:10px; }}
  @media print {{ main {{ padding:0; max-width:none; }} body {{ background:#fff; }} .banner {{ break-inside:avoid; }} }}
</style>
</head>
<body>
<main>
  <p class="kicker">NyayaSaar · Case Intelligence</p>
  <h1>{_e(case.title)}</h1>
  <p class="meta">{_e(case.case_number or "No case number")} · {_e(case.court or "Court not recorded")} · {_e(case.jurisdiction or "Jurisdiction not recorded")}</p>
  <p class="meta">Generated {_e(generated_text)} · {_e(result.provider)} / {_e(result.model)} · workflow {_e(result.workflow_version)} · schema {_e(result.result_schema_version)}</p>
  {fixture}
  <p class="banner"><strong>Professional review required.</strong> This is an AI-assisted research report, not legal advice. Every statement must be independently verified against the original documents before use.</p>

  <h2>Executive summary</h2>
  <p>{_e(result.summary)}</p>

  <h2>Verification</h2>
  <p class="meta">{result.verification.total_claims} statement(s): {result.verification.supported} supported, {result.verification.partially_supported} partially supported, {result.verification.unsupported} unsupported. {result.verification.verified_spans} quote span(s) verified; {result.verification.invalid_source_refs} invalid source reference(s) rejected.</p>
  <table><thead><tr><th>Category</th><th>Supported</th><th>Partial</th><th>Unsupported</th></tr></thead>
  <tbody>{_category_rows(result.verification.categories)}</tbody></table>
  <p class="meta">Source coverage: {stats.documents_analyzed} of {stats.documents_available} document(s), {stats.pages_included} page excerpt(s), {stats.characters_included:,} characters. Duplicate pages skipped: {stats.duplicate_pages_skipped}. Short pages: {stats.short_pages}. Truncated pages: {stats.truncated_pages}. OCR-required documents: {stats.ocr_required_documents}.</p>
  {notes}

  <h2>Parties</h2>
  {parties}

  <h2>Named entities</h2>
  {entities}

  <h2>Amounts</h2>
  {amounts}

  <h2>Material facts</h2>
  {facts}

  <h2>Procedural history</h2>
  {procedural}

  <h2>Chronology</h2>
  {timeline}

  <h2>Potential legal issues</h2>
  {issues}

  <h2>Questions requiring further evidence</h2>
  {evidence_questions}

  <h2>Ambiguity and uncertainty</h2>
  {ambiguities}

  <h2>Model inferences</h2>
  {inferences}

  <h2>Unverified hypotheses</h2>
  {hypotheses}

  <h2>Missing information</h2>
  {missing}

  <h2>Limitations</h2>
  {limitations}

  <h2>Source manifest</h2>
  {manifest}

  <p class="footer">NyayaSaar is a legal research assistant. It does not provide legal advice and never files or submits documents. No external legal authority database was consulted for this report. Generated from uploaded documents only.</p>
</main>
</body>
</html>"""


def _md_sources(refs: list[VerifiedSourceRef]) -> str:
    if not refs:
        return "_No verified source_"
    return " · ".join(
        f"{ref.document_name} p.{ref.page_number}"
        f" ({'verified' if ref.quote_verified else 'quote unverified'})"
        for ref in refs
    )


def render_case_report_markdown(
    case: Case, run: WorkflowRun, result: CaseAnalysisResult
) -> str:
    lines: list[str] = []
    lines.append(f"# Case Intelligence Report — {case.title}")
    lines.append("")
    lines.append(
        f"**Case:** {case.case_number or 'No case number'} · "
        f"{case.court or 'Court not recorded'} · "
        f"{case.jurisdiction or 'Jurisdiction not recorded'}"
    )
    lines.append(
        f"**Generated:** {result.generated_at.isoformat()} · "
        f"**Provider/model:** {result.provider} / {result.model} · "
        f"**Workflow:** {result.workflow_version} · "
        f"**Schema:** {result.result_schema_version}"
    )
    lines.append("")
    if result.is_mock:
        lines.append(
            "> **Development fixture:** no AI model was called. This report is "
            "not AI-generated legal analysis."
        )
        lines.append("")
    lines.append(
        "> **Professional review required.** This is an AI-assisted research "
        "report, not legal advice. Verify every statement against the original "
        "documents before use."
    )
    lines.append("")
    lines.append("## Executive summary")
    lines.append("")
    lines.append(result.summary)
    lines.append("")
    lines.append("## Verification")
    lines.append("")
    lines.append(
        f"- {result.verification.total_claims} statement(s): "
        f"{result.verification.supported} supported, "
        f"{result.verification.partially_supported} partially supported, "
        f"{result.verification.unsupported} unsupported."
    )
    lines.append(
        f"- {result.verification.verified_spans} quote span(s) verified; "
        f"{result.verification.invalid_source_refs} invalid source reference(s) rejected."
    )
    for category in result.verification.categories:
        lines.append(
            f"- {category.category.replace('_', ' ').title()}: "
            f"{category.supported} supported / {category.partially_supported} partial / "
            f"{category.unsupported} unsupported"
        )
    for note in result.verification.notes:
        lines.append(f"- {note}")
    lines.append("")
    lines.append("## Parties")
    lines.append("")
    if result.parties:
        for party in result.parties:
            role = f" — {party.role}" if party.role else ""
            lines.append(
                f"- **{party.name}**{role} — "
                f"{SUPPORT_LABELS.get(party.support, party.support)} — "
                f"{_md_sources(party.sources)}"
            )
    else:
        lines.append("_None extracted._")
    lines.append("")
    lines.append("## Named entities")
    lines.append("")
    if result.entities:
        for entity in result.entities:
            lines.append(
                f"- **{entity.name}** ({entity.entity_type.replace('_', ' ')}) — "
                f"{entity.role or 'role not recorded'} [{entity.support}] — "
                f"{_md_sources(entity.sources)}"
            )
    else:
        lines.append("_None extracted._")
    lines.append("")
    lines.append("## Amounts")
    lines.append("")
    if result.amounts:
        for amount in result.amounts:
            lines.append(
                f"- **{amount.amount_text}** — {amount.description} "
                f"[{amount.support}] — {_md_sources(amount.sources)}"
            )
    else:
        lines.append("_None extracted._")
    lines.append("")
    lines.append("## Material facts")
    lines.append("")
    if result.facts:
        for index, claim in enumerate(result.facts, 1):
            lines.append(f"{index}. {claim.claim} [{claim.support}]")
            lines.append(f"   - {_md_sources(claim.sources)}")
    else:
        lines.append("_None extracted._")
    lines.append("")
    lines.append("## Procedural history")
    lines.append("")
    if result.procedural_history:
        for event in result.procedural_history:
            lines.append(
                f"- **{event.stage}**"
                f"{' · ' + event.date_text if event.date_text else ''} — "
                f"{event.description} [{event.support}] — {_md_sources(event.sources)}"
            )
    else:
        lines.append("_None extracted._")
    lines.append("")
    lines.append("## Chronology")
    lines.append("")
    if result.timeline:
        for event in result.timeline:
            suffix = " _(ambiguous date)_" if event.date_ambiguous else ""
            lines.append(
                f"- **{event.date_text}**{suffix} — {event.event} "
                f"[{event.support}] — {_md_sources(event.sources)}"
            )
    else:
        lines.append("_None extracted._")
    lines.append("")
    lines.append("## Potential legal issues")
    lines.append("")
    if result.issue_analysis:
        for issue in result.issue_analysis:
            lines.append(f"- **{issue.question}** [{issue.support}]")
            lines.append(f"  - Why it matters: {issue.why_it_matters}")
            lines.append(f"  - Sources: {_md_sources(issue.sources)}")
    else:
        lines.append("_None identified._")
    lines.append("")
    lines.append("## Questions requiring further evidence")
    lines.append("")
    if result.evidence_questions:
        for question in result.evidence_questions:
            lines.append(f"- **{question.question}** [{question.support}]")
            lines.append(f"  - Why it matters: {question.why_it_matters}")
            lines.append(f"  - Evidence needed: {question.evidence_needed}")
            lines.append(f"  - Sources: {_md_sources(question.sources)}")
    else:
        lines.append("_None identified._")
    lines.append("")
    lines.append("## Ambiguity and uncertainty")
    lines.append("")
    if result.ambiguities:
        for item in result.ambiguities:
            lines.append(
                f"- **{item.statement}** ({item.severity} severity) [{item.support}]"
            )
            lines.append(f"  - Reason: {item.reason}")
            lines.append(f"  - Sources: {_md_sources(item.sources)}")
    else:
        lines.append("_None recorded._")
    lines.append("")
    lines.append("## Model inferences")
    lines.append("")
    if result.inferences:
        for claim in result.inferences:
            lines.append(f"- {claim.claim} [{claim.support}] — {_md_sources(claim.sources)}")
    else:
        lines.append("_None recorded._")
    lines.append("")
    for heading, items in (
        ("## Unverified hypotheses", result.unverified_hypotheses),
        ("## Missing information", result.missing_information),
        ("## Limitations", result.limitations),
    ):
        lines.append(heading)
        lines.append("")
        if items:
            lines.extend(f"- {item}" for item in items)
        else:
            lines.append("_None recorded._")
        lines.append("")
    lines.append("## Source manifest")
    lines.append("")
    if result.source_manifest:
        for source in result.source_manifest:
            lines.append(
                f"- `{source.source_id}` · {source.document_name} · page "
                f"{source.page_number}{' · truncated' if source.truncated else ''}"
                f"{' · short page' if source.short else ''}"
            )
    else:
        lines.append("_No sources supplied._")
    lines.append("")
    lines.append(
        "---\n_NyayaSaar is a legal research assistant. It does not provide legal "
        "advice and never files or submits documents. No external legal authority "
        "database was consulted for this report._"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Stage 8 — Contradiction & Gap Hunter report renderers
# ---------------------------------------------------------------------------


def render_contradiction_report_markdown(
    case: Case,
    run: WorkflowRun,
    result: Any,
    *,
    reviews: dict[str, Any] | None = None,
) -> str:
    generated = result.generated_at
    if generated.tzinfo is not None:
        generated = generated.astimezone(timezone.utc)
    review_map = reviews or {}
    lines: list[str] = [
        f"# Contradiction & Gap Hunter Report — {case.title}",
        "",
        f"- **Case number:** {case.case_number or 'Not specified'}",
        f"- **Generated:** {generated.strftime('%d %B %Y, %H:%M UTC')}",
        f"- **Workflow:** {run.id} (v{result.workflow_version})",
        f"- **Provider / model:** {result.provider} / {result.model}"
        + (" (development fixture)" if result.is_mock else ""),
        f"- **Verification:** {result.verification.supported} supported, "
        f"{result.verification.partially_supported} source-cited, "
        f"{result.verification.unsupported} unsupported",
        "",
        "> **Professional legal review required.** Potential contradictions and "
        "inconsistencies are analytical flags, not proof of dishonesty or wrongdoing.",
        "",
        "## Summary",
        "",
        result.summary,
        "",
        "## Findings",
        "",
    ]
    if not result.findings:
        lines.append("_No findings recorded._")
    for f in result.findings:
        rev = review_map.get(f.finding_id)
        rev_status = rev.status if rev else "unreviewed"
        lines.append(
            f"### [{f.finding_id}] {f.title} ({f.category} · {f.severity} · review: {rev_status})"
        )
        lines.append("")
        lines.append(f"- **Observed evidence:** {f.observed_evidence_summary}")
        lines.append(f"- **Model interpretation:** {f.model_interpretation}")
        if f.side_a_sources:
            refs_a = "; ".join(
                f"{r.document_name} p.{r.page_number}"
                + (f' "{r.quote}"' if r.quote else "")
                for r in f.side_a_sources
            )
            lines.append(f"- **{f.side_a_label}:** {refs_a}")
        if f.side_b_sources:
            refs_b = "; ".join(
                f"{r.document_name} p.{r.page_number}"
                + (f' "{r.quote}"' if r.quote else "")
                for r in f.side_b_sources
            )
            lines.append(f"- **{f.side_b_label or 'Side B'}:** {refs_b}")
        if rev and rev.reviewer_note:
            lines.append(f"- **Reviewer note:** {rev.reviewer_note}")
        lines.append("")

    lines.append("## Chronological timeline")
    lines.append("")
    if not result.timeline:
        lines.append("_No dated events extracted._")
    for ev in result.timeline:
        refs = ", ".join(f"{r.document_name} p.{r.page_number}" for r in ev.sources)
        lines.append(f"- **{ev.date_text}** — {ev.event}" + (f" ({refs})" if refs else ""))
    lines.append("")
    lines.append("## Limitations")
    lines.append("")
    lines.extend(f"- {lim}" for lim in result.limitations)
    return "\n".join(lines)


def render_contradiction_report_html(
    case: Case,
    run: WorkflowRun,
    result: Any,
    *,
    reviews: dict[str, Any] | None = None,
) -> str:
    generated = result.generated_at
    if generated.tzinfo is not None:
        generated = generated.astimezone(timezone.utc)
    review_map = reviews or {}
    finding_blocks: list[str] = []
    for f in result.findings:
        rev = review_map.get(f.finding_id)
        rev_status = rev.status if rev else "unreviewed"
        rev_note = rev.reviewer_note if rev else None
        finding_blocks.append(
            "<div class='card'>"
            f"<h3>[{_e(f.finding_id)}] {_e(f.title)}</h3>"
            f"<div class='meta'>{_e(f.category)} · severity: {_e(f.severity)} · "
            f"review: <strong>{_e(rev_status)}</strong> · {_badge(f.support)}</div>"
            f"<p><strong>Observed evidence:</strong> {_e(f.observed_evidence_summary)}</p>"
            f"<p><strong>Model interpretation:</strong> {_e(f.model_interpretation)}</p>"
            f"<div class='sources'><strong>{_e(f.side_a_label)}:</strong> {_source_links(f.side_a_sources)}</div>"
            + (
                f"<div class='sources'><strong>{_e(f.side_b_label or 'Side B')}:</strong> {_source_links(f.side_b_sources)}</div>"
                if f.side_b_sources
                else ""
            )
            + (f"<p><strong>Reviewer note:</strong> {_e(rev_note)}</p>" if rev_note else "")
            + "</div>"
        )
    timeline_rows = "".join(
        f"<li><strong>{_e(ev.date_text)}</strong> — {_e(ev.event)} "
        f"<div class='sources'>{_source_links(ev.sources)}</div></li>"
        for ev in result.timeline
    )
    lims = "".join(f"<li>{_e(lim)}</li>" for lim in result.limitations)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Contradiction &amp; Gap Hunter Report — {_e(case.title)}</title>
<style>
  body {{ font-family: Georgia, 'Times New Roman', serif; color: #0f172a; max-width: 900px; margin: 28px auto; padding: 0 20px; line-height: 1.5; }}
  h1, h2, h3 {{ font-family: system-ui, -apple-system, sans-serif; color: #0f172a; }}
  .notice {{ background: #fffbeb; border: 1px solid #fde68a; padding: 10px 14px; border-radius: 6px; font-size: 13px; margin: 14px 0; }}
  .card {{ border: 1px solid #cbd5e1; border-radius: 8px; padding: 14px; margin-bottom: 14px; }}
  .meta {{ font-size: 12px; color: #475569; margin-bottom: 8px; font-family: system-ui, sans-serif; }}
  .sources {{ font-size: 12px; color: #334155; margin-top: 4px; }}
  .source {{ display: inline-block; background: #f1f5f9; padding: 2px 6px; border-radius: 4px; margin-right: 6px; }}
  .badge {{ font-size: 11px; padding: 2px 6px; border-radius: 4px; font-family: system-ui, sans-serif; }}
  .ok {{ background: #dcfce7; color: #166534; }}
  .warn {{ background: #fef3c7; color: #92400e; }}
  .bad {{ background: #fee2e2; color: #991b1b; }}
</style>
</head>
<body>
<h1>Contradiction &amp; Gap Hunter Report — {_e(case.title)}</h1>
<div class="meta">Generated {_e(generated.strftime('%d %B %Y, %H:%M UTC'))} · Workflow {_e(run.id)}</div>
<div class="notice"><strong>Professional legal review required.</strong> Potential contradictions and inconsistencies are analytical flags for human review, not proof of dishonesty or wrongdoing.</div>
<h2>Summary</h2>
<p>{_e(result.summary)}</p>
<h2>Findings ({len(result.findings)})</h2>
{"".join(finding_blocks) if finding_blocks else "<p>No findings recorded.</p>"}
<h2>Chronological Timeline</h2>
<ul>{timeline_rows if timeline_rows else "<li>No dated events extracted.</li>"}</ul>
<h2>Limitations</h2>
<ul>{lims}</ul>
</body>
</html>"""
