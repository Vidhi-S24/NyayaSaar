# Stage 5 Handoff — Provider-Agnostic AI and LangGraph Case Analysis

> Completed: 2026-11-20
> Scope: Stage 5 only. Stage 6 (full Case Intelligence, hybrid retrieval, contradictions, precedent, advocate/judge) was **not** implemented.

---

## 1. What was delivered

### 1.1 Provider-agnostic AI layer

Agent nodes depend only on `LLMProvider` (`apps/api/app/ai/base.py`). Provider/model changes are environment-only.

| Adapter | Transport | Notes |
|---|---|---|
| `gemini` | Official `google-genai` SDK | Default provider; key server-side only |
| `openai` | `httpx` → Chat Completions | Uses `AI_BASE_URL` or OpenAI default |
| `openai_compatible` | `httpx` → Chat Completions | Groq, OpenRouter, Together, DeepSeek, Ollama, LM Studio, compatible gateways |
| `anthropic` | `httpx` → Messages API | `x-api-key`, version header |
| `mock` | none | Deterministic, clearly labelled development fixture |

`generate_structured()` enforces:
- per-request timeout (`AI_TIMEOUT_S`)
- bounded transport retries for timeouts/429/5xx (`AI_MAX_RETRIES`)
- bounded JSON repair attempts (`AI_STRUCTURED_RETRIES`)
- Pydantic schema validation before any agent sees output
- token accounting and safe errors (no prompts, document text, vendor bodies, or keys)

Safe status: `GET /api/v1/ai/status` returns provider, requested provider, model, `is_mock`, `configured`, and a message. It never returns the key.

### 1.2 Real LangGraph workflow

```
START → orchestrator ──(no usable sources)────────────────→ finalize → END
             │
             └→ case_analyst ──(provider/invalid output)───→ finalize → END
                        │
                        └→ verifier ──(partial/unsupported, budget left)──→ case_analyst
                                   │
                                   └──(verified / retry exhausted)──→ finalize → END
```

- Typed `CaseAnalysisState` (`TypedDict`, JSON-serialisable).
- **orchestrator** — deterministic source check; never calls a model.
- **case_analyst** — one structured model call; enforces call/token budgets.
- **verifier** — deterministic, no model call. Resolves `S1` markers to real document IDs/pages, checks quotes, classifies `supported` / `partially_supported` / `unsupported`, counts invalid refs, flags authority-like strings, requests at most one revision.
- **finalize** — always produces a result or a sanitised failure.

Bounded by `AGENT_EXECUTION_TIMEOUT_S`, `AGENT_MAX_LLM_CALLS`, `AGENT_MAX_INPUT_CHARS`, `AGENT_MAX_TOTAL_TOKENS`, `AGENT_MAX_VERIFIER_RETRIES`, and `AGENT_MAX_WORKFLOW_ATTEMPTS`.

### 1.3 Persistence and recovery

- New `workflow_runs` table (Alembic `003`): status, progress, current step, provider/model/is_mock, input, verified result, bounded step history, token usage, sanitised error, attempt count, timestamps.
- Runs are created `queued`, executed by a FastAPI `BackgroundTasks` runner in the web process, and polled by the client.
- On startup, any interrupted `queued`/`running` runs are marked `failed` with `interrupted_by_restart` and can be retried.
- LangGraph uses an in-process `MemorySaver`; durable cross-restart graph resume is **not** implemented (see limitations).

### 1.4 API (all authenticated + case-ownership enforced)

```
POST /api/v1/cases/{case_id}/analysis                    202 queued run
GET  /api/v1/cases/{case_id}/analysis                    recent runs
GET  /api/v1/cases/{case_id}/analysis/{workflow_id}      status + result
POST /api/v1/cases/{case_id}/analysis/{workflow_id}/retry
GET  /api/v1/ai/status
```

Behaviour:
- Cross-user case access returns 404 (no existence leak).
- A second start while one is queued/running returns 409 with the active workflow ID.
- Selected documents must belong to the case and be `processing_status="ready"`; otherwise 422.
- Only `failed` runs can be retried, up to `AGENT_MAX_WORKFLOW_ATTEMPTS`.
- `POST` returns immediately; no long synchronous request.

### 1.5 Frontend

