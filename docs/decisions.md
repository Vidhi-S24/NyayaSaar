# NyayaSaar — Design Decisions

> This file records all significant architectural and technology decisions with rationale. New decisions are appended; old entries are preserved.

---

## Decision log

### D-001: pnpm workspaces monorepo

**Date:** Stage 1
**Decision:** Use pnpm workspaces as the monorepo tool.
**Rationale:** pnpm is faster than npm/yarn, has excellent workspace support, and is the standard for modern JS monorepos. `apps/web` and `packages/shared` share a lock file and hoisted dependencies. The Python API lives in `apps/api` but is not a pnpm package — it uses its own venv.
**Alternatives considered:** Turborepo (adds complexity without enough benefit at this stage), Nx (too heavy).

---

### D-002: Next.js 15 App Router

**Date:** Stage 1
**Decision:** Use Next.js 15 with the App Router (not Pages Router).
**Rationale:** App Router enables React Server Components, co-located layouts, streaming, and modern data patterns. This is the current recommended Next.js paradigm and is required for Vercel's edge capabilities.
**Alternatives considered:** Pages Router (legacy), Remix (less familiar, smaller ecosystem for this use case).

---

### D-003: FastAPI on Render, not Vercel serverless

**Date:** Stage 1
**Decision:** Deploy the FastAPI backend to Render (persistent web service), not Vercel serverless functions.
**Rationale:** Document processing (PyMuPDF, Docling, OCR) and LangGraph workflows are long-running and stateful. Vercel serverless functions have a 60-second timeout and are stateless — unsuitable for agentic workflows. Render provides persistent processes, configurable timeouts, and background worker support.
**Alternatives considered:** Vercel serverless (ruled out — timeout limits), AWS Lambda (overkill for this stage), Railway (similar to Render, less documentation).

---

### D-004: Google Gemini as the primary AI provider

**Date:** Stage 1
**Decision:** Use the official Google Gen AI SDK for Gemini. The model ID is configurable via `GEMINI_MODEL_ID` environment variable.
**Rationale:** Per project requirements. Keeps the option open to switch models (Flash → Pro → experimental) without code changes. API key is server-side only; never in the client bundle.
**Alternatives considered:** OpenAI (not specified), Anthropic (not specified).

---

### D-005: LangGraph for agentic orchestration

**Date:** Stage 1
**Decision:** Use LangGraph for all stateful multi-agent workflows.
**Rationale:** Per project requirements. LangGraph provides typed state, conditional routing, bounded retries, checkpoints, and resumability — the properties needed for legal research workflows that must be auditable and recoverable. Plain prompting chains are not sufficient.
**Alternatives considered:** LangChain LCEL chains (too linear, no checkpoints), CrewAI (less control over state), custom async orchestration (reinventing the wheel).

---

### D-006: PostgreSQL + pgvector as the primary data store

**Date:** Stage 1
**Decision:** Use PostgreSQL with pgvector for both relational data and vector search. Hybrid retrieval (full-text + vector) is the default strategy.
**Rationale:** Reduces infrastructure to one database (vs. separate vector DB). pgvector is well-maintained and sufficient for the expected document volumes. Full-text search covers keyword queries; vector search covers semantic similarity.
**Alternatives considered:** Pinecone (separate service, cost), Weaviate (complexity), SQLite (not production-suitable for multi-user), MongoDB (no strong reason to choose over PostgreSQL for this use case).

---

### D-007: Neo4j is optional

**Date:** Stage 1
**Decision:** Neo4j is an optional dependency for citation graph features. The core product must work without it.
**Rationale:** Citation graphs add value for precedent analysis, but adding a required graph database complicates setup and cost. Features that need Neo4j are gated behind `settings.neo4j_configured` and fail gracefully.
**Alternatives considered:** In-PostgreSQL graph (ltree, recursive CTEs) — possible future fallback.

---

### D-008: Redis + Celery deferred until needed

