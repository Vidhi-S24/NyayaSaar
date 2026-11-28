# Stage 10 Handoff — Advocate Mode & Judge/Clerk Mode

**Status:** Complete  
**Date:** 2026-11-28  
**Scope:** Stage 10 Advocate Mode & Judge/Clerk Mode only (Stage 11 = Evaluation, Security, Reliability, Accessibility, Failure Recovery, Deployment Readiness).

---

## 1. Completed Features

- **Stage 10 Schemas & Prompts (`10.0.0`):**
  - `apps/api/app/agents/schemas_stage10.py`: `AdvocateDraft`, `VerifiedAdvocateArgument` (`tier`: `strong_supported | moderate_supported | speculative`, `strength`, `supporting_sources`, `opposing_sources`, `authority_refs`, `counterarguments`, `evidentiary_gap`), `VerifiedAdvocateGap`, `AdvocateResult`, plus `JudgeDraft`, `VerifiedJudgeAuditItem` (across `issue_coverage`, `reasoning_consistency`, `source_support_audit`, `citation_integrity`, `opposing_consideration_audit`, `unresolved_questions`), and `JudgeResult` with mandatory non-authoritative disclaimers and `professional_review_required=True`.
  - `apps/api/app/ai/prompts/advocate.py` & `judge.py`: Prompts with `<untrusted_document>` wrapping, `preferred_side` emphasis without suppressing contrary material, and non-judicial-authority guardrails.
- **Bounded LangGraph Workflows & Deterministic Verifier:**
  - `apps/api/app/agents/nodes/advocate_analyst.py` & `judge_analyst.py`: Bounded analyst nodes calling the configured `LLMProvider` (`StructuredRequest(output_schema=...)`, `resp.output`) or returning clearly labelled development fixtures in mock mode.
  - `apps/api/app/agents/nodes/stage10_verifier.py`: Deterministic verifier checking `Sn` case-document refs and `Rn` retrieved corpus refs, downgrading ungrounded arguments (or arguments with only contrary material) to `tier="speculative"` / `strength="low"` / `evidentiary_gap=True`, enforcing mandatory disclaimers, and triggering bounded revision on unknown markers.
  - `apps/api/app/agents/graph_stage10.py`: `run_advocate_graph()` and `run_judge_graph()` via shared `_build_mode_graph()` helper with `insufficient_sources` handling and `ProviderError` recovery.
- **API Dispatch & Report Export:**
  - `apps/api/app/schemas/analysis.py`: Added `"advocate"` and `"judge"` to `CaseAnalysisRequest.workflow_type`, `preferred_side: Literal["both", "claimant", "respondent"]`, and `AdvocateResult | JudgeResult` to `WorkflowRunResponse.result`.
  - `apps/api/app/services/analysis.py`: Dispatches `advocate` and `judge` workflows, pre-retrieves case chunks + `LegalCorpusProvider` records, and persists version metadata.
  - `apps/api/app/services/report_stage10.py` & `apps/api/app/routers/analysis.py`: HTML-escaped print-ready report and Markdown report export for `advocate` and `judge` runs under `GET /api/v1/cases/{case_id}/analysis/{workflow_id}/report`.
- **Shared Types, API Client & Frontend Workspaces (`/advocate` & `/judge`):**
  - `packages/shared/src/index.ts`: Added `AdvocateArgumentTier`, `AdvocateStrength`, `AdvocatePreferredSide`, `AdvocateArgument`, `AdvocateGap`, `AdvocateResult`, `JudgeAuditStatus`, `JudgeAuditItem`, `JudgeResult`, and updated `WorkflowRun.result`.
  - `apps/web/src/lib/api/analysis.ts`: Added `startAdvocateAnalysis`, `listAdvocateAnalyses`, `startJudgeAnalysis`, `listJudgeAnalyses`.
  - `apps/web/src/components/shared/mode-ui.tsx`, `apps/web/src/components/advocate/advocate-panel.tsx`, `apps/web/src/app/(app)/advocate/`: Case-scoped Advocate Mode workspace with document selection, `preferred_side` selector, focus input, live progress, two-sided Claimant/Respondent argument columns, tier & support badges, evidentiary gaps, unresolved questions, source inspection modal, prominent legal-research disclaimers, and HTML/Markdown report export.
  - `apps/web/src/components/judge/judge-panel.tsx`, `apps/web/src/app/(app)/judge/`: Case-scoped Judge/Clerk Mode workspace with document selection, focus input, live progress, 6 collapsible audit sections, status/severity/opposing-considered indicators, source inspection modal, non-judicial-authority disclaimers, and HTML/Markdown report export.
  - UI & Docs Sync: Updated `dashboard/page.tsx`, `cases/[id]/page.tsx`, `intelligence/intelligence-client.tsx`, `settings/page.tsx`, `README.md`, `docs/implementation-status.md`, and `docs/decisions.md` (D-052, D-053).

