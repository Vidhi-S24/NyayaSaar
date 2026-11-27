# NyayaSaar — Architecture

> Last updated: Stage 6 — Case Intelligence module (document-grounded multi-agent analysis)

---

## System overview

NyayaSaar is a multi-agent legal case intelligence platform with a clear separation between the frontend (Vercel), the backend API + AI orchestration layer (Render), and data services.

```
┌────────────────────────────────────────────────────────────────┐
│  User (browser)                                                │
└──────────────────────────────┬─────────────────────────────────┘
                               │ HTTPS
                               ▼
┌────────────────────────────────────────────────────────────────┐
│  Vercel (CDN + SSR)                                            │
│  apps/web — Next.js 15 App Router                              │
│                                                                │
│  • React Server Components for data fetching                   │
│  • Client components for interactive UI                        │
│  • NEXT_PUBLIC_API_BASE_URL → Render API                       │
│  • No secrets in client bundle                                 │
│  • No long-running document processing (→ Render API)          │
└──────────────────────────────┬─────────────────────────────────┘
                               │ HTTPS (REST /api/v1)
                               ▼
┌────────────────────────────────────────────────────────────────┐
│  Render (Web Service)                                          │
│  apps/api — FastAPI + LangGraph                                │
│                                                                │
│  ┌─────────────────┐   ┌─────────────────────────────────┐   │
│  │  FastAPI routes │   │  LangGraph case-intelligence     │   │
│  │  /api/v1/*      │──▶│  orchestrator → case_analyst →   │   │
│  │  Pydantic I/O   │   │  evidence_analyst → chronology → │   │
│  │  Auth (Stage 3) │   │  verifier → finalize             │   │
│  └─────────────────┘   └──────────────┬──────────────────┘   │
│                                       │                      │
│  Background (Stage 5)                 │ LLMProvider interface│
│  in-process workflow runner           ▼                      │
│  (Celery/Redis deferred — D-029)  ┌──────────────────────┐   │
│                                   │ Gemini | OpenAI |    │   │
│                                   │ Anthropic | compat. | │   │
│                                   │ mock (fixture)       │   │
│                                   └──────────────────────┘   │
└──────────────────────────┬───────────────────────────────────┘
                           │             │
          ┌────────────────┘             └──────────────────┐
          │                                                 │
          ▼                                                 ▼
┌─────────────────────┐                      ┌─────────────────────────┐
│  PostgreSQL          │                      │  AI provider (server)    │
│  + pgvector          │                      │  Gemini (default) |      │
│  SQLAlchemy/Alembic  │                      │  OpenAI | Anthropic |    │
│  Hybrid retrieval    │                      │  OpenAI-compatible |     │
│  Full-text search    │                      │  labelled fixture        │
└─────────────────────┘                      └─────────────────────────┘
          │
          ├── Neo4j (optional)
          │   Citation graph features
          │   Core product works without it
          │
          └── Redis (optional)
              Background job queue
              Required only for long-running tasks
```

---

## Data flow

### Document upload and analysis

```
Browser
  → POST /api/v1/documents (multipart, file + metadata)
  → FastAPI validates: type, size, filename sanitisation
  → Storage layer saves file (local dev / S3 in prod)
  → Background task queued (Stage 5+): document parsing
  → LangGraph workflow: extract text → chunk → embed → store (pgvector)
  → Return document ID + processing status
  → Frontend polls /api/v1/documents/{id}/status
```

### Legal analysis workflow (Stage 6 Case Intelligence)

```
Browser
  → POST /api/v1/cases/{case_id}/analysis   {document_ids?, focus?}
  → FastAPI verifies case ownership, creates a queued workflow_runs row
  → returns 202 + workflow_id (no long synchronous request)
  → FastAPI BackgroundTasks invokes the bounded runner
      → load ready DocumentChunk pages (round-robin, de-duplicated, char budget)
      → LangGraph:
          orchestrator ──(no usable sources)──────────────→ finalize
               │
               ├→ case_analyst   (facts/parties/entities/dates/procedure/amounts)
               │       │
               │       └→ evidence_analyst (issues/questions/uncertainty)
               │               │
               │               └→ chronology_builder (deterministic, no model)
               │                       │
               │                       └→ verifier (deterministic, no model)
               │                              ├─ unsupported/partial + budget → case_analyst
               │                              │                                  or evidence_analyst
               │                              └─ verified / budget exhausted ──→ finalize
      → verified result + versions + steps + token usage saved to workflow_runs
  → Frontend polls GET /api/v1/cases/{case_id}/analysis/{workflow_id}
  → Result includes document_id + page_number (+ span) for every source reference
  → Failed runs can be re-queued with POST .../analysis/{workflow_id}/retry
  → GET .../analysis/{workflow_id}/report?format=html|markdown exports the
    persisted verified result (no model call)
```

