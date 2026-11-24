# Stage 6 Handoff — Case Intelligence Module

> Completed: 2026-11-24
> Verification: deterministic suite, migration round-trip, frontend checks, and a
> mock-provider HTTP smoke test pass. A live-provider smoke test is **not**
> verified: Gemini returned `503 UNAVAILABLE` and the local key was later absent.
> Scope: Stage 6 **Case Intelligence only**. Hybrid retrieval, contradiction/gap
> detection, precedent graphs, Advocate Mode, and Judge/Clerk Mode were **not**
> implemented. Untracked future-stage scaffolding remains in the working tree but
> is not imported or wired.

---

## 1. What was delivered

Stage 6 extends the existing Stage 5 LangGraph in place. The provider layer,
`workflow_runs` persistence, authenticated APIs, polling, and fixture honesty are
unchanged; the analysis workflow itself is now a two-specialist Case Intelligence
pipeline with deterministic chronology and verification.

### 1.1 Graph topology

```
START → orchestrator
orchestrator ─┬─(no usable sources)──────────────────→ finalize
              └─→ case_analyst
case_analyst ─┬─(error / budget)──────────────────────→ finalize
              └─→ evidence_analyst
evidence_analyst ─┬─(error / budget)──────────────────→ finalize
                  └─→ chronology_builder
chronology_builder → verifier
verifier ─┬─(revision, target=case_analyst)───────────→ case_analyst
          ├─(revision, target=evidence_analyst)───────→ evidence_analyst
          └─(verified / budget exhausted)─────────────→ finalize
finalize → END
```

| Node | Model call | Responsibility |
|---|---|---|
| `orchestrator` | no | Source planning, budgets, insufficient-source exit |
| `case_analyst` | yes | Facts, parties/entities, dates, procedural events, amounts |
| `evidence_analyst` | yes | Legal issues, evidence questions, uncertainties, inferences |
| `chronology_builder` | no | Deterministic date normalisation, ordering, ambiguity flags |
| `verifier` | no | Quote/span verification, support classification, revision request |
| `finalize` | no | Verified result assembly, version stamping, sanitised failure |

### 1.2 Contracts and versioning

`apps/api/app/agents/schemas.py` defines:

- Draft contracts: `CaseAnalysisDraft`, `EvidenceAnalysisDraft`, and their item
  models (`DraftSourceRef`, `DraftClaim`, `DraftParty`, `DraftEntity`,
  `DraftAmount`, `DraftProceduralEvent`, `DraftTimelineEvent`, `DraftKeyDate`,
  `DraftLegalIssue`, `DraftEvidenceQuestion`, `DraftUncertainty`).
- Verified contracts: `CaseAnalysisResult` and verified item models (including
  `VerifiedParty`) with `support` / quote verification fields.
- `VerificationSummary`, `VerificationCategoryCount`, `SourceStats`,
  `SourceManifestEntry`.
- Version constants:
  - `CASE_INTELLIGENCE_WORKFLOW_VERSION = "6.1.0"`
  - `CASE_INTELLIGENCE_PROMPT_VERSION = "2026-11-case-intelligence-v2"`
  - `CASE_INTELLIGENCE_RESULT_SCHEMA_VERSION = "6.1"`

These values are embedded in the result and persisted on `workflow_runs`
(migration `004`).

### 1.3 Source planning

`apps/api/app/agents/tools/sources.py` now:

- selects pages **round-robin across documents** so a long first file cannot
  starve the rest of the case;
- suppresses duplicate page text and counts `duplicate_pages_skipped`;
- treats pages shorter than `AGENT_MIN_SOURCE_CHARS` (default **40**) as
  usable-but-short, and skips pages with no usable text;
- records failed extraction, incomplete extraction, OCR requirement, and
  instruction-like text in `SourceStats` and notes;
- keeps a source manifest with real `document_id` + `page_number`.

`apps/api/app/agents/tools/dates.py` provides deterministic date normalisation:
ISO sort key, precision (`day` / `month` / `year`), and an explicit `ambiguous`
flag. Numeric `dd/mm` vs `mm/dd` defaults to day-first **and is flagged**, never
silently guessed.

`apps/api/app/agents/tools/injection.py` flags instruction-like source text and
provides sanitisation helpers used by the prompt builder.

### 1.4 Verification and citations

`apps/api/app/agents/nodes/verifier.py`:

- normalises whitespace/case and searches each claimed quote in the analysed
  excerpt;
- classifies each item as `supported`, `partially_supported` (source cited,
  quote not located), or `unsupported`;
- stores character offsets relative to the analysed excerpt when a quote is
  found, so the UI can highlight it;
- counts categories in `VerificationSummary`;
- verifies parties as structured records (`name`, optional `role`, source
  references, support, confidence) exactly like entities, so a party name cannot
  appear without a resolvable document/page reference (D-043);
- requests at most one bounded revision (`AGENT_MAX_VERIFIER_RETRIES=1`) and
  routes it to the specialist that produced the unsupported content.

Citations always resolve to a real `document_id` and `page_number` from the
source manifest. The UI highlights only when `quote_verified` is true and the
offsets are valid.

### 1.5 Report export

`apps/api/app/services/report.py` renders the **persisted verified result**:

- `format=html` — self-contained, escaped, print-ready document (browser
  "Print / Save as PDF"), served with
  `CSP: default-src 'none'; style-src 'unsafe-inline'; img-src data:`.
- `format=markdown` — `text/markdown` durable text export.

No model is called during export and no new facts are introduced.

Endpoint:

```
GET /api/v1/cases/{case_id}/analysis/{workflow_id}/report?format=html|markdown
```

### 1.6 Frontend

`apps/web/src/components/analysis/analysis-panel.tsx` is now the full Case
Intelligence workspace:

- document selector for ready documents + optional analyst focus;
- live queued/running progress polled from the API (no simulated progress);
- verification panel (supported / partial / unsupported counts and rate);
- executive summary, parties (name + procedural role, support badge, source
  chips), entities, amounts, source facts, procedural history, chronology with
  ambiguity flags, legal issues, evidence questions, uncertainties, and model
  inferences — visually separated;
- source dialog that opens the real document page and highlights a verified
  quote span when available, otherwise states the quote was not located;
- export: "Print / save PDF", "HTML report", "Markdown";
- rerun and failure recovery through the real retry endpoint.

`apps/web/src/app/(app)/intelligence/intelligence-client.tsx` is the module
entry point and selects the case before rendering the panel.

---

## 2. Changed and added files

### Backend — changed

```
apps/api/app/agents/schemas.py
apps/api/app/agents/state.py
apps/api/app/agents/graph.py
apps/api/app/agents/nodes/case_analyst.py
apps/api/app/agents/nodes/orchestrator.py
apps/api/app/agents/nodes/verifier.py
apps/api/app/agents/nodes/finalize.py
apps/api/app/agents/tools/sources.py
apps/api/app/ai/prompts/case_analysis.py
apps/api/app/config.py
apps/api/app/db/models/workflow.py
apps/api/app/routers/analysis.py
apps/api/app/schemas/analysis.py
apps/api/app/services/analysis.py
apps/api/tests/test_analysis_graph.py
```

### Backend — added

```
apps/api/app/agents/nodes/evidence_analyst.py
apps/api/app/agents/nodes/chronology_builder.py
apps/api/app/agents/tools/dates.py
apps/api/app/agents/tools/injection.py
apps/api/app/services/report.py
apps/api/alembic/versions/004_add_case_intelligence_metadata.py
apps/api/tests/test_case_intelligence.py
apps/api/tests/test_dates.py
apps/api/tests/test_source_planner.py
```

### Frontend / shared — changed

```
packages/shared/src/index.ts
apps/web/src/lib/api-client.ts
apps/web/src/lib/api/analysis.ts
apps/web/src/lib/api/analysis.test.ts
apps/web/src/components/analysis/analysis-panel.tsx
apps/web/src/app/(app)/intelligence/intelligence-client.tsx
```

### Docs — changed

```
.env.example
docs/implementation-status.md
docs/decisions.md (D-036 … D-042)
docs/architecture.md
docs/deployment.md
docs/stage-handoffs/stage-6.md (this file)
```

### Untracked future-stage files — deliberately left untouched

```
apps/api/app/agents/graphs_extended.py
apps/api/app/agents/schemas_extended.py
apps/api/app/agents/nodes/{advocate,contradiction,judge,precedent}_analyst.py
apps/api/app/ai/prompts/{advocate,contradiction,judge,precedent}.py
apps/api/test_gemini_adapter.py
apps/api/test_gemini_basic.py
apps/api/test_gemini_connection.py
apps/api/tests/test_gemini_connection.py
```

