/**
 * @nyayasaar/shared
 *
 * Shared TypeScript types and constants used by both the web frontend
 * and any TypeScript tooling in the monorepo. Keep this package
 * dependency-free (no runtime imports outside stdlib).
 */

// ---------------------------------------------------------------------------
// API response envelope
// ---------------------------------------------------------------------------

export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: ApiError;
  meta?: Record<string, unknown>;
}

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Health / readiness
// ---------------------------------------------------------------------------

export interface HealthResponse {
  status: "ok" | "degraded" | "error";
  version: string;
  timestamp: string;
  services: Record<string, ServiceHealth>;
}

export interface ServiceHealth {
  status: "ok" | "degraded" | "unavailable";
  latency_ms?: number;
  message?: string;
}

// ---------------------------------------------------------------------------
// Cases
// ---------------------------------------------------------------------------

export type CaseStatus = "active" | "review" | "closed" | "archived";

export type CasePriority = "high" | "medium" | "low";

export interface CaseSummary {
  id: string;
  owner_id: string;
  title: string;
  case_number: string | null;
  court: string | null;
  jurisdiction: string | null;
  status: CaseStatus;
  priority: CasePriority;
  documents_count: number;
  created_at: string;
  updated_at: string;
}

export interface Case extends CaseSummary {
  summary: string | null;
  tags: string[];
  issues: string[];
}

export interface CaseListResponse {
  items: Case[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

export interface CaseCreateInput {
  title: string;
  case_number?: string | null;
  court?: string | null;
  jurisdiction?: string | null;
  status?: CaseStatus;
  priority?: CasePriority;
  summary?: string | null;
  tags?: string[];
  issues?: string[];
}

export interface CaseUpdateInput extends Partial<CaseCreateInput> {}

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_verified: boolean;
  role: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

// ---------------------------------------------------------------------------
// Documents
// ---------------------------------------------------------------------------

export type DocumentStatus =
  | "pending"
  | "processing"
  | "ready"
  | "failed";

export type DocumentType =
  | "petition"
  | "affidavit"
  | "judgment"
  | "order"
  | "statute"
  | "contract"
  | "other";

export interface DocumentSummary {
  id: string;
  case_id: string;
  name: string;
  type: DocumentType;
  status: DocumentStatus;
  page_count?: number;
  uploaded_at: string;
}

// ---------------------------------------------------------------------------
// Workflow / agent execution
// ---------------------------------------------------------------------------

export type WorkflowStatus =
  | "queued"
  | "running"
  | "paused"
  | "completed"
  | "failed"
  | "cancelled";

export interface WorkflowRun {
  id: string;
  case_id: string;
  workflow_type: string;
  status: WorkflowStatus;
  started_at?: string;
  completed_at?: string;
  progress?: number;        // 0–100
  current_step?: string;
  error?: string;
}

// ---------------------------------------------------------------------------
// Analysis results
// ---------------------------------------------------------------------------

/** A sourced claim: any assertion that must be traceable to a source. */
export interface SourcedClaim {
  content: string;
  source_id: string;
  source_name: string;
  page?: number;
  confidence: "high" | "medium" | "low" | "unverified";
  is_model_inference: boolean;
}

/** A legal authority reference returned by the research agent. */
export interface LegalAuthority {
  id: string;
  title: string;
  citation: string;
  court?: string;
  year?: number;
  summary?: string;
  relevance_score?: number;
  source_provider: string;        // e.g. "fixture", "indian_kanoon", "custom"
  url?: string;
}

// ---------------------------------------------------------------------------
// Pagination
// ---------------------------------------------------------------------------

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const API_VERSION = "v1" as const;
export const MAX_UPLOAD_SIZE_MB = 50 as const;
export const SUPPORTED_DOCUMENT_TYPES = [
  "application/pdf",
  "application/msword",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "text/plain",
] as const;

