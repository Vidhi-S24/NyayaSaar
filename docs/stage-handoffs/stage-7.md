# Stage 7 Handoff — Hybrid Legal Retrieval

> Completed: 2026-11-25
> Verification: deterministic backend suite, Alembic migration `001 -> 005` on SQLite, frontend type-check, lint, unit tests, and production build.
> Scope: Stage 7 **Hybrid Legal Retrieval & Legal-Source Provider Layer only**. Contradiction & Gap Hunter (Stage 8), Precedent Explorer conflict graphs, Advocate Mode, and Judge/Clerk Mode remain future work.

---

## 1. What was delivered

### 1.1 Database & pgvector migration (`005_add_hybrid_retrieval.py`)

- Added `legal_records` and `legal_record_chunks` tables (`app/db/models/legal_record.py`) with provenance (`source_provider`, `external_id`, `citation`, `jurisdiction`, `court`, `decision_date`, `year`, `source_url`, `is_fixture`, `page_number`, `paragraph_number`, `char_start`, `char_end`, `content_hash`).
- Extended `document_chunks` with `embedding_json`, `embedding_model`, `embedding_dim`.
- On PostgreSQL (`bind.dialect.name == "postgresql"`): enables `CREATE EXTENSION IF NOT EXISTS vector`, adds `vector(256)` and generated `tsvector` columns, and creates GIN (`search_tsv`) and HNSW (`vector_cosine_ops`) indexes on both `document_chunks` and `legal_record_chunks`.
- On SQLite dev fallback: `app/main.py` ensures `legal_records`, `legal_record_chunks`, and `document_chunks` retrieval columns exist on startup.

### 1.2 Configurable embedding provider (`app/ai/embeddings.py`)

- `EmbeddingProvider` ABC decoupled from `LLMProvider` (D-046):
  - `HashingEmbeddingProvider` (default offline deterministic 256-dim L2-normalised feature hashing)
  - `GeminiEmbeddingProvider` (official `google-genai` SDK with `output_dimensionality`)
  - `OpenAICompatibleEmbeddingProvider` (`/embeddings` HTTP endpoint)
  - `none` (lexical-only mode)
- Validates returned vector dimensions against `RETRIEVAL_EMBEDDING_DIM` (`256`).

### 1.3 Legal-source provider architecture (`app/services/legal_corpus.py`)

- `LegalCorpusProvider` interface with `JsonCorpusProvider` (operator-supplied JSON corpus), `FixtureCorpusProvider` (clearly labelled `[SAMPLE FIXTURE — NOT A REAL CITATION]`, `is_fixture=True`), and `NullCorpusProvider`.
- Database-backed ingested records (`legal_records` / `legal_record_chunks`) are queried alongside configured external providers.

### 1.4 Hybrid retrieval & ingestion (`app/services/retrieval/`)

- `chunking.py`: paragraph-aware deterministic chunking preserving `page_number`, `paragraph_number`, `char_start`, `char_end`, and SHA-256 `content_hash`.
- `ingestion.py`: `ingest_legal_record()` and `index_case_documents()` (case-ownership enforced).
- `hybrid.py`: PostgreSQL FTS (`ts_rank_cd`) + `pgvector` cosine distance on PostgreSQL, or deterministic BM25 + cosine similarity on SQLite; combined via Reciprocal Rank Fusion (`k=60`), optional deterministic reranker (`rerank_candidates`), provenance deduplication, metadata filters (`case_id`, `source_type`, `jurisdiction`, `court`, `date_from`, `date_to`, `source_provider`), query length budget (`RETRIEVAL_MAX_QUERY_CHARS=500`), and prompt-injection signal flagging (`has_injection_signals`).
- `evaluation.py`: `recall_at_k()` and `mean_reciprocal_rank()`.

### 1.5 API & Frontend

- `apps/api/app/routers/retrieval.py`:
  - `GET /api/v1/retrieval/status`
  - `POST /api/v1/retrieval/search`
  - `POST /api/v1/retrieval/cases/{case_id}/index`
  - `POST /api/v1/retrieval/records`
  - `GET /api/v1/retrieval/records/{record_id}`
- `apps/web/src/app/(app)/research/`: Legal Research workspace with query, case scope, metadata filters, fixture/provider banner, similarity-score disclaimer, source inspection dialog, and "Send selected to Case Intelligence" flow (passing `caseId`, `docIds`, and `focus` to `/intelligence`).

---

## 2. Environment variables

