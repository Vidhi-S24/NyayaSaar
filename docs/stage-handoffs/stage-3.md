# Stage 3 Handoff — Database, Authentication, and Case Management

**Stage:** 3 of 7
**Completed:** 2026-11-13
**Status:** ✅ Complete — all acceptance criteria met (with one documented environment limitation)

---

## Scope

Persistence foundations (PostgreSQL/SQLAlchemy/Alembic with a SQLite dev fallback), JWT authentication, server-enforced case-level authorization, and real case CRUD wired end-to-end through the frontend. Stage 4 (document ingestion) was NOT started.

> ⚠️ Note for future agents: `docs/stage-handoffs/stage-2.md` was missing from the repository when this session started. Stage 2 state was reconstructed from `docs/implementation-status.md` and git history. This session also found and completed an **uncommitted, unverified Stage 3 backend** left in the working tree by a previous session; it was fixed (see "Fixes applied to in-progress work") and verified rather than rewritten.

---

## What was built

### Backend (`apps/api`)

| Path | Description |
|---|---|
| `alembic.ini`, `alembic/env.py`, `alembic/versions/001_initial_schema.py` | Migrations: `users`, `cases`, `case_memberships` (unique `(case_id,user_id)` declared inline for dialect portability) |
| `app/db/base.py` | Async engine (SQLite fallback when `DATABASE_URL` unset), `sessionmaker`, `TimestampMixin`, `Base` |
| `app/db/session.py` | `get_async_session` FastAPI dependency (commit/rollback/close lifecycle) |
| `app/db/models/user.py`, `case.py` | `User`, `Case`, `CaseMembership` models with FKs, indexes, timestamps |
| `app/schemas/auth.py`, `cases.py` | Pydantic v2 request/response schemas (email validation, length limits, enums for status/priority) |
| `app/services/auth.py` | bcrypt hashing (`bcrypt` used directly), PyJWT encode/decode, `get_current_user` dependency, register/login helpers |
| `app/services/cases.py` | create/get/list/update/delete; **owner_id in every SQL query**; pagination + search + status filter |
| `app/routers/auth.py` | `POST /api/v1/auth/register` (201, 409 dup), `POST /api/v1/auth/login` (200, 401), `GET /api/v1/auth/me` |
| `app/routers/cases.py` | `GET/POST /api/v1/cases`, `GET/PATCH/DELETE /api/v1/cases/{id}`; 404 (not 403) for other users' cases |
| `app/config.py` | Added `jwt_secret_key`, `jwt_algorithm`, `jwt_access_token_expire_minutes`, `database_url`, `database_sync_url` |
| `scripts/seed_demo.py` | Idempotent seed: demo user + 3 `[DEMO]`-prefixed fictional cases; creates schema if the DB is empty |
| `tests/conftest.py` | Per-test in-memory SQLite (aiosqlite) + dependency override + auth fixtures |
| `tests/test_auth.py`, `tests/test_cases.py` | 9 auth tests + 12 case tests incl. cross-user authorization boundaries |

### Frontend (`apps/web`)

