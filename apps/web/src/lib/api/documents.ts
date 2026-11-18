/**
 * Documents API — typed wrappers around /api/v1/cases/{case_id}/documents.
 *
 * Authorization is enforced server-side. Every call requires a bearer token
 * (injected by api-client). Storage keys are never exposed to the frontend.
 *
 * Extracted text is treated as untrusted content (may contain prompt-injection
 * attempts from uploaded documents). Never eval() or dangerously set HTML.
 */
import { apiClient } from "@/lib/api-client";
import type {
  Document,
  DocumentListResponse,
  DocumentTextPreview,
} from "@nyayasaar/shared";

// ---------------------------------------------------------------------------
// List documents for a case
// ---------------------------------------------------------------------------

export interface ListDocumentsParams {
  page?: number;
  page_size?: number;
}

export function listDocuments(caseId: string, params: ListDocumentsParams = {}) {
  return apiClient.get<DocumentListResponse>(
    `/api/v1/cases/${caseId}/documents`,
    {
      params: {
        page: params.page,
        page_size: params.page_size,
      },
    },
  );
}

// ---------------------------------------------------------------------------
// Get a single document's metadata
// ---------------------------------------------------------------------------

export function getDocument(caseId: string, documentId: string) {
  return apiClient.get<Document>(
    `/api/v1/cases/${caseId}/documents/${documentId}`,
  );
}

// ---------------------------------------------------------------------------
// Upload a document to a case
// ---------------------------------------------------------------------------

export function uploadDocument(caseId: string, file: File) {
  const formData = new FormData();
  formData.append("file", file);
  return apiClient.upload<Document>(
    `/api/v1/cases/${caseId}/documents`,
    formData,
  );
}

// ---------------------------------------------------------------------------
// Get extracted text preview (page-referenced chunks)
// ---------------------------------------------------------------------------

export function getDocumentText(
  caseId: string,
  documentId: string,
  options: { page?: number; max_pages?: number } = {},
) {
  return apiClient.get<DocumentTextPreview>(
    `/api/v1/cases/${caseId}/documents/${documentId}/text`,
    {
      params: {
        page: options.page,
        max_pages: options.max_pages,
      },
    },
  );
}

// ---------------------------------------------------------------------------
// Retry failed extraction
// ---------------------------------------------------------------------------

export function retryDocumentExtraction(caseId: string, documentId: string) {
  return apiClient.post<Document>(
    `/api/v1/cases/${caseId}/documents/${documentId}/retry`,
    {},
  );
}

// ---------------------------------------------------------------------------
// Delete a document (removes file, metadata, and all chunks)
// ---------------------------------------------------------------------------

export function deleteDocument(caseId: string, documentId: string) {
  return apiClient.delete<null>(
    `/api/v1/cases/${caseId}/documents/${documentId}`,
  );
}

// ---------------------------------------------------------------------------
// View helpers
// ---------------------------------------------------------------------------

/** Human-readable file size string */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Friendly content type label */
export function formatContentType(mime: string): string {
  const map: Record<string, string> = {
    "application/pdf": "PDF",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
      "DOCX",
    "application/msword": "DOC",
    "text/plain": "TXT",
  };
  return map[mime] ?? mime.split("/").pop()?.toUpperCase() ?? "File";
}
