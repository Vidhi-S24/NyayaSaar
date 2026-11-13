# NyayaSaar — Design Decisions

> This file records all significant architectural and technology decisions with rationale. New decisions are appended; old entries are preserved.

---

## Decision log

### D-001: pnpm workspaces monorepo

**Date:** Stage 1
**Decision:** Use pnpm workspaces as the monorepo tool.
**Rationale:** pnpm is faster than npm/yarn, has excellent workspace support, and is the standard for modern JS monorepos. `apps/web` and `packages/shared` share a lock file and hoisted dependencies. The Python API lives in `apps/api` but is not a pnpm package — it uses its own venv.
**Alternatives considered:** Turborepo (adds complexity without enough benefit at this stage), Nx (too heavy).

---

### D-002: Next.js 15 App Router

**Date:** Stage 1
**Decision:** Use Next.js 15 with the App Router (not Pages Router).
**Rationale:** App Router enables React Server Components, co-located layouts, streaming, and modern data patterns. This is the current recommended Next.js paradigm and is required for Vercel's edge capabilities.
**Alternatives considered:** Pages Router (legacy), Remix (less familiar, smaller ecosystem for this use case).

---

### D-003: FastAPI on Render, not Vercel serverless

**Date:** Stage 1
**Decision:** Deploy the FastAPI backend to Render (persistent web service), not Vercel serverless functions.
**Rationale:** Document processing (PyMuPDF, Docling, OCR) and LangGraph workflows are long-running and stateful. Vercel serverless functions have a 60-second timeout and are stateless — unsuitable for agentic workflows. Render provides persistent processes, configurable timeouts, and background worker support.
**Alternatives considered:** Vercel serverless (ruled out — timeout limits), AWS Lambda (overkill for this stage), Railway (similar to Render, less documentation).

---

### D-004: Google Gemini as the primary AI provider

**Date:** Stage 1
**Decision:** Use the official Google Gen AI SDK for Gemini. The model ID is configurable via `GEMINI_MODEL_ID` environment variable.
**Rationale:** Per project requirements. Keeps the option open to switch models (Flash → Pro → experimental) without code changes. API key is server-side only; never in the client bundle.
**Alternatives considered:** OpenAI (not specified), Anthropic (not specified).

---

### D-005: LangGraph for agentic orchestration

**Date:** Stage 1
**Decision:** Use LangGraph for all stateful multi-agent workflows.
**Rationale:** Per project requirements. LangGraph provides typed state, conditional routing, bounded retries, checkpoints, and resumability — the properties needed for legal research workflows that must be auditable and recoverable. Plain prompting chains are not sufficient.
**Alternatives considered:** LangChain LCEL chains (too linear, no checkpoints), CrewAI (less control over state), custom async orchestration (reinventing the wheel).

---

### D-006: PostgreSQL + pgvector as the primary data store

**Date:** Stage 1
**Decision:** Use PostgreSQL with pgvector for both relational data and vector search. Hybrid retrieval (full-text + vector) is the default strategy.
**Rationale:** Reduces infrastructure to one database (vs. separate vector DB). pgvector is well-maintained and sufficient for the expected document volumes. Full-text search covers keyword queries; vector search covers semantic similarity.
**Alternatives considered:** Pinecone (separate service, cost), Weaviate (complexity), SQLite (not production-suitable for multi-user), MongoDB (no strong reason to choose over PostgreSQL for this use case).

---

### D-007: Neo4j is optional

**Date:** Stage 1
**Decision:** Neo4j is an optional dependency for citation graph features. The core product must work without it.
**Rationale:** Citation graphs add value for precedent analysis, but adding a required graph database complicates setup and cost. Features that need Neo4j are gated behind `settings.neo4j_configured` and fail gracefully.
**Alternatives considered:** In-PostgreSQL graph (ltree, recursive CTEs) — possible future fallback.

---

### D-008: Redis + Celery deferred until needed

**Date:** Stage 1
**Decision:** Background jobs and Redis are not added until Stage 5+ when long-running document processing requires them.
**Rationale:** Premature infrastructure adds operational cost and complexity. FastAPI's background tasks (`BackgroundTasks`) are sufficient for short async work. Celery will be added when document ingestion pipelines require durable, retriable background processing.

---

### D-009: No `apps/worker` scaffolded in Stage 1

**Date:** Stage 1
**Decision:** The optional worker app is not scaffolded yet.
**Rationale:** It is not needed until Stage 5. Scaffolding it now would be speculative. It will be created as a separate Render service when Celery workers are required.

---

### D-010: Design system direction — ink/navy, parchment, teal

**Date:** Stage 1
**Decision:** The NyayaSaar colour palette uses deep ink/navy (primary), warm off-white/parchment (background), and restrained teal (accent).
**Rationale:** Legal-tech context demands trustworthiness, clarity, and authority. These colours are associated with traditional legal aesthetics (ink, parchment) while the teal accent provides a modern, digital feel. Avoids the generic AI dashboard look (electric blue gradients, glassmorphism, emoji icons).
**Tokens defined:** `ink-*`, `parchment-*`, `teal-*` in Tailwind config; CSS variables for shadcn/ui semantic tokens.

---

### D-011: Strict TypeScript throughout the frontend

**Date:** Stage 1
**Decision:** `"strict": true` in all TypeScript configs. Pydantic v2 with strict validation in the backend.
**Rationale:** Legal data requires correctness. Strict typing surfaces bugs at compile time rather than runtime. Shared types in `packages/shared` ensure the frontend and backend agree on data shapes.

---

### D-012: `ApiResponse<T>` envelope for all API responses

