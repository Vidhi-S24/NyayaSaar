import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  apiClient,
  ApiClientError,
  setApiAuthToken,
  setUnauthorizedHandler,
  type ApiEnvelope,
} from "@/lib/api-client";

const fetchMock = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockClear();
  setApiAuthToken(null);
  setUnauthorizedHandler(null);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function jsonResponse(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  };
}

describe("apiClient envelope contract", () => {
  it("returns the FULL envelope (not just data) so callers can use .data", async () => {
    // Regression: request() used to unwrap the envelope, leaving callers'
    // `envelope.data` undefined ("cannot read properties of undefined").
    fetchMock.mockResolvedValueOnce(
      jsonResponse(200, {
        success: true,
        data: { access_token: "tok_123", token_type: "bearer", expires_in: 1800 },
      }),
    );

    const envelope = await apiClient.post<{ access_token: string }>(
      "/api/v1/auth/login",
      { email: "a@b.c", password: "pw" },
    );

    expect(envelope.success).toBe(true);
    expect(envelope.data?.access_token).toBe("tok_123");
  });

  it("throws ApiClientError with the server message on success:false bodies", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(200, {
        success: false,
        data: null,
        error: { code: "x", message: "Something failed" },
      }),
    );

    await expect(apiClient.get("/api/v1/whatever")).rejects.toMatchObject({
      name: "ApiClientError",
      message: "Something failed",
    });
  });

  it("throws ApiClientError on HTTP errors (401) and fires the unauthorized handler", async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    fetchMock.mockResolvedValueOnce(
      jsonResponse(401, { detail: "Not authenticated" }),
    );

    await expect(apiClient.get("/api/v1/auth/me")).rejects.toBeInstanceOf(
      ApiClientError,
    );
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("injects the Authorization header when a token is set", async () => {
    setApiAuthToken("tok_abc");
    fetchMock.mockResolvedValueOnce(
      jsonResponse(200, { success: true, data: { id: "u1" } } as ApiEnvelope<{ id: string }>),
    );

    await apiClient.get("/api/v1/auth/me");

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer tok_abc");
  });

  it("rejects non-envelope 200 bodies instead of faking success", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { detail: "weird" }));

    await expect(apiClient.get("/api/v1/whatever")).rejects.toMatchObject({
      code: "invalid_response",
    });
  });
});