- `apps/web/src/components/analysis/analysis-panel.tsx` — real start, polling (2 s while active), progress/steps, provider/fixture badge, failure + retry, structured results, verification score, source viewer.
- `apps/web/src/lib/api/analysis.ts` — typed wrappers + honest view helpers.
- Case workspace has a new **Analysis** tab. No fake buttons, fake progress, or placeholder results.
- Fixture output is explicitly labelled: "Development fixture — no AI model was called".
- Every fact/issue/timeline entry shows support status and opens the exact document page.

### 1.6 Prompt-injection and honesty controls

- Document text is wrapped in `<untrusted_document>`; control characters removed; wrapper tags inside text escaped.
- System prompt states document text is evidence, not instructions; embedded instructions must be ignored and noted.
- Stage 5 analyst is forbidden from citing statutes/cases because no authority corpus is connected.
- Citation-like strings (`AIR`, `SCC`, `SCR`, etc.) are flagged in verification notes.
- Unsupported claims are surfaced, never silently deleted.
- Result limitations always include: no external authority database consulted; professional verification required.

---

## 2. Files added / changed

### Backend — added

```
apps/api/app/ai/__init__.py
apps/api/app/ai/base.py
apps/api/app/ai/registry.py
apps/api/app/ai/prompts/__init__.py
apps/api/app/ai/prompts/case_analysis.py
apps/api/app/ai/providers/__init__.py
apps/api/app/ai/providers/gemini.py
apps/api/app/ai/providers/openai_compatible.py
apps/api/app/ai/providers/anthropic.py
apps/api/app/ai/providers/mock.py
apps/api/app/agents/__init__.py
apps/api/app/agents/context.py
apps/api/app/agents/state.py
apps/api/app/agents/schemas.py
apps/api/app/agents/graph.py
apps/api/app/agents/nodes/__init__.py
apps/api/app/agents/nodes/orchestrator.py
apps/api/app/agents/nodes/case_analyst.py
apps/api/app/agents/nodes/verifier.py
apps/api/app/agents/nodes/finalize.py
apps/api/app/agents/tools/__init__.py
apps/api/app/agents/tools/sources.py
apps/api/app/db/models/workflow.py
apps/api/alembic/versions/003_add_workflow_runs.py
apps/api/app/schemas/analysis.py
apps/api/app/services/analysis.py
apps/api/app/routers/analysis.py
apps/api/app/routers/ai.py
apps/api/tests/test_ai_providers.py
apps/api/tests/test_verifier.py
apps/api/tests/test_analysis_graph.py
apps/api/tests/test_analysis_api.py
```

### Backend — changed

```
apps/api/app/config.py                 AI/agent settings + provider helpers
apps/api/app/main.py                   lifespan runner, stale recovery, routers
apps/api/app/db/models/__init__.py     export WorkflowRun
apps/api/alembic/env.py                import workflow model
apps/api/requirements.txt              pinned AI/graph stack
apps/api/tests/conftest.py             test runner + fixture provider wiring
```

### Frontend — added

```
apps/web/src/lib/api/analysis.ts
apps/web/src/lib/api/analysis.test.ts
apps/web/src/components/analysis/analysis-panel.tsx
```

### Frontend — changed

```
packages/shared/src/index.ts           real workflow/analysis types
apps/web/src/app/(app)/cases/[id]/page.tsx  Analysis tab
```

### Docs — changed

```
README.md
apps/api/README.md
.env.example
docs/implementation-status.md
docs/decisions.md (D-024 … D-032)
docs/architecture.md
docs/deployment.md
docs/stage-handoffs/stage-5.md (this file)
```

### Pre-existing fixes required to reach a green baseline

- Removed a duplicate `document_chunks.document_id` index in `app/db/models/document.py`.
- Replaced removed `UploadFile.__aiter__` usage with a bounded `await upload.read(...)` loop in `app/routers/documents.py`.
- Set `HTTPBearer(auto_error=False)` and explicit 401 in `app/services/auth.py`; updated auth/case tests from 403 to 401.

---

## 3. Environment variables

### AI provider