**Date:** Stage 1
**Decision:** Background jobs and Redis are not added until Stage 5+ when long-running document processing requires them.
**Rationale:** Premature infrastructure adds operational cost and complexity. FastAPI's background tasks (`BackgroundTasks`) are sufficient for short async work. Celery will be added when document ingestion pipelines require durable, retriable background processing.

---

### D-009: No `apps/worker` scaffolded in Stage 1

**Date:** Stage 1
**Decision:** The optional worker app is not scaffolded yet.
**Rationale:** It is not needed until Stage 5. Scaffolding it now would be speculative. It will be created as a separate Render service when Celery workers are required.

---

### D-010: Design system direction — ink/navy, parchment, teal

**Date:** Stage 1
**Decision:** The NyayaSaar colour palette uses deep ink/navy (primary), warm off-white/parchment (background), and restrained teal (accent).
**Rationale:** Legal-tech context demands trustworthiness, clarity, and authority. These colours are associated with traditional legal aesthetics (ink, parchment) while the teal accent provides a modern, digital feel. Avoids the generic AI dashboard look (electric blue gradients, glassmorphism, emoji icons).
**Tokens defined:** `ink-*`, `parchment-*`, `teal-*` in Tailwind config; CSS variables for shadcn/ui semantic tokens.

---

### D-011: Strict TypeScript throughout the frontend

**Date:** Stage 1
**Decision:** `"strict": true` in all TypeScript configs. Pydantic v2 with strict validation in the backend.
**Rationale:** Legal data requires correctness. Strict typing surfaces bugs at compile time rather than runtime. Shared types in `packages/shared` ensure the frontend and backend agree on data shapes.

---

### D-012: `ApiResponse<T>` envelope for all API responses

**Date:** Stage 1
**Decision:** Every API response is wrapped in `{ success, data, error, meta }`.
**Rationale:** Provides a consistent, machine-readable structure for clients regardless of HTTP status codes. Clients can always check `response.success` without parsing error formats differently per endpoint. Matches the TypeScript type in `packages/shared`.

---

## Stage 3 — Database, Authentication, and Case Management

### D-013: Backend-issued JWT bearer authentication (no NextAuth)

