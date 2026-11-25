/**
 * Analysis API — typed wrappers around Stage 6 Case Intelligence workflows.
 *
 * Long-running work is queued server-side; clients poll the run endpoint.
 * Provider keys never reach the browser. Results are AI-assisted and must be
 * independently verified by a legal professional.
 */
import { apiClient, downloadRequest } from "@/lib/api-client";
import type {
  AIStatus,
  CaseAnalysisRequest,
  CaseAnalysisResult,
  ContradictionReviewStatus,
  FindingReview,
  FindingReviewListResponse,
  WorkflowRun,
  WorkflowRunListResponse,
  WorkflowStatus,
} from "@nyayasaar/shared";

export function startCaseAnalysis(
  caseId: string,
  input: CaseAnalysisRequest & { workflow_type?: "case_analysis" | "contradiction" } = {},
) {
  return apiClient.post<WorkflowRun>(
    `/api/v1/cases/${caseId}/analysis`,
    input,
  );
}

export function listCaseAnalyses(
  caseId: string,
  limit = 20,
  workflowType: "case_analysis" | "contradiction" = "case_analysis",
) {
  return apiClient.get<WorkflowRunListResponse>(
    `/api/v1/cases/${caseId}/analysis`,
    { params: { limit, workflow_type: workflowType } },
  );
}

export function listFindingReviews(caseId: string, workflowId: string) {
  return apiClient.get<FindingReviewListResponse>(
    `/api/v1/cases/${caseId}/analysis/${workflowId}/reviews`,
  );
}

export function updateFindingReview(
  caseId: string,
  workflowId: string,
  findingId: string,
  input: { status: ContradictionReviewStatus; note?: string | null },
) {
  return apiClient.patch<FindingReview>(
    `/api/v1/cases/${caseId}/analysis/${workflowId}/findings/${encodeURIComponent(findingId)}/review`,
    input,
  );
}

export function getCaseAnalysis(caseId: string, workflowId: string) {
  return apiClient.get<WorkflowRun>(
    `/api/v1/cases/${caseId}/analysis/${workflowId}`,
  );
}

export function retryCaseAnalysis(caseId: string, workflowId: string) {
  return apiClient.post<WorkflowRun>(
    `/api/v1/cases/${caseId}/analysis/${workflowId}/retry`,
    {},
  );
}

export function getAIStatus() {
  return apiClient.get<AIStatus>("/api/v1/ai/status");
}

export type ReportFormat = "html" | "markdown";

/** Download a completed report (self-contained HTML or Markdown). */
export function downloadCaseReport(
  caseId: string,
  workflowId: string,
  format: ReportFormat = "html",
) {
  return downloadRequest(
    `/api/v1/cases/${caseId}/analysis/${workflowId}/report`,
    { format },
  );
}

/** Trigger a browser download for an already-fetched report blob. */
export function saveBlob(blob: Blob, filename: string): void {
  if (typeof window === "undefined") return;
  const url = window.URL.createObjectURL(blob);
  const anchor = window.document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  window.document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// View helpers (pure, testable)
// ---------------------------------------------------------------------------

export function isWorkflowActive(status: WorkflowStatus): boolean {
  return status === "queued" || status === "running";
}

export function workflowStatusLabel(status: WorkflowStatus): string {
  switch (status) {
    case "queued":
      return "Queued";
    case "running":
      return "Analysing";
    case "completed":
      return "Completed";
    case "failed":
      return "Failed";
    default:
      return status;
  }
}

export function supportLabel(
  support: CaseAnalysisResult["facts"][number]["support"],
): string {
  switch (support) {
    case "supported":
      return "Supported by source";
    case "partially_supported":
      return "Source cited, quote unverified";
    case "unsupported":
      return "Unsupported";
    default:
      return support;
  }
}

/** True when a result came from the clearly-labelled development fixture. */
export function isFixtureResult(
  run: Pick<WorkflowRun, "is_mock"> | null | undefined,
): boolean {
  return Boolean(run?.is_mock);
}

export function verificationRate(result: CaseAnalysisResult): number {
  const total = result.verification.total_claims;
  if (!total) return 0;
  return Math.round(
    ((result.verification.supported +
      result.verification.partially_supported * 0.5) /
      total) *
      100,
  );
}

export function truncate(text: string, max = 180): string {
  const cleaned = text.trim();
  return cleaned.length > max ? `${cleaned.slice(0, max - 1)}…` : cleaned;
}