| Variable | Default | Purpose |
|---|---|---|
| `AI_PROVIDER` | `gemini` | `gemini`, `openai`, `openai_compatible`, `anthropic`, `mock` |
| `AI_MODEL` | provider default | Model ID; no code change needed |
| `AI_API_KEY` | empty | Provider key; server-side only |
| `AI_BASE_URL` | provider default | Required for `openai_compatible`; optional gateway override |
| `AI_TIMEOUT_S` | `45` | Per-request timeout |
| `AI_MAX_RETRIES` | `2` | Timeout/429/5xx retries |
| `AI_STRUCTURED_RETRIES` | `1` | Invalid-JSON repair attempts |
| `AI_TEMPERATURE` | `0.2` | Model temperature |
| `AI_MAX_OUTPUT_TOKENS` | `4096` | Output token cap |
| `AI_JSON_MODE` | `json_object` | `none` / `json_object` / `json_schema` for compatible APIs |
| `AI_GEMINI_NATIVE_SCHEMA` | `true` | Pass native schema to Gemini |
| `AI_ALLOW_MOCK` | unset | Defaults to allowed outside production; must be `true` to allow fixture in production |

Legacy compatibility: `GEMINI_API_KEY` and `GEMINI_MODEL_ID` are used when `AI_PROVIDER=gemini` and the new variables are empty.

### Agent budgets

| Variable | Default |
|---|---|
| `AGENT_EXECUTION_TIMEOUT_S` | `120` |
| `AGENT_MAX_LLM_CALLS` | `3` |
| `AGENT_MAX_INPUT_CHARS` | `24000` |
| `AGENT_MAX_TOTAL_TOKENS` | `80000` |
| `AGENT_MAX_VERIFIER_RETRIES` | `1` |
| `AGENT_MAX_WORKFLOW_ATTEMPTS` | `2` |
| `MAX_ANALYSIS_FOCUS_CHARS` | `1000` |

---

## 4. Exact commands and actual results

All backend commands run from `apps/api/` with `.venv` (Python 3.13.17).

### Backend test suite

```powershell
.venv/Scripts/python.exe -m pytest tests -q
```

Actual result:

```
127 passed, 5 warnings in 25.90s
```

New Stage 5 tests (52):

```
tests/test_ai_providers.py     21 passed
tests/test_verifier.py         11 passed
tests/test_analysis_graph.py    6 passed
tests/test_analysis_api.py     14 passed
```

The 5 warnings are pre-existing PyMuPDF/SWIG deprecation warnings from `test_documents.py::test_upload_pdf_success`; no failures.

### Migration round-trip (temporary SQLite)

```powershell
$env:DATABASE_SYNC_URL='sqlite:///./stage5-migration-test.db'
.venv/Scripts/python.exe -m alembic upgrade head
```

Actual result:

```
Running upgrade  -> 001, initial schema
Running upgrade 001 -> 002, add documents and document_chunks tables
Running upgrade 002 -> 003, add workflow_runs table
tables: ['alembic_version', 'case_memberships', 'cases', 'document_chunks',
         'documents', 'users', 'workflow_runs']
version: ['003']
```

The temporary database was deleted after the check.

### Frontend

```powershell
cmd /c "pnpm --filter @nyayasaar/web type-check"
# → exit 0 (tsc --noEmit, no output)

cmd /c "pnpm --filter @nyayasaar/web test"
# → 4 files passed, 27 tests passed

cmd /c "pnpm --filter @nyayasaar/web build"
# → exit 0; compiled successfully; 15 routes generated
```

### What was **not** executed

- No real Gemini/OpenAI/Anthropic API call. No key was available locally.
- No live browser session against a real provider.
- No PostgreSQL migration run (SQLite only; local policy blocks some compiled drivers).

Provider correctness is covered by:
- an injected fake Gemini SDK client (`GeminiProvider(..., client=FakeClient())`);
- `httpx.MockTransport` for OpenAI-compatible and Anthropic;
- scripted providers for graph retry/timeout/budget tests;
- the deterministic fixture for end-to-end API/UI tests.

---

## 5. How to run locally

### Backend

```powershell
cd apps/api
python -m venv .venv            # Python 3.13
.venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Optional: real provider
$env:AI_PROVIDER="gemini"
$env:AI_MODEL="gemini-2.5-flash"
$env:AI_API_KEY="<key>"

# No key outside production → clearly-labelled fixture mode.

# SQLite dev fallback (no DATABASE_URL): startup creates missing tables,
# including workflow_runs. For PostgreSQL:
#   $env:DATABASE_URL="postgresql+asyncpg://..."
#   $env:DATABASE_SYNC_URL="postgresql+psycopg://..."
#   alembic upgrade head

uvicorn app.main:app --reload --port 8000
```

