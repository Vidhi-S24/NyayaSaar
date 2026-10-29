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