| Path | Description |
|---|---|
| `src/lib/api-client.ts` | Bearer-token injection, envelope unwrapping, global 401 handler |
| `src/lib/api/auth.ts`, `cases.ts` | Typed API calls; token storage helpers; `userInitials`, `formatRelativeTime` |
| `src/lib/auth/auth-context.tsx` | `AuthProvider`/`useAuth`: restore on mount (token → `/auth/me`), signIn/signUp/signOut |
| `src/components/providers.tsx` | TanStack `QueryClientProvider` + `AuthProvider` in the root layout |
| `src/app/(app)/layout.tsx` | Auth guard: full-screen "Checking session…" loader; redirect to `/signin` when unauthenticated |
| `src/app/signin/page.tsx` | Sign-in / create-account tabs; react-hook-form + zod; inline field errors; auth error banner |
| `src/app/(app)/cases/page.tsx` | Live list: debounced search, status filter, pagination, skeletons, empty + error states, create dialog, per-row delete with confirmation |
| `src/app/(app)/cases/[id]/page.tsx` | Live detail: skeletons, 404/no-access state, error+retry, edit dialog, delete → redirect, issues/documents tabs with honest empty states |
| `src/app/(app)/dashboard/page.tsx` | Live stats from real cases; "Reports/Contradictions" shown as "— (Stage 5)"; demo activity feed replaced by honest empty state |
| `src/app/(app)/settings/page.tsx` | Real signed-in account, sign-out button |
| `src/components/cases/case-form-dialog.tsx` | Create/edit form (title required; tags comma-separated; issues one per line); unsaved-changes AlertDialog |
| `src/components/ui/{dialog,alert-dialog,label}.tsx` | Radix wrappers |
| `src/components/layout/topbar.tsx` | Account menu with real initials/email + sign out; **non-functional notification bell removed** |
| `src/lib/api/cases.test.ts` | Unit tests for `userInitials` / `formatRelativeTime` |
| `package.json` | Removed `next-auth` (unused/wrong approach); added `@hookform/resolvers` |

### Shared (`packages/shared`)

- `src/index.ts` aligned to the actual API: `Case`, `CaseSummary`, `CaseListResponse`, `CaseCreateInput/UpdateInput`, `User`, `TokenResponse`, `CaseStatus = active|review|closed|archived`, `CasePriority`.

### Docs & config

- `.env.example` — JWT settings, demo seed vars, DATABASE_URL/SYNC_URL notes
- `docs/implementation-status.md`, `docs/decisions.md` (D-013…D-018), `docs/architecture.md` (data model + auth flow), `docs/deployment.md` (DB setup, migrations, seed), `README.md` (stage table + API commands)

---

## Fixes applied to in-progress work (previous session's uncommitted Stage 3)

