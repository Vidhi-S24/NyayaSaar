/**
 * Health API — typed queries for the /api/v1/health and /api/v1/ready endpoints.
 */
import type { HealthResponse } from "@nyayasaar/shared";
import { apiClient, type ApiEnvelope } from "@/lib/api-client";

export async function fetchHealth(): Promise<ApiEnvelope<HealthResponse>> {
  return apiClient.get<HealthResponse>("/api/v1/health");
}

export async function fetchReadiness(): Promise<ApiEnvelope<HealthResponse>> {
  return apiClient.get<HealthResponse>("/api/v1/ready");
}

