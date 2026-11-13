# NyayaSaar — Implementation Status

> Updated: Stage 3 complete

---

## Completed stages

### Stage 3 — Database, Authentication, and Case Management ✅

**Completed:** 2026-11-13
*(See stage-handoffs/stage-3.md for full details)*

#### What was built

| Path | Description |
|---|---|
| `apps/api/alembic/` | Alembic setup + `001_initial_schema` migration (users, cases, case_memberships) |
| `apps/api/app/db/` | Async engine, session dependency, `TimestampMixin`, `User` / `Case` / `CaseMembership` models |
| `apps/api/app/services/auth.py` | bcrypt password hashing (passlib removed), PyJWT tokens, `get_current_user` dependency |
| `apps/api/app/services/cases.py` | Case CRUD service — **authorization enforced in SQL (owner-scoped)** |
| `apps/api/app/routers/auth.py` | `POST /auth/register`, `POST /auth/login`, `GET /auth/me` |
| `apps/api/app/routers/cases.py` | Full case CRUD with pagination, search, status filter, request IDs |
| `apps/api/app/schemas/` | Pydantic request/response schemas (auth + cases) |
| `apps/api/scripts/seed_demo.py` | Idempotent demo seed (demo user + 3 labelled [DEMO] cases) |
| `apps/api/tests/` | 25 tests: auth flows, case CRUD, **authorization boundaries**, validation |
| `apps/web/src/lib/auth/auth-context.tsx` | Session provider (restore/sign-in/sign-up/sign-out, 401 handling) |
| `apps/web/src/lib/api/auth.ts`, `cases.ts` | Typed API wrappers; helpers (`userInitials`, `formatRelativeTime`) |
| `apps/web/src/app/signin/page.tsx` | Sign-in / create-account page (react-hook-form + zod, error/loading states) |
| `apps/web/src/app/(app)/layout.tsx` | Auth guard — session restore loader + redirect to `/signin` |
| `apps/web/src/app/(app)/cases/page.tsx` | Live case list: search, status filter, pagination, create, delete confirm |
| `apps/web/src/app/(app)/cases/[id]/page.tsx` | Live case detail: edit, delete, 404/no-access state, issue/document tabs |
| `apps/web/src/app/(app)/dashboard/page.tsx` | Live case stats + recently updated cases; honest "not yet available" stats |
| `apps/web/src/components/cases/case-form-dialog.tsx` | Create/edit case dialog with unsaved-changes confirmation |
| `apps/web/src/components/ui/{dialog,alert-dialog,label}.tsx` | Radix-based UI primitives |
| `apps/web/src/components/layout/topbar.tsx` | Real account menu (initials, email, sign out); fake notification bell removed |
| `packages/shared/src/index.ts` | Types aligned with the real API (`Case`, `CaseListResponse`, `User`, `TokenResponse`) |

#### Acceptance criteria status

| Criterion | Status |
|---|---|
| Migrations create the schema from a clean database | ✅ Verified against SQLite (upgrade → downgrade → upgrade); PostgreSQL run is a first-deploy step (see D-015) |
| Case CRUD works through the actual frontend and backend | ✅ Verified via API round-trip (register → create → list → update → delete → 404) and frontend pages wired to live queries |
| Authorization enforced and tested | ✅ Owner-scoped SQL; tests prove cross-user 404s for GET/PATCH/DELETE and empty lists |
| API schemas and errors predictable | ✅ `ApiResponse` envelope, Pydantic validation (422), 409/401/403/404 semantics, X-Request-ID header |
| Tests cover key routes, validation, access boundaries | ✅ 25 backend tests + 15 frontend unit tests |
| Frontend build/type checks pass | ✅ `tsc --noEmit` 0 errors; `next build` succeeds; Vitest 15/15 |

#### Verification results (actual)

```
apps/api:  .venv\Scripts\python -m pytest tests/ -v
           → 25 passed (auth 9, cases 12, health 4)
apps/web:  tsc --noEmit            → 0 errors
           vitest run              → 15 passed (2 files)
           next build              → compiled, 15 routes generated
Live smoke: uvicorn (SQLite dev DB) + next dev
           register → 201, create case → 201, list → 200,
           me → 200, delete → 200, get-after-delete → 404
           demo login → 200 (sees 3 demo cases)
Alembic:   upgrade head → downgrade base → upgrade head (SQLite) → exit 0
```

---

### Stage 2 — Premium Frontend and Application Experience ✅

**Completed:** 2026-10-30

Full landing page, dashboard, case workspace, document library, module shells, design system (ink/navy/parchment/teal tokens), demo fixtures clearly labelled as such. *Note: `docs/stage-handoffs/stage-2.md` was not present in the repository when Stage 3 began; Stage 2 state was reconstructed from `docs/implementation-status.md` and the git history.*

### Post-handoff fixes (Stage 3 scope, user-reported)

1. **Dev database fallback** — the no-`DATABASE_URL` fallback was an in-memory SQLite DB (500 on every auth call, nothing persisted). Now a file DB (`apps/api/nyayasaar-dev.db`) with startup schema auto-creation. See `docs/decisions.md` D-019.
2. **API-client envelope mismatch** — the client unwrapped the response envelope while callers read `.data`, producing `undefined` crashes on login. Client now returns the full envelope; regression tests added. See `stage-handoffs/stage-3.md`.
3. **Stale `tsconfig.tsbuildinfo`** was masking real TypeScript errors; deleted and re-verified.

### Stage 1 — Repository Audit and Foundation ✅

**Completed:** 2026-10-29 *(See stage-handoffs/stage-1.md)*

---

## Pending stages

### Stage 4 — Document Ingestion Pipeline ⏳

**Prerequisites:** Stage 3 complete (✅)

**Scope:**
- Secure upload endpoint (validation, size limits, safe filenames, untrusted-content handling)
- Storage abstraction (local dev + production object storage)
- PyMuPDF / Docling text extraction, OCR for scanned PDFs
- Page-referenced chunks, pgvector storage, processing status tracking

### Stage 5 — Gemini / LangGraph Agentic Workflows ⏳
### Stage 6 — Legal Analysis Modules ⏳
### Stage 7 — Evaluation, Monitoring, and Deployment ⏳

---

## Known limitations (Stage 3)

1. **PostgreSQL migrations not yet run against a real PostgreSQL instance** in this environment (no local Postgres/Docker; the machine's Application Control policy blocks the psycopg binary DLL). Migration logic verified via SQLite round-trip. First production deploy must run `alembic upgrade head` and verify.
2. **Dev SQLite fallback is functional, not production-grade** — accounts persist in `apps/api/nyayasaar-dev.db` and the schema is auto-created on startup (D-019). PostgreSQL is required for production and for pgvector (Stage 4).
2. **JWT in localStorage** — vulnerable to XSS; mitigated by short expiry and server-side authorization. CSP and/or httpOnly cookie sessions are future hardening (Stage 7).
3. **Case sharing not yet active** — `case_memberships` exists but authorization is owner-only (D-016). Stage 4+ can wire membership roles.
4. **Document/document-model endpoints don't exist yet** — the case detail "Documents" tab shows an honest empty state; counts stay 0 until Stage 4.
5. **Demo data surfaces remain** — document library, history, and the five module shells still use clearly-labelled fixtures; they wire to real data in Stages 4–6.
6. **Dashboard "Reports Generated" / "Contradictions Found"** show "—" deliberately until Stage 5.
7. **No rate limiting yet** (Stage 7).
8. **No email verification flow** — `users.is_verified` exists but is unused; verification mail is out of scope for Stage 3.