1. **passlib → bcrypt directly.** passlib 1.7.4 crashes with bcrypt 5.0 (verified `ValueError` from passlib's backend detection). Hashing now uses `bcrypt.hashpw/checkpw` with the standard 72-byte truncation.
2. **python-jose → PyJWT** (maintained; same API shape).
3. **SQLAlchemy pinned `<2.1`** — 2.1's compiled Cython extension is blocked by this machine's Application Control policy and has no pure-Python fallback; 2.0.x has one. (D-015)
4. **email-validator added** (required by Pydantic `EmailStr`); `asyncpg >=0.31` (0.30 has no Python-3.15 wheel); `psycopg[binary]` added for Alembic sync migrations.
5. **Alembic `001` fixed** — unique constraint moved into `create_table` (SQLite cannot ALTER-add constraints; the standalone `create_unique_constraint` failed).
6. **`next-auth` removed** from `apps/web/package.json` — it conflicted with the backend-JWT architecture and was never wired.
7. **Engine SQL echo disabled** (was logging every statement in development).

---

## Verification commands and actual results

| Command (from `apps/api` unless noted) | Result |
|---|---|
| `.venv\Scripts\python -m pytest tests/ -v` | **25 passed** (9 auth, 12 cases, 4 health) |
| `$env:DATABASE_SYNC_URL="sqlite:///./migration-check.db"; alembic upgrade head` | exit 0, initial schema applied |
| `alembic downgrade base` then `alembic upgrade head` | exit 0 both (round-trip) |
| Seed against migration-created DB: `python -m scripts.seed_demo` | "Created demo user… Created 3 demo case(s)"; re-run idempotent |
| Live: `uvicorn app.main:app --port 8000` (SQLite dev DB) | register 201 → create case 201 → list 200 → me 200 → delete 200 → get-after-delete **404**; demo login 200 sees 3 cases |
| (apps/web) `pnpm exec tsc --noEmit` | 0 errors |
| (apps/web) `pnpm exec vitest run` | **15 passed** (2 files) |
| (apps/web) `pnpm build` (`next build`) | Compiled; 15 routes; lint+type check pass |
| Smoke: `next dev` + API on SQLite | `/signin` 200, `/` 200, `/dashboard` 200 |

Fixes made to satisfy verification: one unit-test fix (`userInitials` empty-string fallback → `?`), five pre-existing lint errors (unused imports in `history`/`intelligence`/`settings`, unused `setCollapsed`, empty `InputProps` interface), and a `StatCard` value-type widening.

---

## Environment variables introduced / changed

| Variable | Default | Notes |
|---|---|---|
| `JWT_SECRET_KEY` | falls back to `APP_SECRET_KEY` | Set a distinct random 32+ char hex secret in production |
| `JWT_ALGORITHM` | `HS256` | |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | |
| `DATABASE_URL` | *(empty → SQLite fallback)* | Async (asyncpg) URL used by the app |
| `DATABASE_SYNC_URL` | *(empty)* | Sync (psycopg 3) URL used by Alembic |
| `DEMO_USER_EMAIL` / `DEMO_USER_PASSWORD` / `DEMO_USER_NAME` | `demo@nyayasaar.example` / `demo-password-123` / `Demo Advocate` | Seed script defaults — development only |

**New pip dependencies:** `asyncpg`, `SQLAlchemy[asyncio]` (<2.1), `alembic`, `pgvector`, `greenlet`, `psycopg[binary]`, `bcrypt`, `pyjwt[crypto]`, `email-validator`, `aiosqlite` (dev), `pytest-asyncio`.
**Removed:** `passlib`, `python-jose`, `next-auth` (npm).
**New npm dependencies:** `@hookform/resolvers`.

## External setup required (manual, not yet verified here)

1. **PostgreSQL** — none available in this environment (no local service, no Docker; psycopg binary DLL blocked by Application Control policy). On a machine with Postgres:
   ```bash
   export DATABASE_URL=postgresql+asyncpg://nyayasaar:password@localhost:5432/nyayasaar_dev
   export DATABASE_SYNC_URL=postgresql+psycopg://nyayasaar:password@localhost:5432/nyayasaar_dev
   alembic upgrade head        # verify: users, cases, case_memberships exist
   python -m scripts.seed_demo
   ```
2. **Render PostgreSQL** at first deploy — run `alembic upgrade head` in the build command and confirm the three tables (documented in `docs/deployment.md`).

---

## Known limitations

1. PostgreSQL migrations verified only against SQLite in this environment (D-015). PostgreSQL dialect behaviour of migration `001` is standard (no exotic types) but unverified here.
2. JWT stored in `localStorage` — XSS-readable; short expiry + server-side authz are the current mitigations (httpOnly cookies / CSP deferred).
3. Case sharing via `case_memberships` is provisioned but **not wired into authorization** (owner-only) — deliberate Stage 3 scope.
4. No rate limiting, no email verification, no password reset.
5. `bcrypt` truncates passwords >72 bytes (standard bcrypt behaviour, documented in code).
6. Demo data remains on: documents library, history, and the five AI module shells (all carry `DemoNotice`).
7. Stale dev-server processes holding ports 8000/3000 had to be killed during verification — if `pnpm dev:web` or uvicorn fails to bind, check for zombie processes.

---

## Post-handoff fix 2 (2026-11-13, user-reported)

**Symptom:** Login/create-account in the browser returned *"Cannot read properties of undefined (reading 'access_token')"*.

**Cause:** `lib/api-client.ts` `request()` **unwrapped** the `ApiResponse` envelope (returned `envelope.data` directly), while every caller — `signIn`/`signUp`, the cases queries, health — expected the **full envelope** and read `.data` off it. The result was `undefined` at every call site.

**Fix:**
- `api-client.ts`: `request<T>()` now resolves to the **complete** `ApiEnvelope<T>`; a 200 body without the envelope shape throws `invalid_response` instead of faking success; `success: false` bodies throw with the server's message.
- `lib/api/auth.ts`, `lib/api/cases.ts`, `lib/api/health.ts` — types now pass the **payload** type (`TokenResponse`, `Case`, …) and callers read `.data` consistently.
- `auth-context.tsx` — guards for a missing token/profile with clear error messages (surfaced in the sign-in form).
- Regression tests added: `lib/api-client.test.ts` (5 tests) covering the envelope contract, `success:false` errors, 401 handling + global handler, Authorization header injection, and non-envelope rejection.

**Important tooling note:** `tsc --noEmit` had been reporting **0 errors due to a stale `tsconfig.tsbuildinfo` incremental cache** while the code had 5 real type errors. The cache was deleted and the build re-verified. If type checking ever "passes" suspiciously fast, delete `apps/web/tsconfig.tsbuildinfo` and re-run.

**Verification after the fix:** `tsc --noEmit` 0 errors (clean cache) · vitest **20 passed** · `next build` success · live API login returns envelope with `access_token` · `/signin` and `/` return 200.

---

## Post-handoff fix (2026-11-13, user-reported)

**Symptom:** Login/create-account returned a fetch error; `POST /api/v1/auth/register` returned 500 when `DATABASE_URL` was unset.

**Cause:** The no-`DATABASE_URL` fallback used an **in-memory** SQLite database — no tables (500 on every auth call) and nothing persisted.

**Fix (D-019):**
- `app/db/base.py` — fallback is now the file `apps/api/nyayasaar-dev.db` (git-ignored)
- `app/main.py` — startup auto-creates the schema if the dev DB is empty (Alembic stays canonical for production)
- `.gitignore` — `apps/api/*.db` added

**Verified live after the fix:** register 201 (+ correct CORS origin header), demo account seeded via `python -m scripts.seed_demo`, demo login 200 (sees 3 cases), `/signin` 200. Tests re-run: 25 passed.

**Demo credentials for local dev:**
- Email: `demo@nyayasaar.example`
- Password: `demo-password-123`
- (Or create your own account on the `/signin` page — it now works.)

---

## How to run

```bash
# Frontend
pnpm install            # once, from root
pnpm dev:web            # → http://localhost:3000

# API
cd apps/api
.venv\Scripts\activate  # Windows (or source .venv/bin/activate)
# Set DATABASE_URL + DATABASE_SYNC_URL in .env, or leave unset for SQLite dev
alembic upgrade head            # PostgreSQL path; skip for SQLite dev
python -m scripts.seed_demo     # optional demo data
uvicorn app.main:app --reload --port 8000

# Tests
python -m pytest tests/ -v     # backend (from apps/api)
pnpm test                       # frontend (from root)
pnpm --filter @nyayasaar/web exec tsc --noEmit
pnpm build:web
```

Sign in at `http://localhost:3000/signin` — create an account, or use seeded `demo@nyayasaar.example` / `demo-password-123` (change it before sharing the instance).

---

## What comes next — Stage 4

**Stage 4: Secure Document Upload, Storage, Extraction, and Processing Status**

- Upload endpoint (`POST /api/v1/cases/{case_id}/documents`) with multipart validation, size limits, safe filenames, and case-level authorization
- Storage provider abstraction (local dev + S3-compatible production interface)
- PyMuPDF/Docling text extraction with OCR fallback for scanned PDFs
- Page-referenced chunk storage (pgvector) and a document model with processing status
- Frontend: real document library + case documents tab replacing demo fixtures
- Treat extracted text as untrusted content (prompt-injection defence groundwork)

**Prerequisites:** Stage 3 complete (this handoff). PostgreSQL strongly recommended from Stage 4 onward (pgvector requires it); Redis/Celery only if processing becomes long-running.
