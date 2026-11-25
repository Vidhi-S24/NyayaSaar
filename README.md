# NyayaSaar — Legal Case Intelligence Platform

**NyayaSaar** is a production-minded, multi-agent legal case intelligence and precedent reasoning platform built with Next.js, FastAPI, LangGraph, and Google Gemini.

> ⚖️ NyayaSaar is a legal *research assistant*, not an autonomous lawyer or judge. It never fabricates legal authorities, citations, statutes, holdings, or claims of precedential status. All outputs require professional legal verification.

---

## Overview

NyayaSaar provides five core intelligence modules:

| Module | Description |
|---|---|
| **Case Intelligence** | Upload documents, extract facts and legal issues, find authorities, generate source-linked analysis |
| **Contradiction & Gap Hunter** | Build timelines, detect conflicts, identify missing evidence, flag unsupported assertions |
| **Precedent Explorer** | Search authorities, explore citation relationships, analyse conflicting reasoning |
| **Advocate Mode** | Develop opposing arguments, identify supporting/opposing authorities, expose evidentiary gaps |
| **Judge/Clerk Mode** | Audit issue coverage, reasoning consistency, source support, citations, unresolved questions |

---

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15 (App Router), React, TypeScript, Tailwind CSS, shadcn/ui |
| Backend | Python, FastAPI, Pydantic, versioned REST API (`/api/v1`) |
| Agentic AI | Provider-agnostic layer: Google Gemini (official SDK, default), OpenAI, OpenAI-compatible (Groq/OpenRouter/Ollama/etc.), Anthropic; LangGraph |
| Database | PostgreSQL + pgvector, SQLAlchemy, Alembic |
| Graph (optional) | Neo4j for citation graph |
| Background Jobs | In-process bounded workflow runner (Stage 5); Redis + Celery when needed |
| Documents | PyMuPDF, python-docx, OCR extension point |
| Storage | Local dev + provider abstraction |

---

## Monorepo Structure

```
nyayasaar/
├── apps/
│   ├── web/          # Next.js frontend → Vercel
│   └── api/          # FastAPI + LangGraph → Render
├── packages/
│   └── shared/       # Shared TypeScript types/config
├── docs/
│   ├── architecture.md
│   ├── implementation-status.md
│   ├── decisions.md
│   ├── deployment.md
│   └── stage-handoffs/
├── scripts/
├── .env.example
├── .gitignore
├── package.json
├── pnpm-workspace.yaml
└── README.md
```

---

## Quick Start

### Prerequisites

- Node.js ≥ 20
- pnpm ≥ 9
- Python 3.13 (required for the pinned LangGraph stack)
- PostgreSQL (optional for local development; SQLite fallback is available)

### 1. Install dependencies

```bash
# Install pnpm if not present
npm install -g pnpm

# Install all workspace dependencies
pnpm install
```

### 2. Environment setup

```bash
# Backend: the API loads apps/api/.env (regardless of the directory you run from)
cp .env.example apps/api/.env
# Edit apps/api/.env with your configuration.
#
# Frontend: create apps/web/.env.local with:
#   NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
#
# For real AI analysis set AI_PROVIDER, AI_MODEL, and AI_API_KEY.
# With no key outside production, the API uses a clearly-labelled fixture;
# it never claims a model was called. See docs/stage-handoffs/stage-5.md.
```

### 3. Start the frontend

```bash
pnpm dev:web
# → http://localhost:3000
```

### 4. Start the API

```bash
cd apps/api
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# → http://localhost:8000
# → Health: http://localhost:8000/api/v1/health
# → Docs: http://localhost:8000/docs
```

---

## Development Commands

From the monorepo root:

| Command | Description |
|---|---|
| `pnpm dev:web` | Start Next.js frontend in dev mode |
| `pnpm build:web` | Build the frontend |
| `pnpm type-check` | Run TypeScript type checking |
| `pnpm lint` | Run ESLint |
| `pnpm test` | Run frontend tests (Vitest) |
| `pnpm test:api` | Instructions for running Python tests |

From `apps/api/` (with the venv active):

| Command | Description |
|---|---|
| `python -m pytest tests/ --ignore=tests/test_gemini_connection.py` | Run deterministic backend tests (163 passing as of Stage 6) |
| `alembic upgrade head` | Apply database migrations (needs `DATABASE_SYNC_URL`) |
| `python -m scripts.seed_demo` | Seed a demo user + labelled [DEMO] sample cases (idempotent) |
| `uvicorn app.main:app --reload --port 8000` | Start the API |

---

## Documentation

- [Architecture](docs/architecture.md)
- [Implementation Status](docs/implementation-status.md)
- [Design Decisions](docs/decisions.md)
- [Deployment Guide](docs/deployment.md)
- [Stage Handoffs](docs/stage-handoffs/)

---

## Implementation Stages

| Stage | Description | Status |
|---|---|---|
| 1 | Repository audit and foundation | ✅ Complete |
| 2 | Premium frontend and application experience | ✅ Complete |
| 3 | Database, authentication, and user management | ✅ Complete |
| 4 | Document ingestion pipeline | ✅ Complete |
| 5 | Provider-agnostic AI + LangGraph case analysis | ✅ Complete |
| 6 | Case Intelligence module (source-grounded workflow, chronology, verifier, export) | ✅ Complete |
| 7 | Hybrid legal retrieval, pgvector, legal-source providers, and Legal Research UI | ✅ Complete |
| 8 | Contradiction & Gap Hunter (cross-document workflow, verifier, review audit trail, `/contradictions` UI) | ✅ Complete |
| 9+ | Precedent Explorer, Advocate & Judge/Clerk modes, evaluation, and deployment | ⏳ Pending |

---

## Important Disclaimers

- NyayaSaar is a research tool and does not constitute legal advice.
- All AI-generated analysis must be independently verified by qualified legal professionals.
- The platform never automatically files, submits, or executes legal actions.
- Legal authorities are sourced from configured providers only; the platform clearly indicates when no corpus is available.

