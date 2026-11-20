/**
 * Analysis API — typed wrappers around Stage 5 case-analysis workflows.
 *
 * Long-running work is queued server-side; clients poll the run endpoint.
 * Provider keys never reach the browser. Results are AI-assisted and must be
 * independently verified by a legal professional.
 */
import { apiClient } from "@/lib/api-client";
import type {
  AIStatus,
  CaseAnalysisRequest,
  CaseAnalysisResult,
  WorkflowRun,
  WorkflowRunListResponse,
  WorkflowStatus,
} from "@nyayasaar/shared";

export function startCaseAnalysis(
  caseId: string,
  input: CaseAnalysisRequest = {},
) {
  return apiClient.post<WorkflowRun>(
    `/api/v1/cases/${caseId}/analysis`,
    input,
  );
}

export function listCaseAnalyses(caseId: string, limit = 20) {
  return apiClient.get<WorkflowRunListResponse>(
    `/api/v1/cases/${caseId}/analysis`,
    { params: { limit } },
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
