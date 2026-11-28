"""Stage 10 HTML + Markdown report renderers (Advocate Mode & Judge/Clerk Mode).

Rendered from persisted, verified results only. No model is called; all text
is HTML-escaped before entering the output document.
"""

from __future__ import annotations

import html
from datetime import timezone

from app.agents.schemas_stage10 import AdvocateResult, JudgeResult
from app.db.models.case import Case
from app.db.models.workflow import WorkflowRun


def _e(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


_CSS = """
  body { font-family: Georgia, 'Times New Roman', serif; color: #0f172a; max-width: 900px; margin: 28px auto; padding: 0 20px; line-height: 1.5; }
  h1, h2, h3 { font-family: system-ui, -apple-system, sans-serif; color: #0f172a; }
  .notice { background: #fffbeb; border: 1px solid #fde68a; padding: 10px 14px; border-radius: 6px; font-size: 13px; margin: 14px 0; }
  .card { border: 1px solid #cbd5e1; border-radius: 8px; padding: 14px; margin-bottom: 14px; }
  .meta { font-size: 12px; color: #475569; margin-bottom: 8px; font-family: system-ui, sans-serif; }
  .sources { font-size: 12px; color: #334155; margin-top: 6px; }
  .source { display: inline-block; background: #f1f5f9; padding: 2px 6px; border-radius: 4px; margin-right: 6px; }
  .badge { font-size: 11px; padding: 2px 6px; border-radius: 4px; font-family: system-ui, sans-serif; background: #e2e8f0; color: #1e293b; margin-right: 4px; }
"""


def render_advocate_report_markdown(
    case: Case, run: WorkflowRun, result: AdvocateResult
) -> str:
    lines = [
        f"# Advocate Mode Argument Report — {case.title}",
        "",
        f"- **Workflow:** `{run.id}`",
        f"- **Side focus:** {result.preferred_side}",
        f"- **Selected issue:** {result.selected_issue or 'General case issues'}",
        f"- **Disclaimer:** {result.research_tool_disclaimer}",
        "",
        "## Summary",
        "",
        result.summary,
        "",
    ]
    if result.relevant_facts:
        lines.extend(["## Relevant Facts", ""])
        lines.extend(f"- {f}" for f in result.relevant_facts)
        lines.append("")

    for heading, args in (
        ("Claimant / Petitioner Arguments", result.claimant_arguments),
        ("Respondent / Defendant Arguments", result.respondent_arguments),
    ):
        lines.extend([f"## {heading}", ""])
        if not args:
            lines.append("_None identified._")
            lines.append("")
            continue
        for a in args:
            lines.append(
                f"### [{a.argument_id}] {a.claim} ({a.tier} · strength: {a.strength} · {a.support})"
            )
            lines.append("")
            lines.append(f"- **Issue:** {a.issue or '—'}")
            lines.append(f"- **Reasoning:** {a.reasoning}")
            if a.authority_refs:
                lines.append(f"- **Authorities:** {', '.join(a.authority_refs)}")
            if a.counterarguments:
                lines.append(f"- **Counterarguments:** {'; '.join(a.counterarguments)}")
            if a.evidentiary_gap:
                lines.append(f"- **Evidentiary gap:** {a.gap_description or 'Support missing'}")
            if a.supporting_sources:
                refs = "; ".join(f"{r.document_name} p.{r.page_number}" for r in a.supporting_sources)
                lines.append(f"- **Supporting sources:** {refs}")
            if a.opposing_sources:
                refs = "; ".join(f"{r.document_name} p.{r.page_number}" for r in a.opposing_sources)
                lines.append(f"- **Contrary sources:** {refs}")
            lines.append("")

    if result.evidentiary_gaps:
        lines.extend(["## Evidentiary Gaps", ""])
        for g in result.evidentiary_gaps:
            lines.append(f"- **{g.missing_evidence_type}:** {g.description} (affects: {g.affected_claim})")
        lines.append("")

    if result.strengths:
        lines.extend(["## Record Strengths", ""])
        lines.extend(f"- {s}" for s in result.strengths)
        lines.append("")

    if result.weaknesses:
        lines.extend(["## Record Weaknesses", ""])
        lines.extend(f"- {w}" for w in result.weaknesses)
        lines.append("")

    if result.unresolved_questions:
        lines.extend(["## Unresolved Legal Questions", ""])
        lines.extend(f"- {q}" for q in result.unresolved_questions)
        lines.append("")

    if result.verification.notes:
        lines.extend(["## Verification Notes", ""])
        lines.extend(f"- {note}" for note in result.verification.notes)
        lines.append("")

    lines.extend(["## Limitations", ""])
    lines.extend(f"- {l}" for l in result.limitations)
    return "\n".join(lines)


def render_advocate_report_html(
    case: Case, run: WorkflowRun, result: AdvocateResult
) -> str:
    generated = result.generated_at
    if generated.tzinfo is not None:
        generated = generated.astimezone(timezone.utc)

    def _arg_cards(args) -> str:
        if not args:
            return "<p>None identified.</p>"
        blocks = []
        for a in args:
            srcs = "".join(
                f"<span class='source'>{_e(r.document_name)} p.{_e(r.page_number)}</span>"
                for r in a.supporting_sources
            )
            opp_srcs = "".join(
                f"<span class='source'>{_e(r.document_name)} p.{_e(r.page_number)}</span>"
                for r in a.opposing_sources
            )
            gap_html = (
                f"<p><strong>Evidentiary gap:</strong> {_e(a.gap_description or 'Missing support')}</p>"
                if a.evidentiary_gap
                else ""
            )
            blocks.append(
                "<div class='card'>"
                f"<h3>[{_e(a.argument_id)}] {_e(a.claim)}</h3>"
                f"<div class='meta'><span class='badge'>{_e(a.tier)}</span>"
                f"<span class='badge'>strength: {_e(a.strength)}</span>"
                f"<span class='badge'>{_e(a.support)}</span></div>"
                f"<p>{_e(a.reasoning)}</p>"
                + (f"<p><strong>Authorities:</strong> {_e(', '.join(a.authority_refs))}</p>" if a.authority_refs else "")
                + (f"<p><strong>Counterarguments:</strong> {_e('; '.join(a.counterarguments))}</p>" if a.counterarguments else "")
                + gap_html
                + (f"<div class='sources'><strong>Sources:</strong> {srcs}</div>" if srcs else "")
                + (f"<div class='sources'><strong>Contrary sources:</strong> {opp_srcs}</div>" if opp_srcs else "")
                + "</div>"
            )
        return "".join(blocks)

    facts_html = "".join(f"<li>{_e(f)}</li>" for f in result.relevant_facts) or "<li>No facts recorded.</li>"
    gaps_html = "".join(
        f"<li><strong>{_e(g.missing_evidence_type)}:</strong> {_e(g.description)}</li>"
        for g in result.evidentiary_gaps
    ) or "<li>No evidentiary gaps recorded.</li>"
    strengths_html = "".join(f"<li>{_e(s)}</li>" for s in result.strengths) or "<li>None recorded.</li>"
    weaknesses_html = "".join(f"<li>{_e(w)}</li>" for w in result.weaknesses) or "<li>None recorded.</li>"
    questions_html = "".join(f"<li>{_e(q)}</li>" for q in result.unresolved_questions) or "<li>None recorded.</li>"
    notes_html = "".join(f"<li>{_e(n)}</li>" for n in result.verification.notes)
    lims_html = "".join(f"<li>{_e(l)}</li>" for l in result.limitations)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Advocate Mode Report — {_e(case.title)}</title>
<style>{_CSS}</style>
</head>
<body>
<h1>Advocate Mode Argument Report — {_e(case.title)}</h1>
<div class="meta">Generated {_e(generated.strftime('%d %B %Y, %H:%M UTC'))} · Workflow {_e(run.id)} · Side focus: {_e(result.preferred_side)}</div>
<div class="notice"><strong>{_e(result.research_tool_disclaimer)}</strong></div>
<h2>Summary</h2>
<p>{_e(result.summary)}</p>
<h2>Relevant Facts</h2>
<ul>{facts_html}</ul>
<h2>Claimant / Petitioner Arguments ({len(result.claimant_arguments)})</h2>
{_arg_cards(result.claimant_arguments)}
<h2>Respondent / Defendant Arguments ({len(result.respondent_arguments)})</h2>
{_arg_cards(result.respondent_arguments)}
<h2>Evidentiary Gaps</h2>
<ul>{gaps_html}</ul>
<h2>Record Strengths</h2>
<ul>{strengths_html}</ul>
<h2>Record Weaknesses</h2>
<ul>{weaknesses_html}</ul>
<h2>Unresolved Legal Questions</h2>
<ul>{questions_html}</ul>
{f'<h2>Verification Notes</h2><ul>{notes_html}</ul>' if notes_html else ''}
<h2>Limitations</h2>
<ul>{lims_html}</ul>
</body>
</html>"""


def render_judge_report_markdown(
    case: Case, run: WorkflowRun, result: JudgeResult
) -> str:
    lines = [
        f"# Judge / Clerk Reasoning Audit Report — {case.title}",
        "",
        f"- **Workflow:** `{run.id}`",
        f"- **Disclaimer:** {result.judicial_audit_disclaimer}",
        "",
        "## Summary",
        "",
        result.summary,
        "",
    ]
    if result.overall_assessment:
        lines.extend(["## Overall Audit Assessment", "", result.overall_assessment, ""])

    if result.verification.notes:
        lines.extend(["## Verification Notes", ""])
        lines.extend(f"- {note}" for note in result.verification.notes)
        lines.append("")

    sections = (
        ("Issue Coverage", result.issue_coverage),
        ("Reasoning Consistency", result.reasoning_consistency),
        ("Source Support Audit", result.source_support_audit),
        ("Citation Integrity", result.citation_integrity),
        ("Opposing Arguments & Contrary Authorities Considered", result.opposing_consideration_audit),
        ("Unresolved Questions", result.unresolved_questions),
    )
    for title, items in sections:
        lines.extend([f"## {title}", ""])
        if not items:
            lines.append("_No findings recorded._")
            lines.append("")
            continue
        for it in items:
            lines.append(
                f"### [{it.audit_id}] {it.item} ({it.status} · severity: {it.severity} · {it.support})"
            )
            lines.append("")
            lines.append(f"- **Finding:** {it.finding}")
            if it.opposing_considered is not None:
                lines.append(f"- **Opposing considered:** {'Yes' if it.opposing_considered else 'No'}")
            if it.source_refs:
                refs = "; ".join(f"{r.document_name} p.{r.page_number}" for r in it.source_refs)
                lines.append(f"- **Sources:** {refs}")
            lines.append("")

    lines.extend(["## Limitations", ""])
    lines.extend(f"- {l}" for l in result.limitations)
    return "\n".join(lines)


def render_judge_report_html(
    case: Case, run: WorkflowRun, result: JudgeResult
) -> str:
    generated = result.generated_at
    if generated.tzinfo is not None:
        generated = generated.astimezone(timezone.utc)

    def _audit_cards(items) -> str:
        if not items:
            return "<p>No findings recorded.</p>"
        blocks = []
        for it in items:
            srcs = "".join(
                f"<span class='source'>{_e(r.document_name)} p.{_e(r.page_number)}</span>"
                for r in it.source_refs
            )
            opp = (
                f"<span class='badge'>opposing considered: {'yes' if it.opposing_considered else 'no'}</span>"
                if it.opposing_considered is not None
                else ""
            )
            blocks.append(
                "<div class='card'>"
                f"<h3>[{_e(it.audit_id)}] {_e(it.item)}</h3>"
                f"<div class='meta'><span class='badge'>{_e(it.status)}</span>"
                f"<span class='badge'>severity: {_e(it.severity)}</span>"
                f"<span class='badge'>{_e(it.support)}</span>{opp}</div>"
                f"<p>{_e(it.finding)}</p>"
                + (f"<div class='sources'><strong>Sources:</strong> {srcs}</div>" if srcs else "")
                + "</div>"
            )
        return "".join(blocks)

    lims_html = "".join(f"<li>{_e(l)}</li>" for l in result.limitations)
    notes_html = "".join(f"<li>{_e(n)}</li>" for n in result.verification.notes)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Judge / Clerk Audit Report — {_e(case.title)}</title>
<style>{_CSS}</style>
</head>
<body>
<h1>Judge / Clerk Reasoning Audit Report — {_e(case.title)}</h1>
<div class="meta">Generated {_e(generated.strftime('%d %B %Y, %H:%M UTC'))} · Workflow {_e(run.id)}</div>
<div class="notice"><strong>{_e(result.judicial_audit_disclaimer)}</strong></div>
<h2>Summary</h2>
<p>{_e(result.summary)}</p>
{f'<h2>Overall Assessment</h2><p>{_e(result.overall_assessment)}</p>' if result.overall_assessment else ''}
<h2>Issue Coverage ({len(result.issue_coverage)})</h2>
{_audit_cards(result.issue_coverage)}
<h2>Reasoning Consistency ({len(result.reasoning_consistency)})</h2>
{_audit_cards(result.reasoning_consistency)}
<h2>Source Support Audit ({len(result.source_support_audit)})</h2>
{_audit_cards(result.source_support_audit)}
<h2>Citation Integrity ({len(result.citation_integrity)})</h2>
{_audit_cards(result.citation_integrity)}
<h2>Opposing Arguments &amp; Contrary Authorities ({len(result.opposing_consideration_audit)})</h2>
{_audit_cards(result.opposing_consideration_audit)}
<h2>Unresolved Questions ({len(result.unresolved_questions)})</h2>
{_audit_cards(result.unresolved_questions)}
{f'<h2>Verification Notes</h2><ul>{notes_html}</ul>' if notes_html else ''}
<h2>Limitations</h2>
<ul>{lims_html}</ul>
</body>
</html>"""