**Date:** Stage 3
**Decision:** Authentication is implemented directly in FastAPI: `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `GET /api/v1/auth/me`. Tokens are short-lived HS256 JWTs signed with `JWT_SECRET_KEY`. The Next.js frontend keeps the token in `localStorage` and sends it as a bearer header.
**Rationale:** FastAPI must enforce case-level authorization server-side, so the backend needs to be the single source of identity truth. Adding NextAuth as a second session layer would create two overlapping session systems with no benefit at this stage. A dedicated external auth provider (Auth0/Clerk/Supabase Auth) can replace the same three endpoints later without touching authorization logic.
**Alternatives considered:** NextAuth/Auth.js (duplicated session logic against the FastAPI backend; the `next-auth` dependency was added by mistake and removed), OAuth-only flows (no password login for private deployments), httpOnly cookie sessions (more secure against XSS but complicates cross-origin Vercel→Render fetches; revisit if the threat model changes).
**Limitations:** Token in `localStorage` is readable by XSS. Mitigations: strict CSP later, short expiry (30 min), server-side authorization on every case route.

### D-014: bcrypt directly (passlib removed), PyJWT (python-jose replaced)

**Date:** Stage 3
**Decision:** Password hashing uses the `bcrypt` library directly. Token encoding/decoding uses `PyJWT`.
**Rationale:** `passlib` is unmaintained (last release 2020) and crashes with `bcrypt ≥ 4.1` (verified: `ValueError: password cannot be longer than 72 bytes` raised from inside passlib's own backend detection with bcrypt 5.0). `python-jose` is similarly dormant. `bcrypt` and `PyJWT` are actively maintained and cover exactly the two functions we need. Passwords are bcrypt-hashed with the standard 72-byte truncation.
**Cost:** Existing hashes generated by passlib remain compatible (standard bcrypt format).

### D-015: SQLAlchemy pinned `<2.1` — compiled Cython extension blocked in sandboxed environments

**Date:** Stage 3
**Decision:** `SQLAlchemy>=2.0.36,<2.1.0` in `apps/api/requirements.txt`.
**Rationale:** SQLAlchemy 2.1.x requires its compiled `_util_cy` extension with no pure-Python fallback. On this development machine a Windows Application Control policy blocks the DLL (`ImportError: DLL load failed`). SQLAlchemy 2.0 ships a pure-Python fallback and imports cleanly. Same consideration applies to `psycopg[binary]`: the prebuilt DLL is blocked locally, but works on Linux deployment targets (Render).
**Consequence:** Alembic migrations were validated against SQLite in this environment. PostgreSQL behaviour must be verified on first deployment to a real PostgreSQL instance (documented in `docs/deployment.md`).

### D-016: Case authorization = ownership check returning 404

**Date:** Stage 3
**Decision:** All case queries filter by `owner_id` in SQL (`WHERE case_id = ? AND owner_id = ?`). A case belonging to another user is indistinguishable from a nonexistent case (404 for GET/PATCH/DELETE), and it never appears in list responses.
**Rationale:** Prevents resource-existence leakage without leaking a 403 that confirms the case exists. The `case_memberships` table exists for future sharing (roles: `owner`/`editor`/`viewer`); it is not yet used for authorization — that is deliberate scope control for Stage 3, and the membership wiring will switch `get_case` from owner-only to owner-or-member.

### D-017: Frontend session restore + client-side route guard

**Date:** Stage 3
**Decision:** `AuthProvider` restores the session on mount (token → `GET /auth/me` → user). The `(app)` route group renders a full-screen loading state while the session is being restored and redirects to `/signin` when unauthenticated. Every API call attaches the bearer token; a global 401 handler clears the session.
**Rationale:** Server components cannot see the browser token, so workspace pages are client components using TanStack Query. Authorization itself remains server-side; the guard is UX, not security.

### D-018: Seed script creates the schema when the database is empty

**Date:** Stage 3
**Decision:** `python -m scripts.seed_demo` creates tables via SQLAlchemy metadata if the target database has no tables, then seeds a demo user and three clearly `[DEMO]`-prefixed fictional cases. It is idempotent.
**Rationale:** Zero-config first-run experience for local development. Alembic remains the canonical migration path for real deployments (the script prints a reminder).

### D-019: Dev fallback is a file-based SQLite DB with startup auto-migration (was in-memory)

**Date:** Stage 3 (post-handoff fix — user-reported login failure)
**Decision:** When `DATABASE_URL` is unset, the API uses the SQLite file `apps/api/nyayasaar-dev.db` (git-ignored). On startup, if that database is empty, the app creates the schema via SQLAlchemy metadata and logs a reminder that Alembic is canonical for production.
**Rationale:** The original fallback was `sqlite:///:memory:`, which broke real use two ways: every connection in the async pool received a fresh empty database (causing intermittent `no such table: users` → HTTP 500 on register/login), and no account could persist across restarts. This was verified live: `POST /api/v1/auth/register` returned 500 with no `DATABASE_URL`, 201 after the fix.
**Consequence:** Users can sign up / sign in with zero configuration; data persists across server restarts. The seeded demo account (`demo@nyayasaar.example` / `demo-password-123`) is created by `python -m scripts.seed_demo`.


---

## Stage 4 — Document Ingestion Pipeline

### D-020: Synchronous extraction (no Celery worker in Stage 4)