---

## Stage 6 — Case Intelligence module

Stage 6 extends the Stage 5 graph in place rather than replacing it. It adds a
second specialist model call, deterministic chronology assembly, richer source
planning, source-span verification, persisted version metadata, report export,
and a full Case Intelligence workspace.

### Graph topology (`apps/api/app/agents/graph.py`)

```
START → orchestrator
orchestrator ─┬─(insufficient sources)──────────────→ finalize
              └─→ case_analyst
case_analyst ─┬─(error/budget)──────────────────────→ finalize
              └─→ evidence_analyst
evidence_analyst ─┬─(error/budget)──────────────────→ finalize
                  └─→ chronology_builder
chronology_builder → verifier
verifier ─┬─(revision needed, target=case_analyst)────→ case_analyst
          ├─(revision needed, target=evidence_analyst)→ evidence_analyst
          └─(verified or budget exhausted)───────────→ finalize
finalize → END
```

| Node | Model call | Responsibility |
|---|---|---|
| `orchestrator` | no | Source planning, budget init, honest insufficient-source exit |
| `case_analyst` | yes | Facts, parties/entities, dates, procedural events, amounts |
| `evidence_analyst` | yes | Legal issues, evidence questions, uncertainties, inferences |
| `chronology_builder` | no | Deterministic date normalisation, ordering, ambiguity flags |
| `verifier` | no | Quote/span verification, support classification, revision request |
| `finalize` | no | Verified result assembly, version stamping, sanitised failure |

### Typed state (`apps/api/app/agents/state.py`)

```
CaseAnalysisState (TypedDict, JSON-serialisable)
  identity: workflow_id, case_id, started_at
  inputs:   case_context, sources[], source_notes[], source_stats
  provider: provider_name, model_name, is_mock
  drafts:   extraction_draft, evidence_draft, draft, chronology[]
  outputs:  result
  control:  status, current_step, progress, outcome, errors, notes
  revision: retry_count, needs_revision, revision_target, verification_feedback
  budgets:  llm_calls, token_usage, token_budget_exhausted
```

### Source planning (`apps/api/app/agents/tools/sources.py`)

- Round-robin page selection across documents so one long file cannot starve a case.
- Duplicate page suppression (`duplicate_pages_skipped`).
- `AGENT_MIN_SOURCE_CHARS` (default 40): shorter pages are analysed but flagged.
- Per-document stats: failed extraction, incomplete extraction, OCR required,
  instruction-like text, truncated/omitted content.

### Verification and citations

`verifier.py` normalises whitespace/case and searches each claimed quote in the
analysed excerpt. Support is `supported`, `partially_supported` (source cited,
quote not located), or `unsupported`. Verified quotes carry character offsets
relative to the analysed excerpt so the UI can highlight them. At most one
revision is requested by default (`AGENT_MAX_VERIFIER_RETRIES=1`) and is routed
back to the specialist that produced the unsupported content.

Parties are verified records (`VerifiedParty`) with a name, optional procedural
role, source references, support status, and confidence. They are checked by the
same deterministic reference verifier as facts and entities, so a party name
cannot appear in the result without a resolvable document/page reference (D-043).

Citations always resolve to a real `document_id` and `page_number` from the
loaded source manifest. The UI never shows a page the verifier did not resolve.

### Workflow data model (Alembic migration `004`)

Migration `003` added `workflow_runs`; migration `004` adds:

```
workflow_runs
────────────────────────────────────────────
workflow_version      e.g. 6.1.0
prompt_version        e.g. 2026-11-case-intelligence-v2
result_schema_version e.g. 6.1
```

The same values are embedded in `CaseAnalysisResult`, so a stored report remains
auditable after prompts or topology change.

### API surface (all authenticated, case-ownership enforced)

```
POST /api/v1/cases/{case_id}/analysis                     → 202 queued run
GET  /api/v1/cases/{case_id}/analysis                     → recent runs
GET  /api/v1/cases/{case_id}/analysis/{workflow_id}       → status/result
POST /api/v1/cases/{case_id}/analysis/{workflow_id}/retry → 202 re-queued
GET  /api/v1/cases/{case_id}/analysis/{workflow_id}/report?format=html|markdown
                                                          → persisted report
GET  /api/v1/ai/status                                    → safe provider metadata
```

Report responses:

