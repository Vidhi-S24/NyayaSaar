/**
 * Health API — typed queries for the /api/v1/health and /api/v1/ready endpoints.
 */
import type { ApiResponse, HealthResponse } from "@nyayasaar/shared";
import { apiClient } from "@/lib/api-client";

export async function fetchHealth(): Promise<ApiResponse<HealthResponse>> {
  return apiClient.get<ApiResponse<HealthResponse>>("/api/v1/health");
}

export async function fetchReadiness(): Promise<ApiResponse<HealthResponse>> {
  return apiClient.get<ApiResponse<HealthResponse>>("/api/v1/ready");
}
