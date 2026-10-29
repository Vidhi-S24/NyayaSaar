# Stage 1 Handoff — Repository Audit and Foundation

**Stage:** 1 of 7
**Completed:** 2026-10-29
**Status:** ✅ Complete — all acceptance criteria met

---

## What was built

Stage 1 establishes the full monorepo foundation: directory structure, tooling, configuration patterns, documentation, and verified-running development servers for both the frontend and backend.

---

## Repository structure

```
nyayasaar/
├── .env.example                 # All env vars documented with safe placeholders
├── .gitignore                   # Node, Python, Next.js, editors
├── package.json                 # Root pnpm workspace scripts
├── pnpm-workspace.yaml          # Workspace: apps/*, packages/*
├── README.md                    # Project overview, quick-start, commands
│
├── apps/
│   ├── web/                     # Next.js 15 App Router frontend
│   │   ├── src/
│   │   │   ├── app/
│   │   │   │   ├── layout.tsx   # Root layout (Inter, Lora, JetBrains Mono fonts)
│   │   │   │   ├── page.tsx     # Minimal homepage shell
│   │   │   │   └── globals.css  # Design tokens (CSS vars), Tailwind base
│   │   │   ├── lib/
│   │   │   │   ├── utils.ts     # cn(), capitalise(), formatDate()
│   │   │   │   ├── utils.test.ts # Vitest tests
│   │   │   │   ├── api-client.ts # Typed fetch wrapper
│   │   │   │   └── api/
│   │   │   │       └── health.ts # Health API queries
│   │   │   └── test/
│   │   │       └── setup.ts     # Vitest + @testing-library/jest-dom
│   │   ├── next.config.js
│   │   ├── tailwind.config.js   # Design tokens: ink/navy, parchment, teal
│   │   ├── postcss.config.js
│   │   ├── tsconfig.json        # Strict TS, App Router, paths
│   │   ├── vitest.config.ts
│   │   ├── eslint.config.mjs
│   │   ├── .prettierrc
│   │   └── package.json
│   │
│   └── api/                     # FastAPI backend
│       ├── app/
│       │   ├── main.py          # App factory, lifespan, CORS, error handling
│       │   ├── config.py        # pydantic-settings, all env vars
│       │   ├── models/
│       │   │   └── responses.py # ApiResponse[T], HealthResponse, PaginatedData
│       │   └── routers/
│       │       └── health.py    # GET /api/v1/health, GET /api/v1/ready
│       ├── tests/
│       │   └── test_health.py   # pytest tests for health endpoints
│       ├── requirements.txt
│       ├── requirements-dev.txt
│       ├── pyproject.toml       # pytest config
│       └── README.md
│
├── packages/
│   └── shared/                  # Shared TypeScript types
│       ├── src/index.ts         # Cases, documents, workflows, health, API types
│       ├── package.json
│       └── tsconfig.json
│
└── docs/
    ├── architecture.md          # System diagram, data flows, module boundaries
    ├── decisions.md             # 12 design decisions with rationale
    ├── deployment.md            # Render + Vercel guide, costs, security checklist
    ├── implementation-status.md # Stage progress, acceptance criteria
    └── stage-handoffs/
        └── stage-1.md           # This file
```

---

## Verification results (actual commands run and their output)

### Python API

```
Command: cd apps/api && .venv\Scripts\python -m pytest tests/ -v
Result: All 4 tests pass
  test_root_returns_service_info PASSED
  test_health_liveness PASSED
  test_health_readiness PASSED
  test_health_response_envelope PASSED
```

```
Command: .venv\Scripts\uvicorn app.main:app --port 8000
Result: Started on http://localhost:8000
  GET /api/v1/health → 200 {"success":true,"data":{"status":"ok",...}}
  GET /api/v1/ready  → 200 {"success":true,"data":{"status":"degraded",...}}
```

### Frontend

```
Command: pnpm dev:web
Result: Started on http://localhost:3000
  Root page renders minimal app shell
```

```
Command: pnpm type-check (from apps/web)
Result: 0 errors
```

```
Command: pnpm test (from apps/web — Vitest)
Result: utils.test.ts — all tests pass
  cn() merges class names ✓
  cn() resolves Tailwind conflicts ✓
  cn() handles conditional classes ✓
  capitalise() ✓ × 3
```

---

## Environment variables introduced in Stage 1

All defined in `.env.example`. None required for Stage 1 basic startup. Required values for AI and database features are documented and staged.

| Variable | Required now | Notes |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Dev default: `http://localhost:8000` | Frontend → backend URL |
| `APP_ENV` | Default: `development` | |
| `APP_SECRET_KEY` | Default insecure placeholder | **Must change in production** |
| `CORS_ORIGINS` | Default: `http://localhost:3000` | |
| `GEMINI_API_KEY` | Stage 5 | AI features |
| `GEMINI_MODEL_ID` | Default: `gemini-2.0-flash-001` | |
| `DATABASE_URL` | Stage 3 | PostgreSQL |
| `DATABASE_SYNC_URL` | Stage 3 | Alembic |
| `REDIS_URL` | Stage 5 | Background jobs |
| `NEO4J_URI/USER/PASSWORD` | Optional | Citation graphs |

---

## Known limitations

1. **`tailwindcss-animate`** — referenced in `tailwind.config.js` but only resolves after `pnpm install` completes in `apps/web`. Run `pnpm install` from the root before starting the frontend.
2. **shadcn/ui** — not yet installed. Tailwind and radix dependencies are listed in `package.json` but shadcn CLI init happens in Stage 2.
3. **No database** — PostgreSQL, Alembic, and SQLAlchemy are not wired; Stage 3 work.
4. **No authentication** — Stage 3 work.
5. **No AI integration** — Gemini and LangGraph are documented but not wired; Stage 5 work.
6. **`apps/worker`** — not scaffolded; added in Stage 5 when Celery workers are needed.

---

## How to run after cloning

```bash
# 1. Install pnpm globally if not present
npm install -g pnpm

# 2. Install all workspace dependencies
pnpm install

# 3. Start the frontend
pnpm dev:web
# → http://localhost:3000

# 4. In another terminal: start the API
cd apps/api
python -m venv .venv

# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# → http://localhost:8000/api/v1/health

# 5. Run API tests
python -m pytest

# 6. Run frontend tests
cd ../web  # or from root: pnpm test
pnpm test
```

---

## What comes next — Stage 2

**Stage 2: Premium Frontend and Application Experience**

Build the full NyayaSaar UI:
- Dashboard with case list, activity feed, statistics
- Case workspace (sidebar nav, document panel, analysis panel)
- Document library with upload UI
- shadcn/ui component setup (`npx shadcn@latest init`)
- Navigation, header, sidebar components
- Loading, empty, error, success, and progress states
- Responsive layout and keyboard accessibility
- Realistic sample/demo data fixtures
- Consistent design system using the ink/navy/parchment/teal tokens

**Prerequisites for Stage 2:**
- Stage 1 complete (this stage ✅)
- `pnpm install` run from root
- Frontend starts on `http://localhost:3000`

---

## Stage 2 continuation prompt

See below.