New Stage 7 variables (all documented in `.env.example`):

- `EMBEDDING_PROVIDER` (`hashing` | `gemini` | `openai` | `openai_compatible` | `none`)
- `EMBEDDING_MODEL`, `EMBEDDING_API_KEY`, `EMBEDDING_BASE_URL`, `EMBEDDING_TIMEOUT_S`
- `RETRIEVAL_EMBEDDINGS_ENABLED` (`true`), `RETRIEVAL_EMBEDDING_DIM` (`256`)
- `RETRIEVAL_MAX_CANDIDATES` (`400`), `RETRIEVAL_DEFAULT_LIMIT` (`10`), `RETRIEVAL_MAX_LIMIT` (`50`), `RETRIEVAL_MAX_QUERY_CHARS` (`500`)
- `RETRIEVAL_RRF_K` (`60`), `RETRIEVAL_LEXICAL_WEIGHT` (`0.5`), `RETRIEVAL_SEMANTIC_WEIGHT` (`0.5`), `RETRIEVAL_RERANK_ENABLED` (`true`)
- `LEGAL_CORPUS_PROVIDER` (`none` | `json` | `fixture`), `LEGAL_CORPUS_PATH`

---

## 3. Known limitations

1. **PostgreSQL `pgvector` / `tsvector` SQL path not executed against a live PostgreSQL server in this environment** — migration `005` was verified end-to-end on SQLite, and the SQLite BM25 + cosine fallback was exercised by all integration/evaluation tests. Run `alembic upgrade head` against PostgreSQL with `pgvector` installed on deployment.
2. **External embedding APIs (`gemini`, `openai`)** were not called live in tests; `HashingEmbeddingProvider` and dimension-validation error paths are covered deterministically.
3. **No paid legal database is bundled** — `LEGAL_CORPUS_PROVIDER=none` uses `FixtureCorpusProvider` with `is_fixture=True` labels.
4. **Stage 8+ modules** (`Contradiction & Gap Hunter`, `Precedent Explorer`, `Advocate Mode`, `Judge/Clerk Mode`) remain unwired future work.

---

## 4. Next-stage prerequisites (Stage 8 — Contradiction & Gap Hunter)

- [ ] Run `alembic upgrade head` against PostgreSQL with `pgvector` enabled.
- [ ] Reuse `hybrid_search` / `document_chunks` retrieval tools inside the Stage 8 Contradiction & Gap Hunter LangGraph workflow to compare claims across documents with preserved `document_id` + `page_number`.
- [ ] Keep all future-stage placeholder pages honestly labelled until each module is wired and tested.

---

## 5. Ready-to-paste continuation prompt (Stage 8)

```text
You are continuing the NyayaSaar project after Stage 7 Hybrid Legal Retrieval.

Read first:
- docs/stage-handoffs/stage-7.md
- docs/implementation-status.md
- docs/decisions.md (especially D-036 to D-047)
- apps/api/app/services/retrieval/{hybrid,ingestion,chunking}.py
- apps/api/app/services/legal_corpus.py
- apps/api/app/agents/{graph,state,schemas}.py
- apps/api/app/services/analysis.py

Stage 7 Hybrid Legal Retrieval is complete (migration 005 with pgvector + FTS
and SQLite fallback, EmbeddingProvider abstraction, LegalCorpusProvider with
honest fixture labelling, RRF hybrid search + filters + reranker, /api/v1/retrieval/*
endpoints, Legal Research UI, and Recall@K evaluation tests).

Implement Stage 8 — Contradiction & Gap Hunter only:
1. Build a bounded, stateful LangGraph workflow for cross-document contradiction
   detection, timeline conflict detection, missing-evidence gaps, and
   unsupported assertions, reusing Stage 7 hybrid retrieval and Stage 6
   deterministic source/quote verification.
2. Preserve document_id, page_number, and verified quote spans for every
   finding; never fabricate conflicts or legal authorities.
3. Wire the `contradiction` workflow type in `app/services/analysis.py`,
   `app/routers/analysis.py`, and `app/services/report.py` (HTML/Markdown export).
4. Replace the `/contradictions` placeholder page with a live, case-scoped
   Contradiction & Gap Hunter workspace (keeping `/precedents`, `/advocate`,
   and `/judge` honestly marked as future work).
5. Add deterministic mocked tests (valid/invalid output, provider errors,
   cross-user auth, quote verification, prompt-injection resistance) and
   update docs + docs/stage-handoffs/stage-8.md.
```
