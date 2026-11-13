/**
 * Auth API — registration, login, and session profile.
 *
 * The FastAPI backend is the single source of authentication truth.
 * Tokens are JWT bearer tokens issued by POST /api/v1/auth/register|login.
 */
import { apiClient } from "@/lib/api-client";
import type { TokenResponse, User } from "@nyayasaar/shared";

const AUTH_TOKEN_STORAGE_KEY = "nyayasaar.auth.token";

export function loadStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function storeToken(token: string | null) {
  if (typeof window === "undefined") return;
  try {
    if (token) {
      window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
    } else {
      window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
    }
  } catch {
    // Storage unavailable (private mode) — session simply won't persist.
  }
}

export function register(email: string, password: string, fullName?: string) {
  return apiClient.post<TokenResponse>(
    "/api/v1/auth/register",
    {
      email,
      password,
      full_name: fullName || undefined,
    },
  );
}

export function login(email: string, password: string) {
  return apiClient.post<TokenResponse>("/api/v1/auth/login", { email, password });
}

export function fetchMe() {
  return apiClient.get<User>("/api/v1/auth/me");
}
