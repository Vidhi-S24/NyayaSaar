/**
 * Cases API — typed wrappers around /api/v1/cases.
 *
 * All calls require a bearer token (injected by the api-client).
 * Authorization is enforced server-side; the frontend merely reflects it.
 */
import { apiClient } from "@/lib/api-client";
import type {
  Case,
  CaseCreateInput,
  CaseListResponse,
  CaseUpdateInput,
  User,
} from "@nyayasaar/shared";

export interface CaseListParams {
  page?: number;
  page_size?: number;
  search?: string;
  status?: string;
}

export function listCases(params: CaseListParams = {}) {
  return apiClient.get<CaseListResponse>("/api/v1/cases", {
    params: {
      page: params.page,
      page_size: params.page_size,
      search: params.search || undefined,
      status: params.status || undefined,
    },
  });
}

export function getCase(caseId: string) {
  return apiClient.get<Case>(`/api/v1/cases/${caseId}`);
}

export function createCase(input: CaseCreateInput) {
  return apiClient.post<Case>("/api/v1/cases", input);
}

export function updateCase(caseId: string, input: CaseUpdateInput) {
  return apiClient.patch<Case>(`/api/v1/cases/${caseId}`, input);
}

export function deleteCase(caseId: string) {
  return apiClient.delete<null>(`/api/v1/cases/${caseId}`);
}

// ---------------------------------------------------------------------------
// View helpers (pure functions — testable)
// ---------------------------------------------------------------------------

export function userInitials(user: Pick<User, "full_name" | "email">): string {
  const name = user.full_name?.trim();
  if (name) {
    const parts = name.split(/\s+/).filter(Boolean);
    const first = parts[0]?.[0] ?? "";
    const last = parts.length > 1 ? parts[parts.length - 1][0] : "";
    return (first + last).toUpperCase() || "?";
  }
  return user.email.slice(0, 2).toUpperCase() || "?";
}

export function formatRelativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const diff = Date.now() - then;
  const minutes = Math.round(diff / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}
