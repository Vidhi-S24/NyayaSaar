/**
 * API client — thin wrapper around fetch for the NyayaSaar backend.
 *
 * Uses NEXT_PUBLIC_API_BASE_URL (set at build/runtime via Vercel env vars).
 * Defaults to localhost:8000 for local development.
 *
 * All server secrets stay in the FastAPI backend; this client only touches
 * public endpoints and authenticated session endpoints.
 */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export interface FetchOptions extends RequestInit {
  /** Query parameters to append to the URL */
  params?: Record<string, string | number | boolean | undefined>;
}

class ApiClientError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code?: string,
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

// ---------------------------------------------------------------------------
// Auth token (set by the AuthProvider after sign-in; bearer header injection)
// ---------------------------------------------------------------------------

let authToken: string | null = null;
let unauthorizedHandler: (() => void) | null = null;

export function setApiAuthToken(token: string | null) {
  authToken = token;
}

export function getApiAuthToken(): string | null {
  return authToken;
}

/** Registers a callback fired when any API call returns 401 Unauthorized. */
export function setUnauthorizedHandler(handler: (() => void) | null) {
  unauthorizedHandler = handler;
}

/** Standard backend envelope: { success, data, error }. */
export interface ApiEnvelope<T> {
  success: boolean;
  data?: T;
  error?: { code: string; message: string; details?: Record<string, unknown> };
}

/**
 * Validates an envelope-shaped response body and returns it whole.
 * Callers access `.data`; a `success: false` body throws ApiClientError.
 */
function asEnvelope<T>(body: unknown, status: number): ApiEnvelope<T> {
  const envelope = body as ApiEnvelope<T>;
  if (!envelope.success) {
    throw new ApiClientError(
      envelope.error?.message ?? "Request failed",
      status,
      envelope.error?.code ?? "request_failed",
    );
  }
  return envelope;
}

async function request<T>(
  path: string,
  options: FetchOptions = {},
): Promise<ApiEnvelope<T>> {
  const { params, ...fetchOptions } = options;

  let url = `${API_BASE_URL}${path}`;
  if (params) {
    const qs = new URLSearchParams(
      Object.entries(params)
        .filter(([, v]) => v !== undefined)
        .map(([k, v]) => [k, String(v)]),
    ).toString();
    if (qs) url += `?${qs}`;
  }

  const res = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
      ...fetchOptions.headers,
    },
    ...fetchOptions,
  });

  const body = await res.json().catch(() => null);

  if (res.status === 401 && unauthorizedHandler) {
    unauthorizedHandler();
  }

  if (!res.ok) {
    const message =
      body?.error?.message ?? body?.detail ?? `HTTP ${res.status}`;
    const code = body?.error?.code ?? "request_failed";
    throw new ApiClientError(message, res.status, code);
  }

  // FastAPI validation errors (422) return a plain detail list, not the envelope.
  if (body && typeof body === "object" && "success" in body) {
    return asEnvelope<T>(body, res.status);
  }
  // A 200 response without the standard envelope is a contract violation —
  // surface it instead of pretending it succeeded.
  throw new ApiClientError(
    "Unexpected response shape from the API (missing envelope)",
    res.status,
    "invalid_response",
  );
}

// ---------------------------------------------------------------------------
// Typed API methods
//
// T is the *payload* type; every method resolves to the full envelope
// (ApiEnvelope<T>) so callers consistently use `.data`.
// ---------------------------------------------------------------------------

export const apiClient = {
  get: <T>(path: string, options?: FetchOptions) =>
    request<T>(path, { ...options, method: "GET" }),

  post: <T>(path: string, body?: unknown, options?: FetchOptions) =>
    request<T>(path, {
      ...options,
      method: "POST",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),

  put: <T>(path: string, body?: unknown, options?: FetchOptions) =>
    request<T>(path, {
      ...options,
      method: "PUT",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),

  patch: <T>(path: string, body?: unknown, options?: FetchOptions) =>
    request<T>(path, {
      ...options,
      method: "PATCH",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),

  delete: <T>(path: string, options?: FetchOptions) =>
    request<T>(path, { ...options, method: "DELETE" }),

  /**
   * Upload a FormData payload (file upload).
   * Does NOT set Content-Type — the browser must set it with the multipart
   * boundary. The auth token is still injected.
   */
  upload: <T>(path: string, formData: FormData, options?: FetchOptions) => {
    const { params, ...rest } = options ?? {};
    let url = `${API_BASE_URL}${path}`;
    if (params) {
      const qs = new URLSearchParams(
        Object.entries(params)
          .filter(([, v]) => v !== undefined)
          .map(([k, v]) => [k, String(v)]),
      ).toString();
      if (qs) url += `?${qs}`;
    }
    // We bypass the shared request() helper so we can skip Content-Type
    return (async (): Promise<ApiEnvelope<T>> => {
      const res = await fetch(url, {
        method: "POST",
        headers: {
          ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
        },
        body: formData,
        ...rest,
      });
      const body = await res.json().catch(() => null);
      if (res.status === 401 && unauthorizedHandler) {
        unauthorizedHandler();
      }
      if (!res.ok) {
        const message =
          body?.error?.message ?? body?.detail ?? `HTTP ${res.status}`;
        const code = body?.error?.code ?? "request_failed";
        throw new ApiClientError(message, res.status, code);
      }
      if (body && typeof body === "object" && "success" in body) {
        return asEnvelope<T>(body, res.status);
      }
      throw new ApiClientError(
        "Unexpected response shape from the API (missing envelope)",
        res.status,
        "invalid_response",
      );
    })();
  },
};

export { ApiClientError };