### Frontend

```powershell
# From repo root
pnpm install
$env:NEXT_PUBLIC_API_BASE_URL="http://localhost:8000"
cmd /c "pnpm dev:web"
# → http://localhost:3000
```

### Try the workflow

1. Register/sign in.
2. Create a case.
3. Upload a TXT or text PDF in **Documents**.
4. Open **Analysis** → **Run analysis**.
5. Watch progress; the panel polls until completion.
6. Click any source chip to open the exact document page.
7. With no key, verify the fixture badge and limitation text are visible.

### Provider swap examples (no code changes)

```powershell
# OpenAI
$env:AI_PROVIDER="openai"; $env:AI_MODEL="gpt-4.1-mini"; $env:AI_API_KEY="<key>"

# Groq (OpenAI-compatible)
$env:AI_PROVIDER="openai_compatible"
$env:AI_BASE_URL="https://api.groq.com/openai/v1"
$env:AI_MODEL="llama-3.3-70b-versatile"
$env:AI_API_KEY="<key>"

# Local Ollama (no key required)
$env:AI_PROVIDER="openai_compatible"
$env:AI_BASE_URL="http://localhost:11434/v1"
$env:AI_MODEL="llama3.1"
$env:AI_API_KEY=""
```

Restart the API after changing environment variables. Check `GET /api/v1/ai/status`.

---

## 6. API examples

### Start

```http
POST /api/v1/cases/{case_id}/analysis
Authorization: Bearer <token>
Content-Type: application/json

{ "document_ids": [], "focus": "Focus on the termination clause and notice dates." }
```

`202 Accepted`:

```json
{
  "success": true,
  "data": {
    "id": "…",
    "case_id": "…",
    "workflow_type": "case_analysis",
    "status": "queued",
    "progress": 0,
    "is_mock": false,
    "result": null,
    "error": null,
    "attempt_count": 0
  },
  "meta": { "poll_after_ms": 1500 }
}
```

### Poll

```http
GET /api/v1/cases/{case_id}/analysis/{workflow_id}
Authorization: Bearer <token>
```

Completed result shape (abridged):

```json
{
  "success": true,
  "data": {
    "id": "…",
    "status": "completed",
    "progress": 100,
    "provider": "gemini",
    "model": "gemini-2.5-flash",
    "is_mock": false,
    "result": {
      "summary": "…",
      "facts": [
        {
          "claim": "…",
          "claim_type": "fact",
          "support": "supported",
          "sources": [
            {
              "source_id": "S1",
              "document_id": "…",
              "document_name": "agreement.pdf",
              "page_number": 3,
              "quote": "…",
              "quote_verified": true
            }
          ]
        }
      ],
      "legal_issues": [],
      "timeline": [],
      "inferences": [],
      "unverified_hypotheses": [],
      "missing_information": [],
      "limitations": ["…"],
      "verification": {
        "total_claims": 1,
        "supported": 1,
        "partially_supported": 0,
        "unsupported": 0,
        "invalid_source_refs": 0,
        "retried": false,
        "notes": []
      },
      "source_manifest": []
    }
  }
}
```

### Retry

```http
POST /api/v1/cases/{case_id}/analysis/{workflow_id}/retry
Authorization: Bearer <token>
```

Only failed runs; 422 when the attempt limit is reached or the run is not failed.

---

## 7. Limitations and risks

1. **No live provider verification** — the adapters are mock-tested. Run the deployment smoke test in `docs/deployment.md` with a real key before claiming production readiness.
2. **In-process runner** — no durable queue. A crash/restart marks the run failed; it is retryable, but the in-flight task is lost. LangGraph `MemorySaver` is in-process only.
3. **Source budget truncation** — very large cases exceed `AGENT_MAX_INPUT_CHARS`; omissions/truncation are reported in notes, not hidden.
4. **Prompt injection is mitigated, not solved** — wrappers + escaping + deterministic verification + authority-citation flags reduce risk; human review is still mandatory.
5. **No external legal authority retrieval** — deliberate Stage 5 boundary. The analyst must not cite statutes/cases. Stage 6 must add provenance and authority validation.
6. **PostgreSQL not exercised locally** — migration `003` verified on SQLite. Verify on the target PostgreSQL instance.
7. **Dev SQLite auto-create** — startup creates missing tables when `DATABASE_URL` is unset. Production must use Alembic.
8. **Retry uses module-level settings** — `analysis.py` reads `get_settings()` at import for retry limits. Changing env requires a restart (normal for deployment).
9. **No rate limiting** — a user can start one analysis per case at a time, but global rate limiting is Stage 7.
10. **Fixture content is deterministic and non-substantive** — it exercises the pipeline and is labelled everywhere; it must never be presented as legal analysis.