---

## 2. Environment Variables / External Setup

- No new environment variables were added in Stage 10.
- Uses existing `AI_PROVIDER`, `AI_MODEL`, `AI_API_KEY`, `LEGAL_CORPUS_PROVIDER` (`none` / `fixture` / `database` / `json_file`), and optional `NEO4J_URI`.

---

## 3. Known Limitations

- Real LLM output against live Gemini was not executed in this automated handoff; deterministic tests exercise `MockProvider` / `_ScriptedProvider` and the full FastAPI HTTP + LangGraph stack.
- With the default `LEGAL_CORPUS_PROVIDER=none`, authority references use clearly labelled development fixtures (`is_fixture=True`) rather than a live legal database.
- On Windows PowerShell with restricted script execution policy, invoke `pnpm.cmd` instead of `pnpm`, and run `pytest` outside the sandbox (`BypassSandbox: true`) because Windows `asyncio.ProactorEventLoop` uses `socket.socketpair()`.

---

## 4. Next Stage

- **Stage 11 — Evaluation, Security Hardening, Reliability, Accessibility & Deployment Readiness.**

---

## 5. Verification Results (Actual)

- `cd apps/api; .\.venv\Scripts\python.exe -m pytest tests/test_stage10_modes.py -v`: **7 passed in 1.44s**.
- `cd apps/api; .\.venv\Scripts\python.exe -m pytest tests -q --ignore=tests/test_gemini_connection.py`: **189 passed in 38.58s**.
- `pnpm.cmd --filter @nyayasaar/shared type-check`: passed (exit 0).
- `pnpm.cmd --filter web type-check`: passed (exit 0).
- `pnpm.cmd --filter web lint`: passed (`No ESLint warnings or errors`).
- `pnpm.cmd --filter web test`: **5 test files, 32 tests passed**.
- `pnpm.cmd --filter web build`: **compiled and built 16/16 static/dynamic routes** including `/advocate` and `/judge`.

---

## 6. Ready-to-Paste Continuation Prompt (Stage 11)

```text
You are continuing the NyayaSaar project after Stage 10 Advocate Mode & Judge/Clerk Mode.

Read first:
- docs/stage-handoffs/stage-10.md
- docs/implementation-status.md
- docs/decisions.md
- docs/deployment.md

Stages 1–10 are complete (Case Intelligence, Hybrid Legal Retrieval, Contradiction & Gap Hunter, Precedent Explorer & Conflict Detector, Advocate Mode, and Judge/Clerk Mode are all live).

Implement Stage 11 — Evaluation, Security Hardening, Reliability, Accessibility, and Deployment Readiness:
1. Run and expand evaluation coverage (retrieval quality, grounding/verifier accuracy, workflow error/failure recovery).
2. Perform security & privacy audit (upload validation, auth/ownership boundaries, CORS, rate limits, headers, secret handling, prompt-injection defences).
3. Perform accessibility & UX polish pass across all routes (keyboard navigation, ARIA labels, focus management, contrast, error/empty/loading states).
4. Verify deployment configuration (`docs/deployment.md`, Render/Vercel commands, Alembic migrations, health/readiness probes).
5. Mandatory UI & Docs Sync (do NOT skip):
   - Ensure no stale "Planned for Stage X" labels remain anywhere in `apps/web/src/`.
   - Update `README.md`, `docs/implementation-status.md`, `docs/decisions.md`, and `docs/stage-handoffs/stage-11.md`.
6. Run full backend `pytest` (outside sandbox on Windows if `asyncio.ProactorEventLoop` `socketpair` is blocked in sandbox), `pnpm.cmd --filter @nyayasaar/shared type-check`, `pnpm.cmd --filter web type-check`, `lint`, `test`, and `build`.
```