- `format=html` — self-contained, escaped, print-ready document; served with
  `CSP: default-src 'none'; style-src 'unsafe-inline'; img-src data:`.
- `format=markdown` — `text/markdown` durable text export.

Neither format calls a model; both render only the persisted verified result.

### Frontend

`components/analysis/analysis-panel.tsx` is the Case Intelligence workspace:

- Configuration: document selector (ready documents), optional analyst focus.
- Live progress: queued/running steps polled from the API; no simulated progress.
- Verification panel: supported / partial / unsupported counts and rate.
- Executive summary, parties/entities, amounts, source facts, procedural history,
  chronology (with ambiguity flags), legal issues, evidence questions,
  uncertainties, and model inferences — visually separated.
- Source dialog: opens the real document page and highlights a verified quote
  span when available; otherwise states the quote was not located.
- Export: "Print / save PDF" (opens the self-contained HTML), HTML download,
  and Markdown download.
- Rerun and failure recovery use the real retry endpoint.

`app/(app)/intelligence/intelligence-client.tsx` is the module entry point.

### Security and honesty controls

- API keys remain server-side only; versions and safe provider metadata are stored.
- All document text is untrusted evidence; instruction-like text is flagged.
- No external authorities are retrieved or invented; Stage 6 stays document-grounded.
- Unsupported or unverified statements are labelled, never presented as verified.
- Report HTML is escaped and locked down with CSP; Markdown is plain text.

### Deferred beyond Stage 6 Case Intelligence

- Hybrid retrieval (full-text + embeddings), contradiction/gap detection.
- Precedent Explorer, authority corpus, provenance checks, precedent graphs.
- Advocate Mode and Judge/Clerk Mode.
- Durable queue/worker and cross-restart LangGraph checkpoint resume.
- Server-side PDF generation (HTML print view is provided instead).
- Real-provider smoke tests in CI (requires a key and network access).

---

## Stage 5 — Provider-agnostic AI and LangGraph case analysis

> **Historical:** this section describes the Stage 5 single-analyst graph. Stage 6
> (above) supersedes its topology, state, and API surface while keeping the same
> provider layer and `workflow_runs` persistence.

### Provider layer (`apps/api/app/ai/`)

```
LLMProvider (ABC)
  ├── GeminiProvider            official google-genai SDK
  ├── OpenAICompatibleProvider  POST {AI_BASE_URL}/chat/completions
  │                             (OpenAI, Groq, OpenRouter, Together,
  │                              DeepSeek, Ollama, LM Studio, gateways)
  ├── AnthropicProvider         POST {base}/v1/messages
  └── MockProvider              labelled development fixture (no network)

get_provider(settings) selects the adapter from AI_PROVIDER / AI_MODEL /
AI_API_KEY / AI_BASE_URL. Agent nodes import only LLMProvider.
```

`generate_structured()` owns the reliability policy: per-request timeout,
bounded transport retries (timeouts/429/5xx), bounded structured-output repair,
Pydantic validation, token accounting, and sanitised errors. Vendor exception
text is never surfaced or logged.

### Workflow data model (Alembic migration `003`)

```
workflow_runs
────────────────────────────────────────────
id (uuid str) PK
case_id → cases.id            user_id → users.id
workflow_type (case_analysis)
status: queued | running | completed | failed
progress (0–100), current_step
provider, model, is_mock      ← safe metadata, never the key
input_payload (JSON)          ← document_ids, focus
result (JSON)                 ← verified CaseAnalysisResult
steps (JSON)                  ← bounded progress history
token_usage (JSON)
error_code, error_message     ← sanitised, no prompts/document text
attempt_count, started_at, completed_at
created_at / updated_at
```

### Graph state and nodes (`apps/api/app/agents/`)

```
CaseAnalysisState (TypedDict, JSON-serialisable)
  identity: workflow_id, case_id, started_at
  inputs:   case_context, sources[], source_notes[]
  provider: provider_name, model_name, is_mock
  outputs:  draft, result
  control:  status, current_step, progress, outcome, errors, notes
  budgets:  retry_count, needs_revision, verification_feedback,
            llm_calls, token_usage, token_budget_exhausted
```

- **orchestrator** — no model call; routes to the analyst or returns an honest
  insufficient-source result.
- **case_analyst** — builds a prompt from sanitised source excerpts, calls the
  configured provider, validates `CaseAnalysisDraft`, enforces call/token budgets.
- **verifier** — no model call; resolves `S1` markers to real documents/pages,
  checks quotes, classifies support, counts invalid refs, flags authority-like
  strings, and requests at most one bounded revision.
