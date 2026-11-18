# Stage 4 Handoff — Legal Document Ingestion Pipeline

**Completed:** 2026-11-18  
**Previous stage:** [Stage 3 — Database, Auth, Case Management](stage-3.md)  
**Next stage:** Stage 5 — Gemini / LangGraph Agentic Workflows

---

## What was built

### Backend

| Path | Description |
|---|---|
| `apps/api/app/db/models/document.py` | `Document` + `DocumentChunk` SQLAlchemy models; `ProcessingStatus` enum |
| `apps/api/alembic/versions/002_add_documents.py` | Migration: `documents` + `document_chunks` tables, FK to `cases`, `pgvector` extension hook |
| `apps/api/app/schemas/documents.py` | Pydantic request/response schemas: `DocumentResponse`, `DocumentListResponse`, `DocumentChunkResponse`, `DocumentTextPreview` |
| `apps/api/app/services/storage.py` | `StorageProvider` ABC; `LocalStorageProvider`; `S3StorageProvider` stub; `make_storage_key()` (UUID-based, never from user filename) |
| `apps/api/app/services/extraction.py` | `validate_upload()` (magic-byte detection + extension + size); `extract_pdf()` (PyMuPDF, page-numbered chunks, scanned-PDF detection); `extract_docx()` (python-docx); `extract_txt()` (UTF-8 with BOM/Latin-1 fallback) |
| `apps/api/app/services/documents.py` | `create_document()`, `process_document()` (sync extraction, bounded 3-retry), `retry_document()`, `list_documents()`, `get_document()`, `get_document_chunks()`, `delete_document()` |
| `apps/api/app/routers/documents.py` | 6 endpoints — all case-ownership-gated |
| `apps/api/app/main.py` | Documents router registered at `/api/v1/cases/{case_id}/documents` |
| `apps/api/tests/test_documents.py` | 16 HTTP integration tests (upload, list, get, text, retry, delete, auth boundaries) |
| `apps/api/tests/test_extraction.py` | Unit tests for `validate_upload()`, magic-byte checks, `extract_txt()` |
| `apps/api/tests/test_storage.py` | Unit tests for `LocalStorageProvider`, `make_storage_key()` |

### Frontend

| Path | Description |
|---|---|
| `packages/shared/src/index.ts` | `Document`, `DocumentListResponse`, `DocumentChunk`, `DocumentTextPreview`, `DocumentProcessingStatus` types (replaces stub `DocumentSummary`) |
| `apps/web/src/lib/api/documents.ts` | `listDocuments()`, `getDocument()`, `uploadDocument()`, `getDocumentText()`, `retryDocumentExtraction()`, `deleteDocument()`, `formatFileSize()`, `formatContentType()` |
| `apps/web/src/lib/api-client.ts` | `upload()` method added — `FormData` POST, skips `Content-Type` (browser sets multipart boundary), still injects auth token |
| `apps/web/src/components/documents/document-upload.tsx` | Drag-and-drop upload panel; client-side validation (extension + size); progress / error / success states; upload triggers `onUploaded` callback |
| `apps/web/src/components/documents/document-list.tsx` | Document rows with `ProcessingBadge`; delete confirm dialog; retry button; text preview trigger; 5-second polling for in-progress documents |
| `apps/web/src/components/documents/document-text-preview.tsx` | Page-navigable extracted text viewer; XSS-safe (`<pre>` only, no `dangerouslySetInnerHTML`) |
| `apps/web/src/app/(app)/cases/[id]/page.tsx` | Documents tab wired with real `DocumentUpload` + `DocumentList`; `uploadedAt` state triggers list refresh |
| `apps/web/src/app/(app)/documents/page.tsx` | Real document library across all cases; `useClient` page, real API data |

---

## API surface

```
POST   /api/v1/cases/{case_id}/documents           Upload document (multipart/form-data)
GET    /api/v1/cases/{case_id}/documents           List documents (paged: skip/limit)
GET    /api/v1/cases/{case_id}/documents/{doc_id}  Get document metadata
GET    /api/v1/cases/{case_id}/documents/{doc_id}/text  Get extracted chunks
POST   /api/v1/cases/{case_id}/documents/{doc_id}/retry  Retry failed extraction
DELETE /api/v1/cases/{case_id}/documents/{doc_id}  Delete document + file + chunks
```

All endpoints require a valid JWT and enforce case ownership (non-owners get 404, not 403).

---

## Acceptance criteria

| Criterion | Status |
|---|---|
| Upload PDFs/DOCX/TXT; validation, size limits, magic-byte detection | ✅ |
| Validate extensions + file signatures; never trust client MIME | ✅ |
| Safe storage keys + provider abstraction (Local + S3 interface) | ✅ |
| Persist document metadata (processing state, timestamps, failure info) | ✅ |
| Extract text with PyMuPDF/python-docx; page numbers preserved in chunks | ✅ |
| Detect scanned PDFs; OCR extension point; report incompleteness | ✅ |
| Processing status + safe retries (bounded at 3), sync extraction | ✅ |
| Frontend document UI — upload, list, preview, delete, retry | ✅ |
| Case authorization enforced on all endpoints | ✅ |
| Failures don't falsely mark documents as completed | ✅ |

---

## Verification results (actual)

