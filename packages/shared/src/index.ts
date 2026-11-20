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
// Documents — Stage 4 (backed by /api/v1/cases/{case_id}/documents)
// ---------------------------------------------------------------------------

export type DocumentProcessingStatus =
  | "pending"
  | "processing"
  | "ready"
  | "failed";

/** Matches the DocumentResponse Pydantic schema in apps/api/app/schemas/documents.py */
export interface Document {
  id: string;
  case_id: string;
  original_name: string;
  content_type: string;
  file_size: number;
  processing_status: DocumentProcessingStatus;
  page_count: number | null;
  is_ocr_required: boolean;
  extraction_completeness: number | null;
  failure_reason: string | null;
  retry_count: number;
  created_at: string;
  updated_at: string;
  processing_started_at: string | null;
  processing_completed_at: string | null;
}

export interface DocumentListResponse {
  items: Document[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

/** A single extracted page/chunk returned by the /text endpoint */
export interface DocumentChunk {
  id: string;
  document_id: string;
  page_number: number;
  extracted_text: string;
  char_count: number;
  created_at: string;
}

export interface DocumentTextPreview {
  document_id: string;
  total_pages: number;
  chunks: DocumentChunk[];
  is_partial: boolean;
}

// Legacy alias kept for backward compatibility in demo-data references
/** @deprecated Use Document instead */
export type DocumentStatus = DocumentProcessingStatus;

// ---------------------------------------------------------------------------
// Workflow / agent execution — Stage 5 (case-analysis workflows)
// ---------------------------------------------------------------------------

export type WorkflowStatus = "queued" | "running" | "completed" | "failed";

export type WorkflowStepStatus = "queued" | "running" | "completed" | "failed";

export interface WorkflowStep {
  step: string;
  status: WorkflowStepStatus | string;
  message?: string | null;
  at?: string | null;
}

export interface WorkflowError {
  code: string;
  message: string;
}

export type AnalysisSupport =
  | "supported"
  | "partially_supported"
  | "unsupported";

export type AnalysisConfidence = "high" | "medium" | "low";

export type AnalysisClaimType = "fact" | "legal_issue" | "inference";

/** A verified reference to an exact document page supplied to the analyst. */
export interface AnalysisSourceRef {
  source_id: string;
  document_id: string;
  document_name: string;
  page_number: number;
  quote: string | null;
  quote_verified: boolean;
}

export interface AnalysisClaim {
  claim: string;
  claim_type: AnalysisClaimType;
  sources: AnalysisSourceRef[];
  support: AnalysisSupport;
  confidence: AnalysisConfidence;
}

export interface AnalysisTimelineEvent {
  date_text: string;
  event: string;
  sources: AnalysisSourceRef[];
  support: AnalysisSupport;
}

export interface AnalysisVerificationSummary {
  total_claims: number;
  supported: number;
  partially_supported: number;
  unsupported: number;
  invalid_source_refs: number;
  retried: boolean;
  notes: string[];
}

export interface AnalysisSourceManifestEntry {
  source_id: string;
  document_id: string;
  document_name: string;
  page_number: number;
  truncated: boolean;
}

/** Structured, source-linked analysis. AI-assisted, never legal advice. */
export interface CaseAnalysisResult {
  workflow_id: string;
  case_id: string;
  generated_at: string;
  provider: string;
  model: string;
  is_mock: boolean;
  insufficient_sources: boolean;
  summary: string;
  parties: string[];
  facts: AnalysisClaim[];
  legal_issues: AnalysisClaim[];
  timeline: AnalysisTimelineEvent[];
  inferences: AnalysisClaim[];
  unverified_hypotheses: string[];
  missing_information: string[];
  limitations: string[];
  verification: AnalysisVerificationSummary;
  source_manifest: AnalysisSourceManifestEntry[];
}

export interface WorkflowRun {
  id: string;
  case_id: string;
  workflow_type: string;
  status: WorkflowStatus;
  progress: number;
  current_step: string | null;
  provider: string | null;
  model: string | null;
  is_mock: boolean;
  document_ids: string[];
  focus: string | null;
  result: CaseAnalysisResult | null;
  steps: WorkflowStep[];
  token_usage: Record<string, number>;
  error: WorkflowError | null;
  attempt_count: number;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface WorkflowRunListResponse {
  items: WorkflowRun[];
  total: number;
}

export interface CaseAnalysisRequest {
  document_ids?: string[] | null;
  focus?: string | null;
}

export interface AIStatus {
  provider: string;
  requested_provider: string;
  model: string;
  is_mock: boolean;
  configured: boolean;
  message: string;
}

// ---------------------------------------------------------------------------
// Analysis placeholders reserved for Stage 6 (not produced in Stage 5)
// ---------------------------------------------------------------------------

/** @deprecated Stage 5 uses AnalysisClaim. Reserved for Stage 6 research. */
export interface SourcedClaim {
  content: string;
  source_id: string;
  source_name: string;
  page?: number;
  confidence: "high" | "medium" | "low" | "unverified";
  is_model_inference: boolean;
}

/** Reserved for Stage 6 precedent research. No authorities are returned yet. */
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

