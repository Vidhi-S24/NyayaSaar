/**
 * Hybrid Legal Retrieval API client (Stage 7).
 */
import { apiClient } from "@/lib/api-client";
import type {
  CaseIndexResponse,
  RetrievalSearchRequest,
  RetrievalSearchResponse,
  RetrievalStatus,
} from "@nyayasaar/shared";

export function getRetrievalStatus() {
  return apiClient.get<RetrievalStatus>("/api/v1/retrieval/status");
}

export function searchLegalRetrieval(input: RetrievalSearchRequest) {
  return apiClient.post<RetrievalSearchResponse>(
    "/api/v1/retrieval/search",
    input,
  );
}

export function indexCaseForRetrieval(caseId: string, force = false) {
  return apiClient.post<CaseIndexResponse>(
    `/api/v1/retrieval/cases/${caseId}/index`,
    {},
    { params: { force } },
  );
}
