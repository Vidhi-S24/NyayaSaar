# Stage 9 Handoff — Precedent Explorer & Conflict Detector

**Status:** Complete  
**Date:** 2026-11-26  
**Scope:** Stage 9 Precedent Explorer & Conflict Detector only (Stage 10 = Advocate Mode + Judge/Clerk Mode).

---

## 1. Completed Features

- **Citation & Authority Data Model (`citation_links` + Alembic `007`):**
  - `apps/api/app/db/models/citation.py`: `CitationLink` storing `from_record_id`, nullable `to_record_id`, `to_citation_text` (stores unresolved citations explicitly without inventing records), `relationship_type` (`cites | cited_by | related_issue | potentially_conflicting`), `source_passage`, `source_provider`, `is_resolved`, `confidence`, `workflow_id`, and `metadata_json`.
  - `apps/api/alembic/versions/007_add_citation_links.py`: Migration `007` creating `citation_links` and indexes.
  - `apps/api/app/main.py`: Added `"citation_links"` to SQLite dev startup table check.
- **Optional Neo4j Citation Graph Backend with DB Fallback:**
  - `apps/api/app/services/citation_graph.py`: `CitationGraphProvider` abstraction with `Neo4jCitationGraphProvider` (used when `NEO4J_URI` is configured; fails gracefully), `DatabaseCitationGraphProvider` (default fallback using `citation_links`), and `_NullCitationGraphProvider`.
- **LangGraph Precedent Explorer Workflow (`workflow_type="precedent"`):**
  - `apps/api/app/agents/schemas_precedent.py`: Versioned schemas (`9.0.0`) with `PrecedentSearchDraft`, `VerifiedAuthority`, `VerifiedCitationPair`, `VerifiedConflict`, `PrecedentResult`, and defensive `@field_validator` coercion.
  - `apps/api/app/ai/prompts/precedent_v9.py`: Prompt with `<untrusted_document>` wrapping, embedded JSON schema, and strict anti-fabrication / non-binding rules.
  - `apps/api/app/agents/nodes/precedent_analyst_v9.py`: Calls configured `LLMProvider` or returns a clearly labelled development fixture when in mock mode.
  - `apps/api/app/agents/nodes/precedent_verifier.py`: Deterministic verifier validating both `Sn` case-document refs and `Rn` retrieved-record refs, flagging unknown markers, preserving `is_fixture` provenance, and triggering bounded revision.
  - `apps/api/app/agents/graph_precedent.py`: `orchestrator -> precedent_analyst -> precedent_verifier -> finalize` with `insufficient_sources` handling.
- **API Integration & Report Export:**
  - `apps/api/app/services/analysis.py`: Dispatches `workflow_type="precedent"`, pre-retrieves case passages + `LegalCorpusProvider.search_records(...)`, persists resolved/unresolved `CitationLink`s, and exposes `list_citations_for_run`.
  - `apps/api/app/schemas/analysis.py`: Added `"precedent"` to `CaseAnalysisRequest.workflow_type`, `PrecedentResult` to `WorkflowRunResponse.result`, and `CitationLinkResponse` / `CitationLinkListResponse`.
  - `apps/api/app/routers/analysis.py`: Added `GET /api/v1/cases/{case_id}/analysis/{workflow_id}/citations` and `workflow_type="precedent"` support in `GET .../report?format=html|markdown`.
  - `apps/api/app/services/report_precedent.py` & `report.py`: HTML-escaped print-ready report and Markdown report for Precedent Explorer.
- **Shared Types & Frontend `/precedents` Page:**
  - `packages/shared/src/index.ts`: Stage 9 TypeScript types (`PrecedentAuthority`, `PrecedentCitationPair`, `PrecedentConflict`, `PrecedentResult`, `CitationLink`).
  - `apps/web/src/lib/api/analysis.ts`: `startPrecedentSearch`, `listPrecedentAnalyses`, `listCitationsForRun`.
  - `apps/web/src/components/precedents/precedent-panel.tsx`, `apps/web/src/app/(app)/precedents/precedents-client.tsx`, `page.tsx`: Corpus search with jurisdiction/court/date filters, case-linked Precedent Explorer runner, result cards with `FIXTURE` / provenance badges, expandable authority detail view, SVG + structured citation graph with relationship filter, side-by-side conflict comparison, graceful empty states, and HTML/Markdown report download.

