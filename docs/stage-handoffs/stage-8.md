# Stage 8 Handoff — Contradiction & Gap Hunter

> Completed: 2026-11-25
> Scope: Stage 8 **Contradiction & Gap Hunter** only. Precedent Explorer (Stage 9), Advocate Mode, and Judge/Clerk Mode remain future work.

---

## 1. What was delivered

### 1.1 Database & Review Audit Trail (`006_add_finding_reviews.py`)
- Added `finding_reviews` table (`apps/api/app/db/models/finding_review.py`) keyed by `(workflow_id, finding_id)` with `status` (`unreviewed | confirmed | dismissed | needs_review`), `reviewer_note`, `updated_by_user_id`, and append-only `history` JSON audit trail (`previous_status`, `new_status`, `note`, `user_id`, `user_email`, `at`).
- Added `"finding_reviews"` to SQLite dev fallback startup check in `apps/api/app/main.py`.

### 1.2 LangGraph Workflow & Deterministic Verifier
- `apps/api/app/agents/schemas_contradiction.py`: `ContradictionAnalysisDraft`, `VerifiedContradictionFinding`, `ContradictionResult` (`CONTRADICTION_WORKFLOW_VERSION = "8.0.0"`). Distinguishes `direct_contradiction`, `possible_inconsistency`, `evidence_gap`, and `unsupported_claim`, and strictly separates `observed_evidence_summary` from `model_interpretation`.
- `apps/api/app/ai/prompts/contradiction.py`: Prompt wrapping all document text and user focus in `<untrusted_document>` tags, prohibiting accusations of dishonesty/wrongdoing or fabricated authorities.
- `apps/api/app/agents/nodes/contradiction_analyst.py`: Bounded specialist node with `MockProvider` fixture support.
- `apps/api/app/agents/nodes/contradiction_verifier.py`: Deterministic `verify_contradiction_draft()` checking Side A / Side B quotes and spans, normalising timeline dates (`normalise_date_text`), flagging authority-like citation patterns, and triggering bounded revision (`AGENT_MAX_VERIFIER_RETRIES`).
- `apps/api/app/agents/graph_contradiction.py`: `orchestrator -> contradiction_analyst -> contradiction_verifier -> finalize` (with bounded revision loop and insufficient-sources handling).

### 1.3 Service, API & Report Export
- `apps/api/app/services/analysis.py`: Dispatches `workflow_type="contradiction"` (using Stage 7 `hybrid_search` to supply optional candidate passages) and implements `list_finding_reviews()` + `upsert_finding_review()`.
- `apps/api/app/routers/analysis.py` & `apps/api/app/schemas/analysis.py`:
  - `POST /api/v1/cases/{case_id}/analysis` (`workflow_type: "contradiction"`)
  - `GET /api/v1/cases/{case_id}/analysis?workflow_type=contradiction`
  - `GET /api/v1/cases/{case_id}/analysis/{workflow_id}/reviews`
  - `PATCH /api/v1/cases/{case_id}/analysis/{workflow_id}/findings/{finding_id}/review`
  - `GET /api/v1/cases/{case_id}/analysis/{workflow_id}/report?format=html|markdown`
- `apps/api/app/services/report.py`: Added `render_contradiction_report_html()` and `render_contradiction_report_markdown()` including review status and reviewer notes.

### 1.4 Frontend Workspace (`/contradictions`)
- `packages/shared/src/index.ts` & `apps/web/src/lib/api/analysis.ts`: Added Stage 8 types and review API helpers.
- `apps/web/src/components/contradictions/contradiction-panel.tsx`, `apps/web/src/app/(app)/contradictions/contradictions-client.tsx`, `apps/web/src/app/(app)/contradictions/page.tsx`:
  - Multi-document selection, partial/incomplete extraction notice, optional focus, live polling, and retry.
  - Observed Evidence vs Model Interpretation cards, side-by-side Side A / Side B source passages with source-viewer dialog and span highlighting.
  - Filters by document, category, review status, and date; severity definitions legend.
  - Review actions (`Confirm`, `Needs Review`, `Dismiss`), reviewer notes, expandable audit trail, chronological timeline, and HTML/Markdown report export.

---

## 2. Verification & Known Limitations
- **Backend unit tests:** `4 passed` in `tests/test_contradiction_hunter.py` (`-k "not audit_trail"`).
- **Alembic migration:** `001 -> 006 (head)` verified on temporary SQLite DB (`python -m alembic upgrade head`).
- **Async HTTP API test:** `test_contradiction_review_audit_trail_and_cross_user_auth` was written in `tests/test_contradiction_hunter.py`, but `@pytest.mark.asyncio` / `aiosqlite` tests hang in this Windows sandbox environment and should be executed in Linux CI.
- **No new env vars required** (reuses Stage 5/6 `AI_*` and Stage 7 `EMBEDDING_*` settings).

---

## 3. Ready-to-paste continuation prompt (Stage 9)

```text
You are continuing the NyayaSaar project after Stage 8 Contradiction & Gap Hunter.

Read first:
- docs/stage-handoffs/stage-8.md
- docs/implementation-status.md
- docs/decisions.md
- apps/api/app/services/legal_corpus.py
- apps/api/app/services/retrieval/hybrid.py
- apps/api/app/agents/graph_contradiction.py
- apps/api/app/services/analysis.py

Stage 8 Contradiction & Gap Hunter is complete (migration 006 finding_reviews
with audit trail, LangGraph contradiction workflow + deterministic verifier,
review & report endpoints, and live /contradictions workspace).

Implement Stage 9 — Precedent Explorer, Citation Relationships & Conflict Detection only:
1. Build a bounded LangGraph workflow for precedent search, citation-relationship
   exploration (optional Neo4j with graceful fallback), and conflicting-reasoning
   analysis grounded in configured legal-source providers (or clearly labelled
   fixtures when no corpus is configured).
2. Never fabricate citations, holdings, or claims of subsequent judicial treatment
   without reliable supporting data.
3. Wire `/precedents` to the live workflow (keeping `/advocate` and `/judge`
   honestly marked as future work).
4. Add deterministic mocked tests and update docs + docs/stage-handoffs/stage-9.md.
```
