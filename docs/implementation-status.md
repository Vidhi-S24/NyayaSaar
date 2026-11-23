# NyayaSaar — Implementation Status

> Updated: Stage 5 complete

---

## Completed stages

### Stage 5 — Provider-agnostic AI and LangGraph case analysis ✅

**Completed:** 2026-11-20
*(See stage-handoffs/stage-5.md for full details, commands, and limitations)*

#### What was built

| Path | Description |
|---|---|
| `apps/api/app/ai/base.py` | `LLMProvider` ABC, structured request/result, bounded retries/timeouts, Pydantic validation, sanitised errors |
| `apps/api/app/ai/providers/gemini.py` | Official `google-genai` SDK adapter (key server-side only) |
| `apps/api/app/ai/providers/openai_compatible.py` | OpenAI/Groq/OpenRouter/Together/Ollama/LM Studio/gateway adapter via `httpx` |
| `apps/api/app/ai/providers/anthropic.py` | Anthropic Messages API adapter via `httpx` |
| `apps/api/app/ai/providers/mock.py` | Clearly-labelled deterministic development fixture |
| `apps/api/app/ai/registry.py` | `AI_PROVIDER`/`AI_MODEL`/`AI_API_KEY`/`AI_BASE_URL` selection + safe status |
| `apps/api/app/ai/prompts/case_analysis.py` | Prompt builder with prompt-injection wrappers and schema contract |
| `apps/api/app/agents/graph.py` | LangGraph: orchestrator → case analyst → deterministic verifier → finalize |
| `apps/api/app/agents/nodes/*` | Orchestrator, analyst, verifier, finalize nodes |
| `apps/api/app/agents/tools/sources.py` | Bounded source loading, S-marker resolution, quote verification |
| `apps/api/app/agents/schemas.py` | Draft vs verified contracts; source manifest and verification summary |
| `apps/api/app/db/models/workflow.py` | `WorkflowRun` persistence model |
| `apps/api/alembic/versions/003_add_workflow_runs.py` | Migration `003` |
| `apps/api/app/services/analysis.py` | Create/list/get/retry, bounded in-process runner, stale-run recovery |
| `apps/api/app/routers/analysis.py` | Start/status/result/list/retry endpoints (all ownership-gated) |
| `apps/api/app/routers/ai.py` | `GET /api/v1/ai/status` (no secrets) |
| `apps/api/app/schemas/analysis.py` | API schemas for runs and status |
| `apps/api/tests/test_ai_providers.py` | 23 provider/registry tests (mocked SDK/HTTP, retries, timeouts, auth, production fixture policy, Gemini schema simplification) |
| `apps/api/tests/test_verifier.py` | 11 verifier/source-preservation/prompt-safety tests |
| `apps/api/tests/test_analysis_graph.py` | 6 graph tests (success, insufficient sources, errors, retries, budgets) |
| `apps/api/tests/test_analysis_api.py` | 14 API tests (auth, polling, retries, conflicts, provider failure recovery, source IDs/pages) |
| `packages/shared/src/index.ts` | Real workflow/analysis types aligned with the API |
| `apps/web/src/lib/api/analysis.ts` | Typed analysis API + honest view helpers |
| `apps/web/src/components/analysis/analysis-panel.tsx` | Start/poll/result UI, verification counts, source viewer, fixture labelling |
| `apps/web/src/app/(app)/cases/[id]/page.tsx` | Analysis tab wired into the case workspace |
| `apps/web/src/lib/api/analysis.test.ts` | 7 frontend API/helper tests |

#### Acceptance criteria status

| Criterion | Status |
|---|---|
| Gemini via official SDK, key server-side only | ✅ Adapter implemented; live key not available locally (mocked SDK test only) |
| Provider/model swap by configuration only | ✅ `gemini`, `openai`, `openai_compatible`, `anthropic`, `mock` behind one interface |
| Genuine typed LangGraph with conditional routing | ✅ Typed state; orchestrator/analyst/verifier/finalize; bounded revision loop |
| Bounded retries, timeouts, token/call budgets | ✅ Per-request timeout, transport retries, repair attempts, graph budgets, run timeout |
| Facts/inferences/hypotheses separated | ✅ Separate result collections; UI labels each |
| Document IDs and page references preserved | ✅ Verifier resolves markers to real `document_id` + `page_number`; tests assert it |
| Authenticated start/status/result APIs | ✅ 202 start + polling; ownership enforced; 404 cross-user |
| Recoverable failures | ✅ Failed runs retryable; interrupted runs marked failed on startup |
| No fake UI data/buttons | ✅ Real endpoints, real progress/steps, explicit fixture and empty states |
| Tests mock all AI calls | ✅ 59 new backend tests; no network calls |
| Docs/handoff updated | ✅ This file, decisions, architecture, deployment, stage-5 handoff, env example, READMEs |