**Date:** Stage 4
**Decision:** Document text extraction runs synchronously inside the upload request handler (`process_document()` called inline after `create_document()`). There is no background worker, Redis, or Celery in Stage 4.
**Rationale:** PyMuPDF text extraction is fast (< 1–2 s for typical legal documents up to ~50 MB). Keeping extraction synchronous avoids adding Redis + Celery infrastructure until there is a demonstrated need. The API returns `processing_status: "processing"` immediately after save, then sets it to `completed` or `failed` within the same request. The frontend polls for status changes.
**Alternatives considered:** Celery + Redis worker (rejected: unnecessary complexity before Stage 5 when LangGraph workflows also need a worker; defer both to the same infrastructure addition), FastAPI BackgroundTasks (rejected: not retriable, no durable state — if the process restarts mid-extraction the task is lost).
**Consequence:** Upload requests block until extraction completes. For very large files or OCR, this will become a timeout risk. When that happens, move `process_document()` into a Celery task (Stage 5 or 6). The service layer is already designed so that extraction is decoupled from the HTTP handler — the router calls `create_document()` then `process_document()`; changing to async task dispatch requires only changing the router call site, not the service itself.
**When to revisit:** When average extraction time exceeds 10 s, or when OCR is added.

---

### D-021: Storage key derived from UUID, never from user filename

**Date:** Stage 4
**Decision:** `make_storage_key()` generates storage paths from a UUID4 and the file extension only: `uploads/{case_id}/{uuid}.{ext}`. The original filename is stored in `Document.original_name` for display but never used in the file path.
**Rationale:** User-supplied filenames are untrusted. Path traversal (`../../etc/passwd`), null bytes, shell metacharacters, and Unicode normalization attacks are all neutralized by ignoring the filename entirely in the path. The extension is taken from the validated MIME/magic-byte check, not the client-supplied extension.

---

### D-022: Magic-byte validation; never trust client Content-Type

**Date:** Stage 4
**Decision:** `validate_upload()` reads the first 8 bytes of the uploaded file and checks them against known signatures for PDF, DOCX/ZIP, and TXT. The client-supplied `content_type` and file extension are cross-checked but do not override the magic-byte result.
**Rationale:** A malicious client can set any `Content-Type` header or any file extension. The magic-byte check is the only server-side control that reflects actual file content.
**What is checked:** `%PDF-` for PDF; `PK\x03\x04` for DOCX (which is a ZIP); printable UTF-8/ASCII for TXT. Files that fail the check are rejected with HTTP 415.

---

### D-023: Scanned PDF detection without full OCR

**Date:** Stage 4
**Decision:** After extracting a PDF page, if the extracted character count is below a threshold (< 50 chars per page on average) the document is flagged as `processing_status = "ocr_required"` rather than `completed`. A `processing_notes` field explains the situation.
**Rationale:** PyMuPDF cannot extract text from image-only PDFs — it returns empty strings. Rather than silently returning an empty extraction (which would be misleading to legal researchers), the platform explicitly reports that the document appears to be scanned and requires OCR. This is honest and actionable. OCR integration (Tesseract or EasyOCR) is an extension point for a future stage.
**Consequence:** Scanned documents show a clear "OCR required" status in the UI. Users are not misled into thinking the document was analysed.

---

## Stage 5 — Provider-agnostic AI and LangGraph case analysis

### D-024: One `LLMProvider` interface; provider/model swaps are environment-only

**Date:** Stage 5
**Decision:** Agent nodes depend only on `app.ai.base.LLMProvider` and call `generate_structured(StructuredRequest)`. Adapters exist for `gemini` (official Google Gen AI SDK), `openai`, `openai_compatible` (Groq/OpenRouter/Together/Ollama/LM Studio/Azure-compatible), `anthropic`, and `mock` (development fixture). Selection is by `AI_PROVIDER`, `AI_MODEL`, `AI_API_KEY`, and `AI_BASE_URL`.
**Rationale:** The user requirement is that changing the AI provider or model must require only a key/model change, not agent-code changes. Keeping vendor SDK imports inside adapters and Pydantic schemas inside the shared contract makes that true: the graph has no Gemini-specific code.
**Consequence:** Adding another vendor means writing one adapter class and registering it; prompts, verifier, graph, persistence, and API remain unchanged.

### D-025: Gemini uses the official Google Gen AI SDK; keys stay server-side

