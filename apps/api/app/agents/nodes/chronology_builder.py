"""Deterministic chronology builder.

Merges the extracted timeline, dated procedural events, and key dates into one
ordered chronology. Date strings are normalised with an explicit precision and
ambiguity flag; unknown dates are kept but sorted last. No model is called.
"""

from __future__ import annotations

from app.agents.context import WorkflowContext
from app.agents.state import CaseAnalysisState
from app.agents.tools.dates import normalise_date_text, sort_key_or_max


def _normalise_event_key(event: str) -> str:
    return " ".join((event or "").casefold().split())


def make_chronology_builder_node(ctx: WorkflowContext):
    async def chronology_builder(state: CaseAnalysisState) -> dict:
        await ctx.report_step(
            "chronology_builder", 72, "Building and ordering the chronology"
        )

        extraction = state.get("extraction_draft") or {}
        events: list[dict] = []
        seen: set[tuple[str, str]] = set()

        def add_event(
            *,
            date_text: str,
            event: str,
            significance: str,
            source_refs: list[dict] | None,
        ) -> None:
            date_info = normalise_date_text(date_text)
            key = (date_info.sort_key or _normalise_event_key(date_text), _normalise_event_key(event))
            if key in seen:
                return
            seen.add(key)
            events.append(
                {
                    "date_text": date_text,
                    "event": event,
                    "significance": significance,
                    "source_refs": source_refs or [],
                    "date_sort_key": date_info.sort_key,
                    "date_precision": date_info.precision,
                    "date_ambiguous": date_info.ambiguous,
                    "date_ambiguity_note": date_info.note,
                }
            )

        for item in extraction.get("timeline") or []:
            if not isinstance(item, dict):
                continue
            add_event(
                date_text=str(item.get("date_text", "")),
                event=str(item.get("event", "")),
                significance=str(item.get("significance", "factual")),
                source_refs=list(item.get("source_refs") or []),
            )

        for item in extraction.get("procedural_history") or []:
            if not isinstance(item, dict) or not item.get("date_text"):
                continue
            stage = str(item.get("stage", "Procedural step"))
            description = str(item.get("description", ""))
            add_event(
                date_text=str(item.get("date_text", "")),
                event=f"{stage}: {description}".strip(": ").strip(),
                significance="procedural",
                source_refs=list(item.get("source_refs") or []),
            )

        for item in extraction.get("key_dates") or []:
            if not isinstance(item, dict):
                continue
            add_event(
                date_text=str(item.get("date_text", "")),
                event=f"Key date: {item.get('label', 'date mentioned in the documents')}",
                significance="other",
                source_refs=list(item.get("source_refs") or []),
            )

        # Stable ordering: dated events first, unknown dates last in extraction order.
        events.sort(key=lambda item: sort_key_or_max(str(item.get("date_sort_key") or "")))

        ambiguous = sum(1 for item in events if item.get("date_ambiguous"))
        notes = list(state.get("notes") or [])
        if ambiguous:
            notes.append(
                f"{ambiguous} chronology entr{'y' if ambiguous == 1 else 'ies'} "
                "use a date that could not be normalised unambiguously."
            )
        unknown = sum(1 for item in events if not item.get("date_sort_key"))
        if unknown:
            notes.append(
                f"{unknown} chronology entr{'y' if unknown == 1 else 'ies'} could "
                "not be placed on the timeline because the date was unclear."
            )

        return {
            "chronology": events,
            "status": "running",
            "current_step": "verifier",
            "progress": 78,
            "notes": notes,
        }

    return chronology_builder