- **finalize** — always produces a result or a sanitised failure; never leaves a
  run silently incomplete.

### API surface (all authenticated, case-ownership enforced)

```
POST /api/v1/cases/{case_id}/analysis                  → 202 queued run
GET  /api/v1/cases/{case_id}/analysis                  → recent runs
GET  /api/v1/cases/{case_id}/analysis/{workflow_id}    → status/result
POST /api/v1/cases/{case_id}/analysis/{workflow_id}/retry → 202 re-queued
GET  /api/v1/ai/status                                 → safe provider metadata
```

### Frontend

The case workspace adds an **Analysis** tab (`components/analysis/analysis-panel.tsx`)
that starts a run, polls progress, shows provider/fixture status, displays the
structured result grouped into facts, legal issues, timeline, inferences,
unverified hypotheses, missing information, limitations, and verification
notes, and opens the exact cited document page in a source viewer.

### Security and honesty controls

- API keys are server-side only and never returned by `/ai/status` or stored in
  `workflow_runs`.
- Document text is untrusted: wrapped in `<untrusted_document>`, structural tags
  escaped, and explicitly described as evidence rather than instructions.
- The Stage 5 analyst is forbidden from citing statutes/cases because no legal
  authority corpus is connected. Citation-like strings are flagged for review.
- Fixture output is labelled in the API (`is_mock`), the UI, and the limitations.
- Every claim carries a source support status; unsupported claims are surfaced.

### Deferred to later stages

- Durable queue/worker (Celery/Redis) and cross-restart LangGraph checkpoint resume.
- Hybrid retrieval, embeddings/pgvector search, authority corpus, contradictions,
  precedent analysis, advocate/judge modules.
- Real-provider smoke tests in CI (requires a key and network access).

---

## Stage 4 — Document ingestion pipeline

### Data model additions (Alembic migration `002`)

```
documents                          document_chunks
─────────────────────────          ──────────────────────────────
id (uuid str) PK                   id (uuid str) PK
case_id → cases.id                 document_id → documents.id
original_name (display only)       page_number (int)
storage_key (UUID-derived path)    chunk_index (int)
content_type                       content (text)
file_size_bytes                    char_count (int)
processing_status                  embedding (ARRAY Float / pgvector)
  pending | processing |           created_at
  completed | failed |
  ocr_required
page_count
processing_notes (failure info)
extracted_at
created_at / updated_at
```

### Storage abstraction

```
StorageProvider (ABC)
  ├── LocalStorageProvider  — dev; files at STORAGE_LOCAL_PATH
  └── S3StorageProvider     — prod stub; wires boto3 in Stage 7

Storage key: uploads/{case_id}/{uuid4}.{ext}
  — derived server-side only; user filename never touches the path
```

### Extraction pipeline

```
POST /api/v1/cases/{case_id}/documents (multipart)
  → validate_upload()   magic-byte check + extension + size limit
  → make_storage_key()  UUID-based path
  → storage.save()      write to local disk or S3
  → create_document()   persist Document row (status=processing)
  → process_document()  synchronous (see D-020)
      ├─ PDF  → PyMuPDF page-by-page → DocumentChunk per page
      │         if avg chars/page < 50 → status=ocr_required
      ├─ DOCX → python-docx paragraph extraction → single chunk
      └─ TXT  → UTF-8/Latin-1 fallback → single chunk
  → update Document (status=completed|failed|ocr_required)
  → return DocumentResponse
```

### Document processing states

```
pending → processing → completed
                    ↘ failed          (retry up to 3 times)
                    ↘ ocr_required    (scanned PDF; no auto-retry)
```

---

## Stage 3 — Data model and authentication

### Data model (PostgreSQL, Alembic migration `001`)

```
users                 cases                          case_memberships
─────────────         ─────────────────────          ────────────────────
id (uuid str) PK      id (uuid str) PK               id (uuid str) PK
email (unique)        owner_id → users.id            case_id → cases.id
hashed_password       title, case_number, court      user_id → users.id
full_name             jurisdiction                   role (owner|editor|viewer)
is_active, is_verified  status, priority             (unique: case_id+user_id)
role                  summary (text)
created_at/updated_at tags, issues (JSON)
                      documents_count
                      created_at/updated_at
```

- `cases.owner_id` is the authorization anchor: every case query is scoped to the authenticated user.
- `case_memberships` is provisioned for future sharing (Stage 3 authorization is owner-only; see D-016).
- Timestamps are `timestamptz` with `server_default=now()`; `updated_at` is maintained on update.
- JSON columns (`tags`, `issues`) are portable across SQLite (development) and PostgreSQL.

