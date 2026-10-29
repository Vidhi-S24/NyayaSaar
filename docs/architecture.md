# NyayaSaar — Architecture

> Last updated: Stage 1 — Foundation

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
| 2 | Premium UI | Full dashboard, case workspace, design system |
| 3 | Database + Auth | PostgreSQL, Alembic, authentication, authorisation |
| 4 | Document ingestion | Upload, parsing, chunking, embedding, storage |
| 5 | Agentic workflows | LangGraph nodes, Gemini integration, tools |
| 6 | Legal analysis | All five intelligence modules, retrieval |
| 7 | Evaluation + deploy | LangSmith, RAGAS, Render/Vercel config, CI |
