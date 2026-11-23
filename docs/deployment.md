# NyayaSaar — Deployment Guide

> Last updated: Stage 5 — Provider-agnostic AI and LangGraph case analysis

---

## Overview

| Service | Platform | URL pattern |
|---|---|---|
| Frontend (`apps/web`) | Vercel | `https://nyayasaar.vercel.app` |
| API (`apps/api`) | Render Web Service | `https://nyayasaar-api.onrender.com` |
| Worker (`apps/worker`) | Render Worker (future) | N/A |
| PostgreSQL | Render Managed PostgreSQL | Internal URL |
| Redis | Render Redis (future) | Internal URL |

---

## Local development

### Prerequisites

- Node.js ≥ 20
- pnpm ≥ 9 (`npm install -g pnpm`)
- Python 3.13 (required for the pinned LangGraph stack in this project)
- PostgreSQL (optional for local development — see below)

### Database options for local development

| Option | Setup |
|---|---|
| **SQLite (zero setup)** | Leave `DATABASE_URL` unset. The API and seed script fall back to `sqlite+aiosqlite:///nyayasaar-dev.db` style local files. Fine for demos; not for production or concurrent use. |
| **PostgreSQL (recommended)** | Install PostgreSQL locally (or run it in Docker: `docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=password -e POSTGRES_USER=nyayasaar -e POSTGRES_DB=nyayasaar_dev postgres:16`), then set `DATABASE_URL` and `DATABASE_SYNC_URL` in `apps/api/.env`. |

### Steps

```bash
# 1. Clone the repo
git clone <repo-url>
cd nyayasaar

# 2. Copy env file
# The API loads apps/api/.env; the frontend uses apps/web/.env.local.
cp .env.example apps/api/.env
# Edit apps/api/.env — for PostgreSQL set DATABASE_URL / DATABASE_SYNC_URL.
# Create apps/web/.env.local with:
#   NEXT_PUBLIC_API_BASE_URL=http://localhost:8000

# 3. Install JS dependencies
pnpm install

# 4. Start the frontend
pnpm dev:web
# → http://localhost:3000

# 5. In a second terminal: set up and start the API
cd apps/api
python -m venv .venv

# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
# → http://localhost:8000/api/v1/health
# → http://localhost:8000/docs
```

### Database migrations and demo data

```bash
cd apps/api

# Create the schema from a clean database (Alembic reads DATABASE_SYNC_URL):
export DATABASE_SYNC_URL=postgresql+psycopg://nyayasaar:password@localhost:5432/nyayasaar_dev
alembic upgrade head

# Seed a demo user + three clearly-labelled [DEMO] sample cases (idempotent):
python -m scripts.seed_demo
# Demo credentials default to demo@nyayasaar.example / demo-password-123
# (override with --email/--password or DEMO_USER_* env vars).
# Sign in with them at http://localhost:3000/signin
```

Note: without `DATABASE_URL`, the seed script creates an SQLite file database automatically.

### Test credentials and registration

There is no pre-provisioned production user. For a fresh deployment either register through the `/signin` page ("Create account") or run the seed script. Change the demo password before letting anyone else near the instance.

---

## Render deployment (API)

### Service type
**Web Service** (not a Function) — required for persistent processes and LangGraph workflows.

### Repository root
The Render service must be configured to use `apps/api` as the root directory, or the start command must `cd` into it.

### Build command
```bash
pip install -r requirements.txt
```

