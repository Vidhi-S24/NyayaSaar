# NyayaSaar — Deployment Guide

> Last updated: Stage 1 — Foundation

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
- Python ≥ 3.11
- PostgreSQL (optional for Stage 1)

### Steps

```bash
# 1. Clone the repo
git clone <repo-url>
cd nyayasaar

# 2. Copy env file
cp .env.example .env
# Edit .env — set at minimum NEXT_PUBLIC_API_BASE_URL=http://localhost:8000

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

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# → http://localhost:8000/api/v1/health
# → http://localhost:8000/docs
```

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
| `APP_SECRET_KEY` | Yes | Random 32-char hex string |
| `CORS_ORIGINS` | Yes | Your Vercel frontend URL |
| `GEMINI_API_KEY` | For AI features | Google AI Studio key |
| `GEMINI_MODEL_ID` | No | Defaults to `gemini-2.0-flash-001` |
| `DATABASE_URL` | From Stage 3 | Async asyncpg URL |
| `DATABASE_SYNC_URL` | From Stage 3 | Sync URL for Alembic |
| `REDIS_URL` | From Stage 5 | Redis connection URL |
| `NEO4J_URI` | Optional | Neo4j for citation graphs |
| `NEO4J_USER` | Optional | Neo4j username |
| `NEO4J_PASSWORD` | Optional | Neo4j password |

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

## Database migrations (Stage 3+)

Alembic migrations will be run as a one-off command before the main service starts:

```bash
# Render build command (Stage 3+):
pip install -r requirements.txt && alembic upgrade head
```

---

## Optional services

### Neo4j (citation graphs)

- Hosted: [Neo4j AuraDB](https://neo4j.com/cloud/platform/aura-graph-database/) — free tier available (limited to 200k nodes).
- Local: `docker run -p 7474:7474 -p 7687:7687 neo4j:latest`
- Set `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` in environment.
- The core product functions without Neo4j; citation graph features are gated.

### Redis (background jobs)

- Render Redis: available from ~\$10/month.
- Local: `docker run -p 6379:6379 redis:latest`
- Required from Stage 5 when document processing background jobs are added.

### LangSmith (LLM tracing)

- Free tier available at [smith.langchain.com](https://smith.langchain.com).
- Set `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, `LANGCHAIN_TRACING_V2=true`.
- Completely optional; the API runs without it.

---

## Security checklist (before production)

- [ ] `APP_SECRET_KEY` is a random 32+ char hex string
- [ ] `APP_ENV=production` (disables `/docs`, `/redoc`, `/openapi.json`)
- [ ] `CORS_ORIGINS` is set to the exact Vercel domain only
- [ ] `GEMINI_API_KEY` is set only as a Render environment variable (never committed)
- [ ] `DATABASE_URL` uses a dedicated database user with least privilege
- [ ] All file uploads validated (type, size, sanitised filename)
- [ ] Authentication enabled (Stage 3)
- [ ] Case-level authorisation enabled (Stage 3)
- [ ] Rate limiting enabled (Stage 7)
- [ ] HTTPS enforced on all services (automatic on Render/Vercel)