#### Verification results (actual)

```
apps/api:  .venv\Scripts\python.exe -m pytest tests -q
           → 134 passed (75 pre-existing + 59 new), 5 warnings
           alembic upgrade head (temp SQLite)
           → 001 → 002 → 003; tables include workflow_runs; version=003
apps/web:  pnpm --filter @nyayasaar/web type-check → exit 0
           pnpm --filter @nyayasaar/web test       → 27 passed (4 files)
           pnpm --filter @nyayasaar/web build      → exit 0; 15 routes compiled
```

#### Known Stage 5 limitations

1. **No live AI call was executed** in this environment (no Gemini/OpenAI/Anthropic key). Provider adapters are verified with an injected fake Gemini client and `httpx.MockTransport`; a real-key smoke test is a deployment step.
2. **In-process runner, not a durable queue** — a process crash loses in-flight work; startup recovery marks the row failed and retryable. LangGraph `MemorySaver` is in-process, so cross-restart graph resume is deferred (D-029).
3. **No external legal authority retrieval** — Stage 5 deliberately extracts only from uploaded documents and forbids statute/case citations. Contradictions, precedent, advocate, and judge modules remain Stage 6.
4. **Source budget is bounded** — very large document sets are truncated (`AGENT_MAX_INPUT_CHARS`, default 24k); the result records truncation/omission notes.
5. **Prompt injection is mitigated, not eliminated** — wrappers, escaping, verifier constraints, and authority-citation flags reduce risk; human review remains required.
6. **PostgreSQL migration not run here** — verified on SQLite only (local policy blocks some compiled drivers). First deploy must run `alembic upgrade head` against PostgreSQL.

---

### Stage 4 — Document Ingestion Pipeline ✅

**Completed:** 2026-11-18
*(See stage-handoffs/stage-4.md for full details)*

#### What was built

| Path | Description |
|---|---|
| `apps/api/app/db/models/document.py` | `Document` + `DocumentChunk` models; `ProcessingStatus` enum |
| `apps/api/alembic/versions/002_add_documents.py` | Migration: `documents` + `document_chunks` tables |
| `apps/api/app/schemas/documents.py` | Pydantic schemas for all document endpoints |
| `apps/api/app/services/storage.py` | `StorageProvider` ABC; `LocalStorageProvider`; `S3StorageProvider` stub |
| `apps/api/app/services/extraction.py` | `validate_upload()` (magic bytes + extension + size); `extract_pdf/docx/txt()` |
| `apps/api/app/services/documents.py` | Full document service: create, process, retry, list, get, chunks, delete |
| `apps/api/app/routers/documents.py` | 6 endpoints, all case-ownership-gated |
| `apps/api/tests/test_documents.py` | 16 HTTP integration tests |
| `apps/api/tests/test_extraction.py` | Unit tests for validation + extraction |
| `apps/api/tests/test_storage.py` | Unit tests for storage providers |
| `packages/shared/src/index.ts` | `Document`, `DocumentListResponse`, `DocumentChunk` types |
| `apps/web/src/lib/api/documents.ts` | Typed frontend API wrappers |
| `apps/web/src/lib/api-client.ts` | Added `upload()` method (FormData, auth-injected) |
| `apps/web/src/components/documents/document-upload.tsx` | Drag-and-drop upload panel |
| `apps/web/src/components/documents/document-list.tsx` | Document rows with status badges, delete, retry, preview |
| `apps/web/src/components/documents/document-text-preview.tsx` | Page-navigable extracted text viewer (XSS-safe) |
| `apps/web/src/app/(app)/cases/[id]/page.tsx` | Documents tab wired with real upload + list |
| `apps/web/src/app/(app)/documents/page.tsx` | Real document library across all cases |

