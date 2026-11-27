"""Precedent Explorer HTML + Markdown report renderers (Stage 9).

Rendered from persisted, verified result. No model is called; no new facts added.
All model/document text is HTML-escaped before it reaches the document.
"""

from __future__ import annotations

import html
from datetime import timezone

from app.agents.schemas_precedent import PrecedentResult
from app.db.models.case import Case
from app.db.models.workflow import WorkflowRun


def _e(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


_REPORT_CSS = """
  body { font-family: Georgia, 'Times New Roman', serif; color: #0f172a; max-width: 900px; margin: 28px auto; padding: 0 20px; line-height: 1.5; }
  h1, h2, h3 { font-family: system-ui, -apple-system, sans-serif; color: #0f172a; }
  .notice { background: #fffbeb; border: 1px solid #fde68a; padding: 10px 14px; border-radius: 6px; font-size: 13px; margin: 14px 0; }
  .fixture-notice { background: #fff7ed; border: 1px solid #fed7aa; padding: 10px 14px; border-radius: 6px; font-size: 13px; margin: 14px 0; color: #9a3412; }
  .card { border: 1px solid #cbd5e1; border-radius: 8px; padding: 14px; margin-bottom: 14px; }
  .card.fixture { border-color: #fed7aa; background: #fff7ed08; }
  .meta { font-size: 12px; color: #475569; margin-bottom: 8px; font-family: system-ui, sans-serif; }
  .sources { font-size: 12px; color: #334155; margin-top: 4px; }
  .source { display: inline-block; background: #f1f5f9; padding: 2px 6px; border-radius: 4px; margin-right: 6px; }
  .badge { font-size: 11px; padding: 2px 6px; border-radius: 4px; font-family: system-ui, sans-serif; margin-left: 4px; }
  .ok { background: #dcfce7; color: #166534; }
  .warn { background: #fef3c7; color: #92400e; }
  .bad { background: #fee2e2; color: #991b1b; }
  .fixture-badge { background: #fed7aa; color: #9a3412; }
  table { border-collapse: collapse; width: 100%; font-size: 13px; }
  th, td { text-align: left; padding: 6px 10px; border: 1px solid #e2e8f0; }
  th { background: #f8fafc; }
"""


def render_precedent_report_html(
    case: Case, run: WorkflowRun, result: PrecedentResult
) -> str:
    generated = result.generated_at
    if generated.tzinfo is not None:
        generated = generated.astimezone(timezone.utc)
    gen_text = generated.strftime("%d %B %Y, %H:%M UTC")
    title = f"Precedent Explorer Report — {case.title}"

    any_fixture = any(a.is_fixture for a in result.authorities)
    fixture_notice = (
        '<div class="fixture-notice"><strong>Development fixture data included.</strong> '
        "Records labelled [FIXTURE] are demonstration data and are NOT real legal authorities. "
        "They must NOT be cited in legal proceedings.</div>"
        if any_fixture
        else ""
    )

    # Authorities
    auth_blocks = []
    for auth in result.authorities:
        fixture_cls = " fixture" if auth.is_fixture else ""
        fixture_badge = (
            '<span class="badge fixture-badge">FIXTURE — NOT REAL LAW</span>'
            if auth.is_fixture
            else ""
        )
        auth_blocks.append(
            f'<div class="card{fixture_cls}">'
            f'<div class="meta">{_e(auth.court)} · {_e(auth.jurisdiction)} · {_e(auth.decision_date)}'
            f' · Source: {_e(auth.source_provider)}{fixture_badge}</div>'
            f"<strong>{_e(auth.citation_text)}</strong> — {_e(auth.title)}<br>"
            f"<div>Holding: {_e(auth.holding_summary)}</div>"
            + (f'<div class="sources">Relevance note: {_e(auth.relevance_note)}</div>' if auth.relevance_note else "")
            + f"</div>"
        )
    authorities_html = "".join(auth_blocks) or "<p>No authorities identified.</p>"

    # Citation pairs
    pair_blocks = []
    for pair in result.citation_pairs:
        pair_blocks.append(
            f'<div class="card">'
            f'<strong>{_e(pair.from_citation)}</strong>'
            f' <span class="badge warn">{_e(pair.relationship_type.replace("_", " "))}</span> '
            f"<strong>{_e(pair.to_citation)}</strong><br>"
            f'<div class="meta">Confidence: {_e(pair.confidence)}</div>'
            + (f'<div class="sources">Supporting passage: {_e(pair.supporting_passage[:300])}</div>' if pair.supporting_passage else "")
            + f"</div>"
        )
    pairs_html = "".join(pair_blocks) or "<p>No citation relationships identified.</p>"

    # Conflicts
    conflict_blocks = []
    for conflict in result.potential_conflicts:
        conflict_blocks.append(
            f'<div class="card">'
            f"<h3>{_e(conflict.title)}</h3>"
            f"<table><tr><th>Interpretation A</th><th>Interpretation B</th></tr>"
            f"<tr><td>{_e(conflict.interpretation_a)}</td><td>{_e(conflict.interpretation_b)}</td></tr></table>"
            f'<div class="notice" style="margin-top:8px">{_e(conflict.model_note)}</div>'
            f"</div>"
        )
    conflicts_html = "".join(conflict_blocks) or "<p>No potential conflicts identified.</p>"

    lims = "".join(f"<li>{_e(l)}</li>" for l in result.limitations) or "<li>See professional disclaimer above.</li>"

    corpus_status = (
        "Connected — results sourced from configured legal corpus."
        if result.corpus_configured
        else "Not connected — no real legal corpus is configured. Results are development fixtures only."
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{_e(title)}</title>
<style>{_REPORT_CSS}</style>
</head>
<body>
<h1>{_e(title)}</h1>
<div class="meta">Generated {_e(gen_text)} · Workflow {_e(run.id)}</div>
<div class="notice"><strong>Professional legal review required.</strong> This is an AI-assisted research output. No authority is confirmed as binding, reversed, or overruled without reliable evidence. All metadata must be independently verified.</div>
{fixture_notice}
<p><strong>Corpus status:</strong> {_e(corpus_status)}</p>
<p><strong>Query used:</strong> {_e(result.query_used) or "—"}</p>
<h2>Summary</h2>
<p>{_e(result.summary)}</p>
<h2>Identified Authorities ({len(result.authorities)})</h2>
{authorities_html}
<h2>Citation Relationships ({len(result.citation_pairs)})</h2>
{pairs_html}
<h2>Potential Conflicts for Review ({len(result.potential_conflicts)})</h2>
{conflicts_html}
<h2>Limitations</h2>
<ul>{lims}</ul>
</body>
</html>"""


def render_precedent_report_markdown(
    case: Case, run: WorkflowRun, result: PrecedentResult
) -> str:
    generated = result.generated_at
    if generated.tzinfo is not None:
        generated = generated.astimezone(timezone.utc)
    gen_text = generated.strftime("%d %B %Y, %H:%M UTC")

    lines = [
        f"# Precedent Explorer Report — {case.title}",
        f"",
        f"Generated: {gen_text}  |  Workflow: {run.id}",
        f"",
        f"> **Professional legal review required.** AI-assisted research output only.",
        f"",
        f"**Corpus configured:** {'Yes' if result.corpus_configured else 'No — development fixtures only'}  ",
        f"**Query used:** {result.query_used or '—'}",
        f"",
        f"## Summary",
        f"",
        result.summary,
        f"",
        f"## Identified Authorities ({len(result.authorities)})",
        f"",
    ]
    for auth in result.authorities:
        fixture_note = " **[FIXTURE — NOT REAL LAW]**" if auth.is_fixture else ""
        lines.append(f"### {auth.citation_text}{fixture_note}")
        lines.append(f"- Court: {auth.court}")
        lines.append(f"- Jurisdiction: {auth.jurisdiction}")
        lines.append(f"- Date: {auth.decision_date}")
        lines.append(f"- Source: {auth.source_provider}")
        lines.append(f"- Holding: {auth.holding_summary}")
        if auth.relevance_note:
            lines.append(f"- Relevance note: {auth.relevance_note}")
        lines.append("")

    if not result.authorities:
        lines.append("No authorities identified.\n")

    lines.append(f"## Citation Relationships ({len(result.citation_pairs)})")
    lines.append("")
    for pair in result.citation_pairs:
        lines.append(
            f"- **{pair.from_citation}** → *{pair.relationship_type.replace('_', ' ')}* → "
            f"**{pair.to_citation}** (confidence: {pair.confidence})"
        )
        if pair.supporting_passage:
            lines.append(f"  - Supporting passage: {pair.supporting_passage[:300]}")
    if not result.citation_pairs:
        lines.append("No citation relationships identified.\n")

    lines.append("")
    lines.append(f"## Potential Conflicts for Review ({len(result.potential_conflicts)})")
    lines.append("")
    for conflict in result.potential_conflicts:
        lines.append(f"### {conflict.title}")
        lines.append(f"- Interpretation A: {conflict.interpretation_a}")
        lines.append(f"- Interpretation B: {conflict.interpretation_b}")
        lines.append(f"- Note: {conflict.model_note}")
        lines.append("")
    if not result.potential_conflicts:
        lines.append("No potential conflicts identified.\n")

    lines.append("## Limitations")
    lines.append("")
    for lim in result.limitations:
        lines.append(f"- {lim}")

    return "\n".join(lines)