**Date:** Stage 5
**Decision:** The Gemini adapter imports `google.genai` and constructs `genai.Client(api_key=...)` only on the server. No key is ever returned by `/api/v1/ai/status`, written to workflow rows, or logged.
**Rationale:** Matches the project requirement and avoids a second-hand HTTP reimplementation of Gemini. Status exposes only provider, model, configured flag, and a safe message.
**Limitation:** No real Gemini key was available in this environment, so the adapter is covered by an injected fake SDK client and the OpenAI/Anthropic adapters by `httpx.MockTransport`. A live smoke test remains a deployment step.

### D-026: Structured output is validated before it reaches the graph

**Date:** Stage 5
**Decision:** Every model call returns a Pydantic-validated object (`CaseAnalysisDraft`). Invalid JSON gets a bounded repair attempt (`AI_STRUCTURED_RETRIES`, default 1). Transport failures get bounded retries (`AI_MAX_RETRIES`, default 2) for timeouts, 429s, and 5xx only. Auth/400 errors are not retried.
**Rationale:** Legal output cannot be parsed optimistically. Validation happens in the provider layer so every adapter behaves identically. Repair prompts contain only a generic instruction, never raw document text or vendor error details.
**Consequence:** `ProviderResponseError(code="invalid_model_output")` is a recoverable workflow failure the user can retry.

### D-027: Source markers (`S1`, `S2`, ...) instead of document UUIDs in prompts

**Date:** Stage 5
**Decision:** Source excerpts are numbered per run and the model must cite `source_id` markers plus a short quote. The verifier maps markers back to real `document_id`/`page_number` pairs before results are stored or shown.
**Rationale:** Models are unreliable at reproducing UUIDs. Markers remove a common hallucination path while preserving exact source traceability. The verifier also rejects invented markers and quotes that are not real substrings of the cited page.
**Consequence:** Every displayed source reference is derived from the server's own excerpt list, not from model-supplied identifiers.

### D-028: Deterministic verifier node (no second LLM)

**Date:** Stage 5
**Decision:** The verifier node performs no model call. It validates source IDs, checks quotes against normalised page text, classifies each claim as `supported`, `partially_supported`, or `unsupported`, counts invalid references, and flags citation-like strings. Unsupported/partial claims trigger at most `AGENT_MAX_VERIFIER_RETRIES` (default 1) analyst revision.
**Rationale:** A second model cannot reliably police the first. Deterministic checks are auditable, cheap, and testable. Unsupported claims are surfaced rather than silently deleted.
**Consequence:** The UI shows the verification counts and the exact page for every cited claim. The result explicitly states that no external authority database was consulted.

### D-029: `workflow_runs` table + in-process background runner (no Celery/Redis yet)

**Date:** Stage 5
**Decision:** A new `workflow_runs` table (migration `003`) stores status, progress, steps, provider metadata, input, token usage, sanitised error, and the verified result. `POST /api/v1/cases/{id}/analysis` creates a queued row and schedules a bounded runner via FastAPI `BackgroundTasks`. Clients poll `GET .../analysis/{workflow_id}`. On startup, interrupted `queued`/`running` rows are marked failed with `interrupted_by_restart` and can be retried.
**Rationale:** Keeps Stage 5 deployable on the existing single Render web service. Workflows are bounded by `AGENT_EXECUTION_TIMEOUT_S` (120 s), call budgets, token budgets, and attempt limits. Persisting state means a completed result survives a restart and failures are recoverable.
**Limitation:** The runner is not a durable queue: a process crash loses the in-flight task (the row is recovered as failed on next startup). LangGraph uses an in-process `MemorySaver`; true cross-restart graph resume is deferred. Move to Celery/Redis or a managed queue when concurrent analysis volume or long OCR jobs require it.
**Alternatives considered:** Celery + Redis now (infrastructure cost/complexity before demonstrated need), synchronous request execution (timeouts and poor UX), Vercel functions (timeout limits).

### D-030: Development fixture mode is explicit and can be disabled