#### Acceptance criteria status

| Criterion | Status |
|---|---|
| Upload + validate (extension, magic bytes, size) | ✅ |
| Safe storage keys + provider abstraction | ✅ |
| Text extraction with page-numbered chunks | ✅ |
| Scanned PDF detection + OCR extension point | ✅ |
| Processing status + bounded retries (3) | ✅ |
| Frontend upload, list, preview, delete, retry | ✅ |
| Case authorization on all endpoints | ✅ |
| Failures don't falsely mark as completed | ✅ |

#### Verification results (actual)

```
apps/api:  pytest tests/ -v  → 75 collected; all passed
           alembic upgrade head → 002_add_documents applied (SQLite dev)
apps/web:  tsc --noEmit      → 0 errors
           vitest run         → 20/20 passed (3 files)
           next build         → exit 0; 15 routes compiled
```

---

### Stage 3 — Database, Authentication, and Case Management ✅

**Completed:** 2026-11-13
*(See stage-handoffs/stage-3.md for full details)*

#### What was built

| Path | Description |
|---|---|
| `apps/api/alembic/` | Alembic setup + `001_initial_schema` migration (users, cases, case_memberships) |
| `apps/api/app/db/` | Async engine, session dependency, `TimestampMixin`, `User` / `Case` / `CaseMembership` models |
| `apps/api/app/services/auth.py` | bcrypt password hashing (passlib removed), PyJWT tokens, `get_current_user` dependency |
| `apps/api/app/services/cases.py` | Case CRUD service — **authorization enforced in SQL (owner-scoped)** |
| `apps/api/app/routers/auth.py` | `POST /auth/register`, `POST /auth/login`, `GET /auth/me` |
| `apps/api/app/routers/cases.py` | Full case CRUD with pagination, search, status filter, request IDs |
| `apps/api/app/schemas/` | Pydantic request/response schemas (auth + cases) |
| `apps/api/scripts/seed_demo.py` | Idempotent demo seed (demo user + 3 labelled [DEMO] cases) |
| `apps/api/tests/` | 25 tests: auth flows, case CRUD, **authorization boundaries**, validation |
| `apps/web/src/lib/auth/auth-context.tsx` | Session provider (restore/sign-in/sign-up/sign-out, 401 handling) |
| `apps/web/src/lib/api/auth.ts`, `cases.ts` | Typed API wrappers; helpers (`userInitials`, `formatRelativeTime`) |
| `apps/web/src/app/signin/page.tsx` | Sign-in / create-account page (react-hook-form + zod, error/loading states) |
| `apps/web/src/app/(app)/layout.tsx` | Auth guard — session restore loader + redirect to `/signin` |
| `apps/web/src/app/(app)/cases/page.tsx` | Live case list: search, status filter, pagination, create, delete confirm |
| `apps/web/src/app/(app)/cases/[id]/page.tsx` | Live case detail: edit, delete, 404/no-access state, issue/document tabs |
| `apps/web/src/app/(app)/dashboard/page.tsx` | Live case stats + recently updated cases; honest "not yet available" stats |
| `apps/web/src/components/cases/case-form-dialog.tsx` | Create/edit case dialog with unsaved-changes confirmation |
| `apps/web/src/components/ui/{dialog,alert-dialog,label}.tsx` | Radix-based UI primitives |
| `apps/web/src/components/layout/topbar.tsx` | Real account menu (initials, email, sign out); fake notification bell removed |
| `packages/shared/src/index.ts` | Types aligned with the real API (`Case`, `CaseListResponse`, `User`, `TokenResponse`) |

#### Acceptance criteria status

| Criterion | Status |
|---|---|
| Migrations create the schema from a clean database | ✅ Verified against SQLite (upgrade → downgrade → upgrade); PostgreSQL run is a first-deploy step (see D-015) |
| Case CRUD works through the actual frontend and backend | ✅ Verified via API round-trip (register → create → list → update → delete → 404) and frontend pages wired to live queries |
| Authorization enforced and tested | ✅ Owner-scoped SQL; tests prove cross-user 404s for GET/PATCH/DELETE and empty lists |
| API schemas and errors predictable | ✅ `ApiResponse` envelope, Pydantic validation (422), 409/401/403/404 semantics, X-Request-ID header |
| Tests cover key routes, validation, access boundaries | ✅ 25 backend tests + 15 frontend unit tests |
| Frontend build/type checks pass | ✅ `tsc --noEmit` 0 errors; `next build` succeeds; Vitest 15/15 |