### Start command
```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Health check path
```
/api/v1/health
```

### Environment variables (set in Render dashboard)

| Variable | Required | Notes |
|---|---|---|
| `APP_ENV` | Yes | Set to `production` |
| `PYTHON_VERSION` | Yes (Render) | `3.13.17` — required by the pinned LangGraph/langsmith stack |
| `APP_SECRET_KEY` | Yes | Random 32-char hex string |
| `JWT_SECRET_KEY` | Yes (Stage 3) | Separate secret for JWTs (falls back to `APP_SECRET_KEY`) |
| `CORS_ORIGINS` | Yes | Your Vercel frontend URL |
| `AI_PROVIDER` | For AI features | `gemini` (default), `openai`, `openai_compatible`, `anthropic`, `mock` |
| `AI_MODEL` | No | Model ID for the selected provider; empty uses a provider default |
| `AI_API_KEY` | For real AI | Provider key (server-side only). Never expose to Vercel/browser |
| `AI_BASE_URL` | If compatible | Required for `openai_compatible`; optional gateway override |
| `AI_TIMEOUT_S` | No | Per-request timeout (default 45) |
| `AI_MAX_RETRIES` | No | Transport retries for timeout/429/5xx (default 2) |
| `AI_STRUCTURED_RETRIES` | No | JSON repair attempts (default 1) |
| `AI_MAX_OUTPUT_TOKENS` | No | Output cap (default 4096) |
| `AI_JSON_MODE` | No | `json_object` (default), `json_schema`, or `none` |
| `AI_ALLOW_MOCK` | No | Must be explicitly `true` to allow fixture mode in production |
| `GEMINI_API_KEY` | Legacy | Used only when `AI_PROVIDER=gemini` and `AI_API_KEY` is empty |
| `GEMINI_MODEL_ID` | Legacy | Used only when `AI_PROVIDER=gemini` and `AI_MODEL` is empty |
| `AGENT_EXECUTION_TIMEOUT_S` | No | Whole-workflow timeout (default 120) |
| `AGENT_MAX_LLM_CALLS` | No | Model-call budget per run (default 3) |
| `AGENT_MAX_INPUT_CHARS` | No | Source excerpt budget (default 24000) |
| `AGENT_MAX_TOTAL_TOKENS` | No | Token budget per run (default 80000) |
| `AGENT_MAX_VERIFIER_RETRIES` | No | Analyst revisions after verification (default 1) |
| `AGENT_MAX_WORKFLOW_ATTEMPTS` | No | Manual retry limit per run (default 2) |
| `DATABASE_URL` | Yes (Stage 3) | Async asyncpg URL (Render internal database URL + `+asyncpg`) |
| `DATABASE_SYNC_URL` | Yes (Stage 3) | Sync psycopg-3 URL for Alembic |
| `REDIS_URL` | Not used in Stage 5 | Reserved for a durable queue (D-029) |
| `NEO4J_URI` | Optional | Neo4j for citation graphs |
| `NEO4J_USER` | Optional | Neo4j username |
| `NEO4J_PASSWORD` | Optional | Neo4j password |
| `STORAGE_BACKEND` | No | `local` (default) or `s3` |
| `STORAGE_LOCAL_PATH` | No | Root dir for local uploads (default `./uploads`); ignored when `STORAGE_BACKEND=s3` |
| `AWS_BUCKET_NAME` | If `s3` | S3 bucket name |
| `AWS_REGION` | If `s3` | AWS region (default `us-east-1`) |
| `AWS_ACCESS_KEY_ID` | If `s3` | S3 credentials |
| `AWS_SECRET_ACCESS_KEY` | If `s3` | S3 credentials |
| `MAX_UPLOAD_SIZE_MB` | No | Per-file size limit in MB (default `50`) |
| `MAX_DOCUMENTS_PER_CASE` | No | Hard cap per case (default `50`) |

### AI provider configuration and smoke test

Provider/model changes require no code changes:

```bash
# Gemini (default, official google-genai SDK)
AI_PROVIDER=gemini
AI_MODEL=gemini-3.1-flash-lite
AI_API_KEY=...

# OpenAI
AI_PROVIDER=openai
AI_MODEL=gpt-4.1-mini
AI_API_KEY=...

# Groq / OpenRouter / Together / Ollama / LM Studio
AI_PROVIDER=openai_compatible
AI_BASE_URL=https://api.groq.com/openai/v1
AI_MODEL=llama-3.3-70b-versatile
AI_API_KEY=...

# Anthropic
AI_PROVIDER=anthropic
AI_MODEL=claude-sonnet-4-5
AI_API_KEY=...
```

After deploy:

1. `GET /api/v1/ai/status` (authenticated) must report `is_mock: false`, the expected provider/model, and `configured: true`.
2. Upload a small TXT/PDF with known text, open the case **Analysis** tab, run it, and confirm every fact cites the real document/page and the result says `is_mock: false`.
3. If `is_mock: true` appears, the key is missing or invalid for the selected provider. Do **not** treat fixture output as analysis. In production, fixture mode is disabled unless `AI_ALLOW_MOCK=true` is set deliberately.
4. If a run fails with `provider_model_unavailable`, the model ID has been retired for your account; set `AI_MODEL` to a model your key can use.
5. Check server logs for `AI provider configured provider=... model=...` (never the key or document text).

### Cost notes (Render)

- **Free tier:** Web services spin down after 15 minutes of inactivity (cold start ~30s). Not suitable for production.
- **Starter plan (~\$7/month):** No spin-down, 512 MB RAM, 0.5 CPU. Minimum for persistent operation.
- **Managed PostgreSQL:** Render's free tier PostgreSQL expires after 90 days. Use a paid plan or Supabase for production.
- **Estimated baseline cost:** ~\$14–20/month (API service + PostgreSQL Starter).

---

## Vercel deployment (Frontend)

### Configuration

1. Connect the repository to Vercel.
2. Set the **Root Directory** to `apps/web`.
3. Framework preset: **Next.js**.
4. Add environment variables in the Vercel dashboard:

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Your Render API URL (e.g. `https://nyayasaar-api.onrender.com`) |