### Authentication flow

```
Sign in  POST /api/v1/auth/login  {email, password}
             → bcrypt verify → JWT (HS256, 30 min) → {access_token, expires_in}
Sign up  POST /api/v1/auth/register (same response; 409 on duplicate email)
Session  GET /api/v1/auth/me (Authorization: Bearer <token>) → user profile
Every protected route → get_current_user dependency → 401/403 on failure
```

- The frontend stores the token in `localStorage` (see D-013 for trade-offs) and injects it via the shared api-client; a global 401 handler signs the user out.
- Case authorization is enforced in the service layer (`app/services/cases.py`) by including `owner_id` in every SQL query — not in the frontend.
- Development fallback: with no `DATABASE_URL`, the API and seed script use a local SQLite file so the product runs without infrastructure.

---

## External data flows and privacy


| Provider | Data sent | Retention | Configurable? |
|---|---|---|---|
| Selected AI provider (Gemini default; OpenAI/Anthropic/compatible optional) | Bounded document excerpts, case metadata, focus | Per provider's data policies | `AI_PROVIDER`, `AI_MODEL`, `AI_BASE_URL`, key |
| PostgreSQL (Render) | All structured data, workflow runs/results | Persistent, managed by operator | DATABASE_URL |
| Neo4j (optional) | Citation relationships | Persistent | NEO4J_URI |
| Redis (optional, not used in Stage 5) | Job payloads (transient) | Ephemeral | REDIS_URL |
| LangSmith (optional) | LLM traces, if explicitly enabled | Per LangSmith policy | LANGSMITH_API_KEY |

**Privacy principles:**
- Raw legal documents are not logged in plaintext.
- Sensitive personal data is not logged unnecessarily.
- AI API keys are never exposed to the browser bundle, API responses, workflow rows, or logs.
- All AI outputs are explicitly marked as requiring professional verification.

---

## Module boundaries

| Package | Language | Deployment | Responsibility |
|---|---|---|---|
| `apps/web` | TypeScript / React | Vercel | UI, routing, client state |
| `apps/api` | Python / FastAPI | Render | API, auth, agent orchestration |
| `apps/worker` | Python / Celery | Render (separate service) | Long-running background jobs (staged) |
| `packages/shared` | TypeScript | N/A (compile-time only) | Shared types consumed by web |

---

## Agent architecture

LangGraph workflows are implemented as stateful graphs with:
- **Typed state** (TypedDict / Pydantic) for safe inter-node communication
- **Conditional routing** based on analysis outcomes
- **Bounded retries** with configurable limits
- **Execution timeouts** (`AGENT_EXECUTION_TIMEOUT_S`)
- **Workflow status tracking** in PostgreSQL
- **Human-review checkpoints** before consequential actions
- **Prompt injection defence**: documents treated as untrusted content

Legal source providers use an explicit interface (`LegalSourceProvider`). When no provider is configured, fixtures are used and clearly labelled as development data.

---

## Key decisions

See [decisions.md](decisions.md) for the rationale behind technology choices.

---

## Stage-by-stage build plan

| Stage | Scope | Key additions |
|---|---|---|
| 1 ✅ | Foundation | Monorepo, FastAPI skeleton, Next.js shell, docs |
| 2 ✅ | Premium UI | Full dashboard, case workspace, design system |
| 3 ✅ | Database + Auth | PostgreSQL, Alembic, JWT authentication, ownership authorisation, live case CRUD |
| 4 ✅ | Document ingestion | Upload, validation, extraction, chunking, storage abstraction, frontend UI |
| 5 ✅ | Agentic workflows | Provider-agnostic AI layer, LangGraph case analysis, deterministic verifier, persisted runs, analysis UI |
| 6 ✅ | Legal analysis | Case Intelligence module: dual-specialist graph, chronology, span verification, version metadata, report export |
| 7 ✅ | Hybrid retrieval | `pgvector` + FTS + RRF hybrid retrieval, `EmbeddingProvider`, `LegalCorpusProvider`, Legal Research UI |
| 8 ✅ | Contradiction & Gap Hunter | Cross-document contradiction workflow, deterministic verifier, `finding_reviews` audit trail, `/contradictions` workspace |
| 9 ✅ | Precedent Explorer & Conflict Detector | `citation_links` migration `007`, optional Neo4j + DB fallback, `precedent` LangGraph workflow, `/precedents` UI |
| 10+ | Future stages | Advocate Mode, Judge/Clerk Mode, evaluation & CI |