---

## 8. Stage 6 prerequisites

Before starting Stage 6:

- [ ] A real provider key is configured and `GET /api/v1/ai/status` reports `is_mock: false`.
- [ ] One real analysis run succeeds against a TXT/PDF with verifiable page citations.
- [ ] PostgreSQL is available and `alembic upgrade head` has applied `001`–`003`; verify `workflow_runs` exists.
- [ ] Decide whether Stage 6 needs a durable queue. If yes, add Redis/Celery (or a managed queue) and move the runner out of the web process before adding longer retrieval workflows.
- [ ] Confirm the authority-corpus/licensing plan for precedent retrieval. Stage 6 must not fabricate citations; every authority needs a real provider and provenance.
- [ ] Decide embedding model/provider separately from the chat model (the current `LLMProvider` is text-generation only).
- [ ] Review `AGENT_MAX_INPUT_CHARS`/token budgets for retrieval-heavy prompts.
- [ ] Keep the deterministic verifier and source manifest as non-negotiable output contracts.

---

## 9. Ready-to-paste Stage 6 continuation prompt

```text
You are continuing the NyayaSaar project (E:\Projects\NyayaSaar) after Stage 5.

Read first:
- docs/stage-handoffs/stage-5.md
- docs/implementation-status.md
- docs/decisions.md (especially D-024 to D-032)
- docs/architecture.md (Stage 5 section)
- apps/api/app/agents/*, apps/api/app/ai/*, apps/api/app/services/analysis.py
- apps/web/src/components/analysis/analysis-panel.tsx

Stage 5 is complete: provider-agnostic AI adapters, a real LangGraph case-analysis
workflow with a deterministic verifier, authenticated start/status/result/retry APIs,
persisted workflow_runs, and a case-workspace Analysis tab. Backend: 127 tests pass.
Frontend: 27 tests pass, type-check and build pass. No live provider key was available,
so real-provider calls still need a deployment smoke test.

Implement Stage 6 only: full Legal Analysis Modules.
Scope:
1. Case Intelligence enrichment: hybrid retrieval over document chunks
   (PostgreSQL full-text + pgvector embeddings), contradiction/gap detection,
   timeline consolidation, and stronger source-linked findings.
2. Precedent Explorer backed by a real, licensed/configured authority corpus.
   Every authority must have provenance (provider, URL/identifier, retrieval time).
   Never fabricate citations, holdings, or precedential status.
3. Advocate Mode and Judge/Clerk Mode as real workflows, not placeholder pages.
4. Reuse the existing LLMProvider abstraction. Do not add provider-specific logic
   to graph nodes. Add an embedding-provider abstraction separately if needed.
5. Preserve the Stage 5 contracts: typed LangGraph state, deterministic verification,
   document_id + page_number for every source, bounded retries/timeouts/token budgets,
   authenticated case-scoped APIs, honest fixture labelling, no fake UI data.
6. Extend workflow_runs/API/UI for the new workflow types; keep polling, not long
   synchronous requests.
7. Add tests that mock all AI/retrieval calls: valid output, invalid output, provider
   errors, timeouts, retries, authorization, source preservation, authority provenance,
   and prompt-injection resistance.
8. Update docs/implementation-status.md, docs/decisions.md, docs/architecture.md,
   docs/deployment.md, .env.example, READMEs, and create docs/stage-handoffs/stage-6.md
   with exact commands/results, limitations, run instructions, and Stage 7 prerequisites.

Constraints:
- Do not implement Stage 7 (evaluation/monitoring/CI) beyond what Stage 6 strictly needs.
- Do not expose AI/retrieval keys to the frontend, API responses, logs, or workflow rows.
- Uploaded documents remain untrusted; defend against prompt injection.
- If a real authority corpus or embedding provider is unavailable, implement the
  interface and use a clearly labelled fixture — never present fixture authorities
  as real law.
- Report exact commands and actual results. Do not claim a live AI/retrieval call
  succeeded unless it did.
```