### Build command (auto-detected)
```bash
pnpm build
```

### Cost notes (Vercel)

- **Hobby (free):** Sufficient for development and low-traffic demos. Bandwidth limits apply.
- **Pro (~\$20/month):** Required for team collaboration, custom domains with SSL, and commercial use.

---

## Database migrations

Alembic migrations run as part of the Render build command, before the service starts:

```bash
# Render build command:
pip install -r requirements.txt && alembic upgrade head
```

- Alembic reads `DATABASE_SYNC_URL` (sync psycopg-3 URL) — on Render, take the internal database URL and replace the driver: `postgresql+psycopg://...`.
- `DATABASE_URL` (used by the app at runtime) must be the async variant: `postgresql+asyncpg://...`.
- Migration `001` creates `users`, `cases`, and `case_memberships`.
- Migration `002` (Stage 4) creates `documents` and `document_chunks`; enables the `pgvector` extension.
- Migration `003` (Stage 5) creates `workflow_runs` and its indexes.
- Run `alembic upgrade head` to apply all pending migrations atomically.
- Run `alembic downgrade base` only when you accept full data loss.
- ⚠️ PostgreSQL behaviour was logic-verified against SQLite in this environment (D-015/D-032). Run `alembic upgrade head` against the production database once at first deploy and confirm all six tables exist, including `workflow_runs`.

---

## Optional services

### Neo4j (citation graphs)

- Hosted: [Neo4j AuraDB](https://neo4j.com/cloud/platform/aura-graph-database/) — free tier available (limited to 200k nodes).
- Local: `docker run -p 7474:7474 -p 7687:7687 neo4j:latest`
- Set `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` in environment.
- The core product functions without Neo4j; citation graph features are gated.

### Redis (background jobs — not used in Stage 5)

- Render Redis: available from ~\$10/month.
- Local: `docker run -p 6379:6379 redis:latest`
- Stage 5 runs analysis as a bounded in-process FastAPI background task (D-029). Redis/Celery becomes necessary when analysis volume, OCR, or crash-safe long jobs require a durable queue.

### LangSmith (LLM tracing)

- Free tier available at [smith.langchain.com](https://smith.langchain.com).
- Set `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, `LANGCHAIN_TRACING_V2=true`.
- Completely optional; the API runs without it.

---

## Security checklist (before production)

- [ ] `APP_SECRET_KEY` is a random 32+ char hex string
- [ ] `APP_ENV=production` (disables `/docs`, `/redoc`, `/openapi.json`)
- [ ] `CORS_ORIGINS` is set to the exact Vercel domain only
- [ ] `AI_API_KEY` (or legacy `GEMINI_API_KEY`) is set only as a Render environment variable (never committed)
- [ ] `GET /api/v1/ai/status` reports `is_mock: false` and the intended provider/model
- [ ] A real analysis run cites real document IDs/pages and is not labelled as a fixture
- [ ] `AI_ALLOW_MOCK` is not enabled in production
- [ ] `DATABASE_URL` uses a dedicated database user with least privilege
- [ ] All file uploads validated (type, size, sanitised filename)
- [x] Authentication enabled (Stage 3 — JWT bearer, bcrypt password hashing)
- [x] Case-level authorisation enabled (Stage 3 — ownership enforced in SQL, tested)
- [x] File uploads validated — extension, magic bytes, size, UUID-based storage key (Stage 4)
- [ ] Demo seed data removed / demo password changed before real use
- [ ] Rate limiting enabled (Stage 7)
- [ ] HTTPS enforced on all services (automatic on Render/Vercel)

