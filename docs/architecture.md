# NyayaSaar — Architecture

> Last updated: Stage 5 — Provider-agnostic AI and LangGraph case analysis

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
│  │  FastAPI routes │   │  LangGraph case-analysis graph   │   │
│  │  /api/v1/*      │──▶│  orchestrator → analyst →        │   │
│  │  Pydantic I/O   │   │  deterministic verifier → final  │   │
│  │  Auth (Stage 3) │   │  (bounded retries/timeouts)      │   │
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

### Legal analysis workflow (Stage 5)

```
Browser
  → POST /api/v1/cases/{case_id}/analysis   {document_ids?, focus?}
  → FastAPI verifies case ownership, creates a queued workflow_runs row
  → returns 202 + workflow_id (no long synchronous request)
  → FastAPI BackgroundTasks invokes the bounded runner
      → load ready DocumentChunk pages (bounded character budget)
      → LangGraph:
          orchestrator ──(no usable sources)──────────────→ finalize
               │
               └→ case_analyst (LLMProvider, structured JSON)
                       │
                       └→ verifier (deterministic, no model call)
                              ├─ unsupported/partial + budget left → case_analyst
                              └─ verified / budget exhausted → finalize
      → verified result + steps + token usage saved to workflow_runs
  → Frontend polls GET /api/v1/cases/{case_id}/analysis/{workflow_id}
  → Result includes document_id + page_number for every source reference
  → Failed runs can be re-queued with POST .../analysis/{workflow_id}/retry
```

---

## Stage 5 — Provider-agnostic AI and LangGraph case analysis

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
| 6 | Legal analysis | Full case intelligence, hybrid retrieval, contradictions, precedents, advocate/judge modules |
| 7 | Evaluation + deploy | LangSmith, RAGAS, Render/Vercel config, CI |