---

## 2. Environment Variables / External Setup

- Optional: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` — when unset or unreachable, the app falls back to `DatabaseCitationGraphProvider` (`citation_links` table) without error.
- Existing: `LEGAL_CORPUS_PROVIDER` (`none` / `fixture` / `database` / `json_file`), `AI_PROVIDER`, `AI_MODEL`, `AI_API_KEY`.

---

## 3. Known Limitations

- Subsequent judicial treatment (affirmed/overruled/distinguished) is only displayed when supplied by a configured corpus; with the default fixture corpus, it is explicitly shown as unavailable.
- Real LLM output against live Gemini was not run in this automated handoff; deterministic tests use `_FakeProvider` / `MockProvider`.
- On Windows PowerShell with restricted script execution policy, invoke `pnpm.cmd` instead of `pnpm`.

---

## 4. Next Stage

- **Stage 10 — Advocate Mode & Judge/Clerk Mode** (`workflow_type="advocate"` and `workflow_type="judge"`).

---

## 5. Verification Results (Actual)

- `alembic upgrade head` (temp SQLite): `001` → `007 (head)` passed.
- `.venv\Scripts\python.exe -m pytest tests/test_precedent_explorer.py -v --tb=short`: **6 passed in 0.13s** (run outside sandbox because Windows `asyncio.ProactorEventLoop` uses `socket.socketpair()` which is blocked inside the sandbox).
- `pnpm.cmd --filter @nyayasaar/shared type-check`: passed (exit 0).
- `pnpm.cmd --filter web type-check`: passed (exit 0).
- `pnpm.cmd --filter web lint`: passed (`No ESLint warnings or errors`).
- `pnpm.cmd --filter web test`: **5 test files, 30 tests passed**.
- `pnpm.cmd --filter web build`: **compiled and built 16/16 static/dynamic routes** including `/precedents`.

---

## 6. Ready-to-Paste Continuation Prompt (Stage 10)

```text
You are continuing the NyayaSaar project after Stage 9 Precedent Explorer & Conflict Detector.

Read first:
- docs/stage-handoffs/stage-9.md
- docs/implementation-status.md
- docs/decisions.md
- apps/api/app/agents/graph_precedent.py
- apps/api/app/services/analysis.py
- apps/api/app/routers/analysis.py

Stages 1–9 are complete (Case Intelligence, Hybrid Legal Retrieval, Contradiction & Gap Hunter, and Precedent Explorer & Conflict Detector are all live).

Implement Stage 10 — Advocate Mode & Judge/Clerk Mode:
1. Build bounded LangGraph workflows for `workflow_type="advocate"` and `workflow_type="judge"` with deterministic verification, source-ref grounding, and HTML/Markdown report export.
2. Replace `/advocate` and `/judge` placeholders with live case-scoped workspaces.
3. Mandatory UI & Docs Sync (do NOT skip — no explicit user reminder should be needed):
   - Update all stage/status labels and alerts across:
     - `apps/web/src/app/(app)/dashboard/page.tsx` (Intelligence Modules badges & stat cards)
     - `apps/web/src/app/(app)/cases/[id]/page.tsx` (module descriptions & `?caseId=` links)
     - `apps/web/src/app/(app)/intelligence/intelligence-client.tsx` (top status banner)
     - `apps/web/src/app/(app)/settings/page.tsx` (DemoNotice)
     - `apps/web/src/components/shared/case-ui.tsx` (`ComingSoonState` if still used)
   - Update `README.md`, `docs/implementation-status.md`, and `docs/stage-handoffs/stage-10.md`.
4. Run full backend `pytest` (outside sandbox on Windows if `asyncio.ProactorEventLoop` `socketpair` is blocked in sandbox), `pnpm.cmd --filter web type-check`, `lint`, `test`, and `build`.
```