#### Verification results (actual)

```
apps/api:  .venv\Scripts\python -m pytest tests/ -v
           → 25 passed (auth 9, cases 12, health 4)
apps/web:  tsc --noEmit            → 0 errors
           vitest run              → 15 passed (2 files)
           next build              → compiled, 15 routes generated
Live smoke: uvicorn (SQLite dev DB) + next dev
           register → 201, create case → 201, list → 200,
           me → 200, delete → 200, get-after-delete → 404
           demo login → 200 (sees 3 demo cases)
Alembic:   upgrade head → downgrade base → upgrade head (SQLite) → exit 0
```

---

### Stage 2 — Premium Frontend and Application Experience ✅

**Completed:** 2026-10-30

Full landing page, dashboard, case workspace, document library, module shells, design system (ink/navy/parchment/teal tokens), demo fixtures clearly labelled as such. *Note: `docs/stage-handoffs/stage-2.md` was not present in the repository when Stage 3 began; Stage 2 state was reconstructed from `docs/implementation-status.md` and the git history.*

### Post-handoff fixes (Stage 3 scope, user-reported)

1. **Dev database fallback** — the no-`DATABASE_URL` fallback was an in-memory SQLite DB (500 on every auth call, nothing persisted). Now a file DB (`apps/api/nyayasaar-dev.db`) with startup schema auto-creation. See `docs/decisions.md` D-019.
2. **API-client envelope mismatch** — the client unwrapped the response envelope while callers read `.data`, producing `undefined` crashes on login. Client now returns the full envelope; regression tests added. See `stage-handoffs/stage-3.md`.
3. **Stale `tsconfig.tsbuildinfo`** was masking real TypeScript errors; deleted and re-verified.

### Stage 1 — Repository Audit and Foundation ✅

**Completed:** 2026-10-29 *(See stage-handoffs/stage-1.md)*

---

## Pending stages

### Stage 6 — Legal Analysis Modules ⏳

**Prerequisites:** Stage 5 complete (✅), PostgreSQL + pgvector for retrieval

**Scope:**
- Full Case Intelligence enrichment: hybrid retrieval (full-text + embeddings), contradiction/gap detection
- Precedent Explorer with a configured legal-authority corpus and provenance checks
- Advocate and Judge/Clerk modules
- Durable background queue if analysis volume requires it

### Stage 7 — Evaluation, Monitoring, and Deployment ⏳

---

## Known limitations (current)

1. **No live AI provider call was executed locally** — adapters are tested with mocks; configure a key and run a real smoke test on deployment.
2. **PostgreSQL migrations not yet run against a real PostgreSQL instance** in this environment (no local Postgres/Docker; some compiled driver DLLs are blocked). Migration logic verified via SQLite round-trip (001→003). First production deploy must run `alembic upgrade head` and verify.
3. **Dev SQLite fallback is functional, not production-grade** — accounts persist in `apps/api/nyayasaar-dev.db`; startup creates missing tables (D-019). PostgreSQL is required for production and pgvector.
4. **JWT in localStorage** — vulnerable to XSS; mitigated by short expiry and server-side authorization. CSP and/or httpOnly cookie sessions are future hardening (Stage 7).
5. **Case sharing not yet active** — `case_memberships` exists but authorization is owner-only (D-016).
6. **Analysis runner is in-process** — not a durable queue; interrupted runs are marked failed on startup and can be retried (D-029).
7. **No external authority retrieval in Stage 5** — precedent/contradiction/advocate/judge modules and hybrid retrieval are Stage 6.
8. **Demo data surfaces remain** — history and several module shells still use clearly-labelled fixtures until Stage 6.
9. **Dashboard advanced stats** (reports/contradictions) remain placeholders until Stage 6.
10. **No rate limiting yet** (Stage 7).
11. **No email verification flow** — `users.is_verified` exists but is unused; verification mail is out of scope.