**Date:** Stage 1
**Decision:** Every API response is wrapped in `{ success, data, error, meta }`.
**Rationale:** Provides a consistent, machine-readable structure for clients regardless of HTTP status codes. Clients can always check `response.success` without parsing error formats differently per endpoint. Matches the TypeScript type in `packages/shared`.

---

## Stage 3 — Database, Authentication, and Case Management

### D-013: Backend-issued JWT bearer authentication (no NextAuth)

**Date:** Stage 3
**Decision:** Authentication is implemented directly in FastAPI: `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `GET /api/v1/auth/me`. Tokens are short-lived HS256 JWTs signed with `JWT_SECRET_KEY`. The Next.js frontend keeps the token in `localStorage` and sends it as a bearer header.
**Rationale:** FastAPI must enforce case-level authorization server-side, so the backend needs to be the single source of identity truth. Adding NextAuth as a second session layer would create two overlapping session systems with no benefit at this stage. A dedicated external auth provider (Auth0/Clerk/Supabase Auth) can replace the same three endpoints later without touching authorization logic.
**Alternatives considered:** NextAuth/Auth.js (duplicated session logic against the FastAPI backend; the `next-auth` dependency was added by mistake and removed), OAuth-only flows (no password login for private deployments), httpOnly cookie sessions (more secure against XSS but complicates cross-origin Vercel→Render fetches; revisit if the threat model changes).
**Limitations:** Token in `localStorage` is readable by XSS. Mitigations: strict CSP later, short expiry (30 min), server-side authorization on every case route.

### D-014: bcrypt directly (passlib removed), PyJWT (python-jose replaced)

**Date:** Stage 3
**Decision:** Password hashing uses the `bcrypt` library directly. Token encoding/decoding uses `PyJWT`.
**Rationale:** `passlib` is unmaintained (last release 2020) and crashes with `bcrypt ≥ 4.1` (verified: `ValueError: password cannot be longer than 72 bytes` raised from inside passlib's own backend detection with bcrypt 5.0). `python-jose` is similarly dormant. `bcrypt` and `PyJWT` are actively maintained and cover exactly the two functions we need. Passwords are bcrypt-hashed with the standard 72-byte truncation.
**Cost:** Existing hashes generated by passlib remain compatible (standard bcrypt format).

### D-015: SQLAlchemy pinned `<2.1` — compiled Cython extension blocked in sandboxed environments

**Date:** Stage 3
**Decision:** `SQLAlchemy>=2.0.36,<2.1.0` in `apps/api/requirements.txt`.
**Rationale:** SQLAlchemy 2.1.x requires its compiled `_util_cy` extension with no pure-Python fallback. On this development machine a Windows Application Control policy blocks the DLL (`ImportError: DLL load failed`). SQLAlchemy 2.0 ships a pure-Python fallback and imports cleanly. Same consideration applies to `psycopg[binary]`: the prebuilt DLL is blocked locally, but works on Linux deployment targets (Render).
**Consequence:** Alembic migrations were validated against SQLite in this environment. PostgreSQL behaviour must be verified on first deployment to a real PostgreSQL instance (documented in `docs/deployment.md`).

### D-016: Case authorization = ownership check returning 404

**Date:** Stage 3
**Decision:** All case queries filter by `owner_id` in SQL (`WHERE case_id = ? AND owner_id = ?`). A case belonging to another user is indistinguishable from a nonexistent case (404 for GET/PATCH/DELETE), and it never appears in list responses.
**Rationale:** Prevents resource-existence leakage without leaking a 403 that confirms the case exists. The `case_memberships` table exists for future sharing (roles: `owner`/`editor`/`viewer`); it is not yet used for authorization — that is deliberate scope control for Stage 3, and the membership wiring will switch `get_case` from owner-only to owner-or-member.

### D-017: Frontend session restore + client-side route guard

**Date:** Stage 3
**Decision:** `AuthProvider` restores the session on mount (token → `GET /auth/me` → user). The `(app)` route group renders a full-screen loading state while the session is being restored and redirects to `/signin` when unauthenticated. Every API call attaches the bearer token; a global 401 handler clears the session.
**Rationale:** Server components cannot see the browser token, so workspace pages are client components using TanStack Query. Authorization itself remains server-side; the guard is UX, not security.

### D-018: Seed script creates the schema when the database is empty

**Date:** Stage 3
**Decision:** `python -m scripts.seed_demo` creates tables via SQLAlchemy metadata if the target database has no tables, then seeds a demo user and three clearly `[DEMO]`-prefixed fictional cases. It is idempotent.
**Rationale:** Zero-config first-run experience for local development. Alembic remains the canonical migration path for real deployments (the script prints a reminder).

### D-019: Dev fallback is a file-based SQLite DB with startup auto-migration (was in-memory)

**Date:** Stage 3 (post-handoff fix — user-reported login failure)
**Decision:** When `DATABASE_URL` is unset, the API uses the SQLite file `apps/api/nyayasaar-dev.db` (git-ignored). On startup, if that database is empty, the app creates the schema via SQLAlchemy metadata and logs a reminder that Alembic is canonical for production.
**Rationale:** The original fallback was `sqlite:///:memory:`, which broke real use two ways: every connection in the async pool received a fresh empty database (causing intermittent `no such table: users` → HTTP 500 on register/login), and no account could persist across restarts. This was verified live: `POST /api/v1/auth/register` returned 500 with no `DATABASE_URL`, 201 after the fix.
**Consequence:** Users can sign up / sign in with zero configuration; data persists across server restarts. The seeded demo account (`demo@nyayasaar.example` / `demo-password-123`) is created by `python -m scripts.seed_demo`.