The future-stage agent files are incomplete (for example a missing
`wrap_untrusted` helper) and are **not imported**. `app/services/analysis.py`
dispatches only the Case Intelligence workflow; unknown workflow types fail with
`unsupported_workflow`. The opt-in Gemini test is excluded from the deterministic
suite because it requires a live key.

---

## 3. Environment variables

### New / changed for Stage 6

| Variable | Default | Notes |
|---|---|---|
| `AGENT_MAX_LLM_CALLS` | `5` | Was `3`; two specialist calls + one bounded revision + headroom |
| `AGENT_MIN_SOURCE_CHARS` | `40` | Was `120`; shorter pages are analysed but flagged |

All existing Stage 5 variables remain valid:

```
AI_PROVIDER, AI_MODEL, AI_API_KEY, AI_BASE_URL, AI_TIMEOUT_S,
AI_MAX_RETRIES, AI_STRUCTURED_RETRIES, AI_TEMPERATURE,
AI_MAX_OUTPUT_TOKENS, AI_JSON_MODE, AI_GEMINI_NATIVE_SCHEMA, AI_ALLOW_MOCK,
AGENT_EXECUTION_TIMEOUT_S, AGENT_MAX_INPUT_CHARS, AGENT_MAX_TOTAL_TOKENS,
AGENT_MAX_VERIFIER_RETRIES, AGENT_MAX_WORKFLOW_ATTEMPTS,
MAX_ANALYSIS_FOCUS_CHARS
```

No new secret is required. Provider keys stay server-side.

---

## 4. Exact commands and actual results

### Backend tests

Run from `apps/api/` with `.venv` (Python 3.11.9 in this environment):

```powershell
.venv/Scripts/python.exe -m pytest tests -q --ignore=tests/test_gemini_connection.py
```

Actual result:

```
163 passed in 36.46s
```

New Stage 6 test files:

```
tests/test_dates.py             5 passed
tests/test_source_planner.py    5 passed
tests/test_case_intelligence.py (verifier extensions incl. party provenance,
                                 report rendering, export API)
tests/test_analysis_graph.py    updated for two specialist calls and revision routing
```

`apps/api/tests/test_gemini_connection.py` is an untracked, opt-in live-provider
test. It fails collection without a Gemini key and is therefore excluded. No test
in the deterministic suite makes a network call.

### Migration round-trip (temporary SQLite)

```powershell
$db = Join-Path $env:TEMP "nyayasaar_stage6_migration.db"
$env:DATABASE_SYNC_URL = "sqlite:///$($db -replace '\\','/')"
.venv/Scripts/python.exe -m alembic upgrade head
```

Actual result:

```
Running upgrade  -> 001, initial schema
Running upgrade 001 -> 002, add documents and document_chunks tables
Running upgrade 002 -> 003, add workflow_runs table
Running upgrade 003 -> 004, add case intelligence version metadata
alembic_version = 004
workflow_runs version columns = ['workflow_version', 'prompt_version', 'result_schema_version']
```

### Mock-provider HTTP smoke test

A real Uvicorn server was started against a fresh SQLite database migrated to
`004`, with `AI_PROVIDER=mock` and `AI_MODEL=fixture`. The flow exercised the
actual HTTP API, background runner, persistence, report rendering, and ownership
checks:

```
register                          → 201
create case                       → 201
upload TXT document               → 201 (ready, 1 page)
POST .../analysis                 → 202 queued
GET  .../analysis/{workflow_id}   → completed, progress 100
versions                          → 6.1.0 / 2026-11-case-intelligence-v2 / 6.1
result                            → is_mock=true, 1 fact, 1 entity, 3 timeline events
verification                      → 11 total, 11 supported, 0 invalid refs
first fact source                 → real document_id, page 1, quote_verified=true
GET .../report?format=html        → 200 text/html (10,923 bytes)
GET .../report?format=markdown    → 200 text/markdown (5,004 bytes)
cross-user run / report           → 404 / 404
```

Fixture output deliberately contains no parties, so mock runs do not fabricate
party names. Party provenance is covered by a deterministic unit test with a
known source text.

### Live-provider smoke test (attempted, not verified)

`apps/api/.env` contained a Gemini key at the start of verification.
`GET /api/v1/ai/status` reported `provider=gemini`, `is_mock=false`,
`configured=true`. A tiny `generate_content` probe succeeded for
`gemini-3.5-flash-lite`. The full Case Analyst request then failed:

