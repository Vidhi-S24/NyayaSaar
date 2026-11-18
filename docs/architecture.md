# NyayaSaar — Architecture

> Last updated: Stage 4 — Document Ingestion Pipeline

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
│  │  FastAPI routes │   │  LangGraph workflows             │   │
│  │  /api/v1/*      │──▶│  (stateful agent orchestration) │   │
│  │  Pydantic I/O   │   │                                 │   │
│  │  Auth (Stage 3) │   │  Nodes (staged):                │   │
│  └─────────────────┘   │  • Case Analyst                 │   │
│                         │  • Evidence Analyst             │   │
│  Background (optional)  │  • Legal Research Agent         │   │
│  apps/worker (Stage 5+) │  • Precedent Analyst            │   │
│  Celery + Redis         │  • Argument Analyst             │   │
│                         │  • Verifier/Report Agent        │   │
│                         └──────────────┬────────────────┘   │
└──────────────────────────┬─────────────┼─────────────────────┘
                           │             │
          ┌────────────────┘             └──────────────────┐
          │                                                 │
          ▼                                                 ▼
┌─────────────────────┐                      ┌─────────────────────┐
│  PostgreSQL          │                      │  Google Gemini API   │
│  + pgvector          │                      │  (server-side key)   │
│  SQLAlchemy/Alembic  │                      │  Configurable model  │
│  Hybrid retrieval    │                      └─────────────────────┘
│  Full-text search    │
└─────────────────────┘
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

### Legal analysis workflow

```
Browser
  → POST /api/v1/analysis/run (case_id, workflow_type, parameters)
  → FastAPI creates WorkflowRun record, returns run_id
  → LangGraph workflow executes:
      [Case Analyst]
        ↓ typed state
      [Evidence Analyst]
        ↓
      [Legal Research Agent] → searches configured legal corpus
        ↓
      [Precedent Analyst]
        ↓
      [Verifier/Report Agent] → checks source citations
        ↓
      structured report saved to DB
  → Frontend polls /api/v1/analysis/{run_id}/status
  → GET /api/v1/analysis/{run_id}/report → source-linked findings
```

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
| Google Gemini API | Document chunks, legal queries | Per Google's data policies | Model ID + key configurable |
| PostgreSQL (Render) | All structured data | Persistent, managed by operator | DATABASE_URL |
| Neo4j (optional) | Citation relationships | Persistent | NEO4J_URI |
| Redis (optional) | Job payloads (transient) | Ephemeral | REDIS_URL |
| LangSmith (optional) | LLM traces | Per LangSmith policy | LANGSMITH_API_KEY |

**Privacy principles:**
- Raw legal documents are not logged in plaintext.
- Sensitive personal data is not logged unnecessarily.
- Gemini API key is never exposed to the browser bundle.
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
| 5 | Agentic workflows | LangGraph nodes, Gemini integration, embedding, hybrid retrieval |
| 6 | Legal analysis | All five intelligence modules, retrieval |
| 7 | Evaluation + deploy | LangSmith, RAGAS, Render/Vercel config, CI |