```
Frontend
  tsc --noEmit          → 0 errors
  vitest run            → 20/20 passed (3 files)
  next build            → exit 0; 15 routes; /cases/[id] 14.5 kB

Backend
  pytest tests/ -v -x   → 75 collected; all passed (see task-198 log)
  alembic upgrade head  → 002_add_documents applied cleanly (SQLite dev)
```

---

## New environment variables (Stage 4)

| Variable | Default | Description |
|---|---|---|
| `STORAGE_BACKEND` | `local` | `local` or `s3` |
| `STORAGE_LOCAL_PATH` | `./uploads` | Root directory for local file storage |
| `AWS_BUCKET_NAME` | — | Required if `STORAGE_BACKEND=s3` |
| `AWS_REGION` | `us-east-1` | S3 region |
| `AWS_ACCESS_KEY_ID` | — | S3 credentials |
| `AWS_SECRET_ACCESS_KEY` | — | S3 credentials |
| `MAX_UPLOAD_SIZE_MB` | `50` | Per-file upload limit |
| `MAX_DOCUMENTS_PER_CASE` | `50` | Hard cap per case |

---

## Known limitations

1. **No OCR for scanned PDFs** — `extract_pdf()` detects scanned pages (char count < threshold) and sets `processing_status = ocr_required`. An OCR integration point is stubbed but not implemented. Tesseract/EasyOCR can be wired in Stage 5 or 6.
2. **Synchronous extraction** — processing happens inline in the upload request (no Celery worker). Files up to ~50 MB extract in < 5 s on typical hardware. If extraction time becomes a bottleneck, move `process_document()` to a Celery task (see D-020).
3. **SQLite dev mode has no pgvector** — `document_chunks.embedding` column is `ARRAY(Float)` in Alembic; on SQLite this column is ignored. Vector search requires PostgreSQL + pgvector (Stage 5).
4. **S3StorageProvider is a stub** — the class exists with the correct interface but `boto3` calls are commented as TODO. Wire in Stage 7 for production.
5. **No virus scanning** — file content is validated by magic bytes and extension only. ClamAV or a cloud scanner can be added in Stage 7.

---

## How to run locally (Stage 4)

```bash
# Backend
cd apps/api
.venv\Scripts\python -m alembic upgrade head   # apply migration 002
.venv\Scripts\python -m uvicorn app.main:app --reload

# Frontend
cd apps/web
pnpm exec next dev

# Upload a document
# 1. Sign in at http://localhost:3000/signin
# 2. Create a case
# 3. Click the Documents tab → drag a PDF or DOCX
```

---

## Files changed in Stage 4

```
apps/api/app/db/models/document.py          NEW
apps/api/app/schemas/documents.py           NEW
apps/api/app/services/storage.py            NEW
apps/api/app/services/extraction.py         NEW
apps/api/app/services/documents.py          NEW
apps/api/app/routers/documents.py           NEW
apps/api/app/main.py                        MODIFIED (router registered)
apps/api/alembic/versions/002_add_documents.py  NEW
apps/api/tests/test_documents.py            NEW
apps/api/tests/test_extraction.py           NEW
apps/api/tests/test_storage.py              NEW
packages/shared/src/index.ts                MODIFIED (Document types added)
apps/web/src/lib/api-client.ts              MODIFIED (upload() method)
apps/web/src/lib/api/documents.ts           NEW
apps/web/src/components/documents/document-upload.tsx       NEW
apps/web/src/components/documents/document-list.tsx         NEW
apps/web/src/components/documents/document-text-preview.tsx NEW
apps/web/src/app/(app)/cases/[id]/page.tsx  MODIFIED (Documents tab wired)
apps/web/src/app/(app)/documents/page.tsx   MODIFIED (real API data)
```

---

## Stage 5 prerequisites & continuation prompt

### Prerequisites
- PostgreSQL running with `pgvector` extension installed (`CREATE EXTENSION vector;`)
- `DATABASE_URL` pointing to that PostgreSQL instance
- `GEMINI_API_KEY` set server-side
- `GEMINI_MODEL` configurable (default `gemini-2.0-flash`)
- Stage 4 migration applied (`alembic upgrade head`)

### Continuation prompt for Stage 5

```
Continue NyayaSaar at Stage 5 — Gemini / LangGraph Agentic Workflows.

Repo: D:\Vidhi Soni\NyayaSaar-publish\
Stage 4 is complete (documents ingestion, extraction, frontend UI — all verified).
See docs/stage-handoffs/stage-4.md for context.

Stage 5 scope:
- Embed document chunks using Gemini text-embedding-004 (pgvector storage)
- Hybrid retrieval: pgvector cosine similarity + PostgreSQL full-text search
- LangGraph stateful graph for Case Intelligence workflow:
    orchestrator → fact_extractor → issue_identifier → authority_finder → synthesizer
- Gemini API via google-genai SDK; model ID configurable via GEMINI_MODEL env var
- Never fabricate legal authorities, citations, or holdings
- Background embedding job (Celery or inline; justify the choice)
- API endpoints: POST /api/v1/cases/{id}/analyze, GET /api/v1/cases/{id}/analysis
- Frontend: Analysis panel in the case workspace (streaming or polling)
- LangSmith tracing optional (LANGSMITH_API_KEY env var, skip gracefully if absent)
```