**Date:** Stage 5
**Decision:** When no provider key is configured outside production, the API uses a deterministic `MockProvider` that returns source-linked fixture content. Every result carries `is_mock: true`, the UI shows a "Development fixture — no AI model was called" badge, and limitations say so. In production the fixture is disabled unless `AI_ALLOW_MOCK=true` is set deliberately.
**Rationale:** Local development and automated tests must exercise the real graph, verifier, persistence, and UI without credentials, but fixture output must never be mistaken for legal analysis.
**Consequence:** A missing key is visible and honest rather than a silent failure or fabricated "AI" output.

### D-031: Prompt-injection defence treats all document text as untrusted evidence

**Date:** Stage 5
**Decision:** Source text is wrapped in `<untrusted_document>` tags, control characters are removed, and any structural wrapper tags inside the text are escaped. The system prompt states that document text is evidence, never instructions, and that any embedded instruction must be ignored and noted as a limitation. The model is forbidden from citing external statutes/cases in Stage 5 because no authority corpus is available.
**Rationale:** Uploaded PDFs/DOCX/TXT are attacker-controlled in a multi-user product. This is defence-in-depth: prompts cannot fully prevent injection, so the verifier and deterministic source checks also constrain what can appear as a supported claim.
**Limitation:** Prompt injection is mitigated, not solved. Stage 6 retrieval and authority handling need the same treatment plus provenance checks.

### D-032: Pinned LangGraph/langsmith stack and Python 3.13

**Date:** Stage 5
**Decision:** Pin `langgraph==0.6.11`, `langchain-core==0.3.79`, `langsmith==0.3.45`, and `google-genai>=1.0,<2.0`; run the backend on Python 3.13.17 in this environment.
**Rationale:** Python 3.15 had no compatible wheels for parts of the graph stack (`zstandard` tried a source build with no MSVC), and a newer langsmith/xxhash combination was blocked by the local Windows Application Control policy. The pinned set imports and runs cleanly; 127 backend tests pass.
**Consequence:** Do not bump these pins casually. Re-run the full backend suite and a live provider smoke test before changing them.

### D-033: `apps/api/.env` is resolved relative to the package; tests never read it

**Date:** Stage 5 follow-up
**Decision:** `Settings` loads `Path(__file__).parent.parent / ".env"` (that is, `apps/api/.env`) instead of a CWD-relative `.env`. The test suite forces `AI_PROVIDER=mock` before importing app modules so a developer's real key cannot change test behaviour.
**Rationale:** A relative `.env` silently fails when uvicorn is started from the repository root, which makes a configured provider look like it is still using the fixture. Tests must be hermetic and must never make network calls or depend on local credentials.
**Consequence:** `.env` changes require an API restart; `uvicorn --reload` watches Python files, not `.env`. Gemini's native response schema stays enabled by default because disabling it produced non-JSON output in a live smoke test.

### D-034: Gemini model IDs are configuration, not code

**Date:** Stage 5 follow-up
**Decision:** The default Gemini model is `gemini-3.1-flash-lite`. `provider_model_unavailable` is a distinct non-retryable error code.
**Rationale:** Google retires model IDs for new users (for example `gemini-2.5-flash` returned 404 in a live check). Operators must be able to change `AI_MODEL` without a code change, and the UI/API must say clearly when the configured model is unavailable rather than reporting a generic provider failure.

### D-035: Gemini receives a constraint-free JSON schema

**Date:** Stage 5 follow-up
**Decision:** The Gemini adapter converts the agent's Pydantic output model to a JSON schema, inlines `$defs`/`$ref`, and removes validation-only keywords (`minLength`, `maxLength`, `minItems`, `maxItems`, `minimum`, `maximum`, `pattern`, `format`, `additionalProperties`, and similar) before sending it as `response_schema`. The full Pydantic model still validates the returned JSON locally.
**Rationale:** A live run with the real `CaseAnalysisDraft` schema returned `400 INVALID_ARGUMENT` because Gemini rejects schemas with too many constraint states. A minimal schema probe passed; the stripped schema passed and the full workflow completed with 8/8 claims supported.
**Consequence:** Agents keep one schema and no provider-specific code. The model may occasionally return more list items than the local maximum; structured retries and the verifier handle that, and the local schema remains authoritative.