```
Graph: orchestrator → case_analyst → finalize
Error: Case analyst provider error code=provider_unavailable
       provider=gemini model=gemini-3.5-flash-lite
Final: status=failed outcome=provider_unavailable llm_calls=0 retry_count=0
Result: none
```

Direct Google SDK probes returned `503 UNAVAILABLE` ("This model is currently
experiencing high demand") for the full request across `gemini-3.1-flash-lite`,
`gemini-3.5-flash`, `gemini-3.6-flash`, `gemini-3.7-flash`, `gemini-3.8-flash`,
and `gemini-flash-lite-latest`; `gemini-2.5-flash` returned `404 NOT_FOUND`
("no longer available to new users"). This is upstream load-shedding, not a
schema rejection. Later, `apps/api/.env` no longer contained `AI_API_KEY`
(`len=0`), so no further live run was possible. **No live analysis result has
been verified** (D-044).

### Frontend

From the repository root (PowerShell execution policy blocks `pnpm.ps1`, so use
`pnpm.cmd`):

```powershell
pnpm.cmd --filter web type-check                # exit 0
pnpm.cmd --filter web lint                      # no warnings or errors
pnpm.cmd --filter web test                      # 27 passed (4 files), exit 0
pnpm.cmd --filter web build                     # exit 0; 15 routes compiled
pnpm.cmd --filter @nyayasaar/shared type-check  # exit 0
```

Vitest can print a PowerShell `NativeCommandError` wrapper while still exiting 0;
the reliable check is `$LASTEXITCODE`.

---

## 5. Manual steps still required

1. **Run migration `004` against real PostgreSQL.** Only SQLite was available
   here. Confirm `workflow_runs` has `workflow_version`, `prompt_version`, and
   `result_schema_version` after `alembic upgrade head`.
2. **Repeat the live-provider smoke test.** The key that was present during
   verification has since been removed from `apps/api/.env`, and the earlier
   attempt failed upstream with Gemini `503`. Restore a valid `AI_API_KEY`:
   - `GET /api/v1/ai/status` must show `configured: true`, `is_mock: false`;
   - run a Case Intelligence analysis on a small TXT/PDF with known text;
   - confirm parties, facts, entities, amounts, procedural events, and timeline
     entries each carry a real document/page reference;
   - confirm the verification panel shows sensible counts;
   - export HTML and Markdown and confirm both download.
   Record the actual provider/model and result in this handoff.
3. **Review short-page behaviour** on real documents. `AGENT_MIN_SOURCE_CHARS=40`
   was chosen to admit short orders while still flagging near-empty pages; adjust
   if the corpus needs a different threshold.
4. **Check the print view** in the target browsers (Chrome/Edge/Safari) and
   confirm "Print / Save as PDF" produces a usable report.

---

## 6. Known limitations

1. **Live-provider output is unverified** — the graph, verifier, API, and reports
   are verified with scripted/mock providers and a mock HTTP smoke test. The one
   live attempt reached Gemini but failed with `503 UNAVAILABLE` before any model
   output; the local key was later absent. Latency, token use, quote quality, and
   party extraction on real documents remain unverified until deployment (D-044).
2. **PostgreSQL migration `004` was not run against PostgreSQL** — verified on a
   temporary SQLite database only.
3. **Report export is HTML/Markdown, not server-generated PDF** — the HTML report
   is self-contained and print-ready; no PDF dependency was added.
4. **The runner is in-process** — no durable queue; a crash loses in-flight work
   and the run is marked failed/retryable on startup (D-029).
5. **Stage 6 is document-grounded only** — no external authority retrieval,
   precedent graph, contradiction detection, or advocate/judge modes. The prompt
   and verifier forbid inventing authorities.
6. **Source span offsets are excerpt-relative** — the UI highlights only when the
   verifier marked the quote verified and offsets are valid.
7. **Untracked future-stage files remain** — they are user-owned, incomplete, and
   unwired. Do not import them until they are finished and explicitly tested.
8. **Prompt injection is mitigated, not eliminated** — instruction-like text is
   flagged and wrapped as untrusted evidence, but human review remains required.

---

## 7. Next-stage prerequisites

Before implementing the remaining Stage 6 modules (retrieval, contradictions,
precedent, advocate/judge) or Stage 7:

- [ ] Restore a valid `AI_API_KEY` and repeat the live-provider smoke test on a
      real deployment (the earlier attempt failed upstream with Gemini `503`).
- [ ] Run migration `004` against PostgreSQL (verified on SQLite only).
- [ ] Decide whether the remaining modules need a durable queue (Redis/Celery or
      managed queue) before adding longer retrieval workflows.
- [ ] Confirm the authority-corpus/licensing plan for precedent retrieval. Every
      authority needs a real provider and provenance; never fabricate citations.
- [ ] Decide the embedding model/provider separately from the chat model — the
      current `LLMProvider` is text-generation only.
- [ ] Review `AGENT_MAX_INPUT_CHARS` and token budgets for retrieval-heavy prompts.
- [ ] Complete and test the untracked future-stage scaffolding before wiring it;
      do not import incomplete modules into `app/services/analysis.py`.
- [ ] Keep the deterministic verifier, source manifest, and version metadata as
      non-negotiable output contracts.

---

## 8. Ready-to-paste continuation prompt

```text
You are continuing the NyayaSaar project after Stage 6 Case Intelligence.

Read first:
- docs/stage-handoffs/stage-6.md
- docs/implementation-status.md
- docs/decisions.md (especially D-036 to D-044)
- docs/architecture.md (Stage 6 section)
- apps/api/app/agents/{graph,state,schemas}.py
- apps/api/app/agents/nodes/* and apps/api/app/agents/tools/*
- apps/api/app/services/{analysis,report}.py
- apps/web/src/components/analysis/analysis-panel.tsx

Stage 6 Case Intelligence is complete: a two-specialist LangGraph
(case_analyst → evidence_analyst → deterministic chronology → deterministic
verifier → finalize), source planning with round-robin/dedup, span verification,
source-linked party records, persisted workflow/prompt/schema versions
(6.1.0 / 2026-11-case-intelligence-v2 / 6.1), authenticated HTML/Markdown
report export, and a full Case Intelligence workspace. Backend: 163 tests pass
(excluding the opt-in live Gemini test). Frontend: 27 tests pass, type-check,
lint, and build pass. A mock-provider HTTP smoke test passed end to end. The
live-provider smoke test did NOT complete: Gemini returned 503 UNAVAILABLE for
the full analyst request and the local key was later absent. Do not describe
live analysis as verified until a real-key run succeeds.

Implement the remaining Stage 6 legal-analysis modules only:
1. Hybrid retrieval over document chunks (PostgreSQL full-text + pgvector
   embeddings), with a separate embedding-provider abstraction.
2. Contradiction/gap detection across documents, with deterministic evidence and
   source-linked findings.
3. Precedent Explorer backed by a real, licensed/configured authority corpus.
   Every authority must have provenance (provider, URL/identifier, retrieval
   time). Never fabricate citations, holdings, or precedential status.
4. Advocate Mode and Judge/Clerk Mode as real workflows, not placeholder pages.
5. Preserve existing contracts: typed LangGraph state, deterministic verification,
   document_id + page_number (+ span) for every source, bounded
   retries/timeouts/token budgets, authenticated case-scoped APIs, honest fixture
   labelling, persisted versions, no fake UI data or buttons.
6. Extend workflow_runs/API/UI for new workflow types; keep polling, not long
   synchronous requests.
7. Add deterministic tests that mock all AI/retrieval calls: valid/invalid output,
   provider errors, timeouts, retries, authorization, source preservation,
   authority provenance, and prompt-injection resistance.
8. Update docs/implementation-status.md, docs/decisions.md, docs/architecture.md,
   docs/deployment.md, .env.example, READMEs, and create
   docs/stage-handoffs/stage-7.md (or the appropriate next handoff) with exact
   commands/results, limitations, manual steps, and next-stage prerequisites.

Constraints:
- Do not implement Stage 7 (evaluation/monitoring/CI) beyond what the remaining
  Stage 6 modules strictly need.
- Do not expose AI/retrieval keys to the frontend, API responses, logs, or
  workflow rows.
- Uploaded documents remain untrusted; defend against prompt injection.
- The untracked future-stage scaffolding files are incomplete. Complete and test
  them before importing; do not leave broken imports in the app startup path.
- If a real authority corpus or embedding provider is unavailable, implement the
  interface and use a clearly labelled fixture — never present fixture
  authorities as real law.
- Report exact commands and actual results. Do not claim a live AI/retrieval call
  succeeded unless it did.
```