### D-036: Stage 6 splits model work into two specialist nodes

**Date:** Stage 6
**Decision:** Case Intelligence uses two model calls instead of one monolith: a **Case Analyst** (facts, entities, parties, dates, procedural history, amounts) and an **Evidence Analyst** (legal issues, evidence questions, uncertainties, inferences). A deterministic **chronology builder** merges dated items between them. The verifier can route one bounded revision back to whichever specialist produced unsupported content (`revision_target`).
**Rationale:** One prompt doing extraction and legal issue-spotting produced shallow issue analysis and made verification feedback ambiguous. Splitting keeps each prompt's contract small, makes the JSON schemas easier for the model to satisfy, and lets retries target only the failing half of the draft.
**Consequence:** The default `AGENT_MAX_LLM_CALLS` rises from 3 to 5 (two drafts + up to one revision + headroom). Graphs without a configured provider still return `insufficient_sources` before any call.

### D-037: Chronology is built deterministically, not by the model

**Date:** Stage 6
**Decision:** `app/agents/nodes/chronology_builder.py` orders dated items using `app/agents/tools/dates.py`. Dates are normalised to ISO sort keys with a recorded precision (`day`/`month`/`year`) and an `ambiguous` flag. Numeric day/month order defaults to day-first but is explicitly flagged and annotated rather than silently guessed. Undated items are retained and marked as undated.
**Rationale:** Timeline ordering is deterministic logic, so asking an LLM to sort dates adds cost and hallucination risk. Ambiguous dates (for example `05/06/2024`) must be visible to a lawyer, not resolved by assumption.
**Consequence:** The chronology contains only dates present in the source drafts; it never invents an event or a date. Ambiguity notes surface in the UI and the report.

### D-038: Source planning is fair, de-duplicated, and budget-bounded

**Date:** Stage 6
**Decision:** `load_case_sources` selects pages **round-robin across documents** so a long first file cannot starve the rest of the case. Identical page text is suppressed and counted (`duplicate_pages_skipped`). Pages below `AGENT_MIN_SOURCE_CHARS` (default 40, lowered from 120) are still analysed but flagged `short`; pages with no usable text are skipped. Per-document extraction completeness, failed extraction, OCR requirement, and instruction-like text are recorded in `SourceStats`/notes.
**Rationale:** Sending duplicate text wastes tokens and can make the model over-weight repeated facts. Round-robin selection improves recall across a multi-document case. Lowering the short-page threshold admits genuinely useful short pages (for example a one-line order) while still flagging them.
**Consequence:** Source selection is deterministic and testable (`tests/test_source_planner.py`). The result records exactly what was analysed, skipped, or truncated.

### D-039: Verification is deterministic and records support categories plus spans

**Date:** Stage 6
**Decision:** The verifier normalises whitespace/case and searches the analysed excerpt for each claimed quote. Each item becomes `supported`, `partially_supported` (source cited but quote not found), or `unsupported`. When a quote is found, character offsets relative to the analysed excerpt are stored so the UI can highlight it. `VerificationSummary` counts each category. At most one revision is requested by default (`AGENT_MAX_VERIFIER_RETRIES=1`).
**Rationale:** A second LLM verifying the first is neither reproducible nor auditable. Deterministic substring checks are testable, cheap, and honest: if a quote cannot be located, the product says so instead of implying verification.
**Limitation:** Offsets are relative to the analysed excerpt/page prefix, not the full original file. The UI highlights only when `quote_verified` is true and the offsets are valid.

### D-040: Report export is a self-contained HTML print view plus Markdown, from persisted results only

**Date:** Stage 6
**Decision:** `GET /api/v1/cases/{case_id}/analysis/{workflow_id}/report?format=html|markdown` renders the **persisted verified result**. HTML is escaped, self-contained, print-ready (browser "Print / Save as PDF"), and served with `CSP: default-src 'none'; style-src 'unsafe-inline'; img-src data:`. Markdown is served as `text/markdown`. No model is called during export and no new facts are introduced.
**Rationale:** A PDF dependency adds weight and a new failure mode for a feature whose main need is a shareable, printable record. Rendering only the stored result keeps the export auditable and identical to what was reviewed on screen.
**Consequence:** The frontend offers "Print / save PDF", "HTML report", and "Markdown"; all download real bytes from the API. Server-side PDF generation can be added later without changing the data contract.

### D-041: Workflow, prompt, and result-schema versions are persisted

**Date:** Stage 6
**Decision:** Migration `004` adds `workflow_version`, `prompt_version`, and `result_schema_version` to `workflow_runs`; the same values are embedded in `CaseAnalysisResult`. Constants live in `app/agents/schemas.py` (`6.1.0`, `2026-11-case-intelligence-v2`, `6.1`).
**Rationale:** A stored report must remain explainable after prompts or graph topology change. Persisting versions makes "which logic produced this report?" answerable without git archaeology.
**Consequence:** Bump the constants whenever a prompt or result contract changes in a way that affects interpretation. The Stage 6 follow-up party-contract change bumped all three (D-043).

### D-042: Stage 6 is wired in isolation; future-stage scaffolding stays unwired

**Date:** Stage 6
**Decision:** Only the Case Intelligence workflow is dispatched from `app/services/analysis.py`. Untracked future-stage files (`graphs_extended.py`, `schemas_extended.py`, contradiction/advocate/judge/precedent nodes and prompts) are **not imported**. Unknown workflow types fail with a clear `unsupported_workflow` error rather than falling through to a broken graph.
**Rationale:** The future-stage files are incomplete (for example a missing `wrap_untrusted` helper) and importing them prevented application startup. Stage 6 scope explicitly excludes those modules.
**Consequence:** The app starts cleanly and the Stage 6 test suite is deterministic. Those files remain user-owned and untouched for a later stage; they must be completed and explicitly wired before use.

### D-043: Parties are verified source-linked records, not bare strings

**Date:** Stage 6 follow-up
**Decision:** `CaseAnalysisDraft.parties` and `CaseAnalysisResult.parties` are lists of structured party records (`DraftParty` / `VerifiedParty`) with `name`, optional `role` (for example Petitioner or Respondent), `source_refs`/`sources`, `support`, and `confidence`. The deterministic verifier checks each party reference exactly like facts and entities and records a `parties` verification category. The Case Analyst prompt requires a source marker and, where possible, a verbatim quote for every party. The result contract version moves to `6.1`, prompt to `2026-11-case-intelligence-v2`, and workflow to `6.1.0`.
**Rationale:** Bare party names could not be traced to a document page, so they were the only extracted collection without a verifiable provenance. A lawyer must be able to open the page that names each party and see whether the quote was located.
**Consequence:** API/shared consumers now read `party.name` instead of a string. Party records render with support badges and source chips in the workspace and report. The verifier routes a party-provenance failure back to the Case Analyst during the bounded revision.

### D-044: Live Gemini verification is reported separately from deterministic verification

**Date:** Stage 6 follow-up
**Decision:** Stage 6 completion is evidenced by the deterministic suite, migration round-trip, frontend checks, and a mock-provider HTTP smoke test. A real-provider run is reported as a separate, explicitly labelled result. If the provider returns `503 UNAVAILABLE` or the local key is absent, the handoff must say so and must not describe live analysis as verified.
**Rationale:** The live attempt reached the configured Gemini endpoint but failed before any model output (`provider_unavailable`, `llm_calls=0`). Gemini returned `503` "model is currently experiencing high demand" for the full analyst request across several model IDs, and later the local `AI_API_KEY` was no longer present in `apps/api/.env`. Mock success is not evidence that a real provider call works.
**Consequence:** The product remains fully testable without a key, but first deployment must repeat the live smoke test in `docs/stage-handoffs/stage-6.md` §5 and record the actual provider/model result.
