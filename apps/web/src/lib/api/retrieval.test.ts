import { describe, expect, it, vi, beforeEach } from "vitest";
import {
  getRetrievalStatus,
  indexCaseForRetrieval,
  searchLegalRetrieval,
} from "./retrieval";
import { apiClient } from "@/lib/api-client";

describe("retrieval API client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("fetches retrieval status", async () => {
    const spy = vi.spyOn(apiClient, "get").mockResolvedValue({
      success: true,
      data: {
        embedding_provider: "hashing",
        embedding_model: "hashing-256",
        embedding_dimensions: 256,
        embeddings_enabled: true,
        vector_backend: "sqlite_json",
        corpus_provider: "development_fixture",
        corpus_configured: false,
        fixture_active: true,
        rerank_enabled: true,
        max_query_chars: 500,
        max_limit: 50,
      },
    });

    const res = await getRetrievalStatus();
    expect(spy).toHaveBeenCalledWith("/api/v1/retrieval/status");
    expect(res.data?.fixture_active).toBe(true);
  });

  it("posts hybrid search payload", async () => {
    const spy = vi.spyOn(apiClient, "post").mockResolvedValue({
      success: true,
      data: {
        query: "limitation",
        items: [],
        total_candidates: 0,
        deduplicated_count: 0,
        retrieval_method: "bm25+cosine_rrf+rerank",
        embedding_provider: "hashing",
        embedding_model: "hashing-256",
        corpus_provider: "development_fixture",
        corpus_configured: false,
        fixture_used: false,
        reranked: false,
        notes: [],
        score_disclaimer: "Scores reflect similarity only.",
        untrusted_notice: "Untrusted text.",
      },
    });

    await searchLegalRetrieval({
      query: "limitation",
      filters: { jurisdiction: "India" },
      limit: 10,
    });
    expect(spy).toHaveBeenCalledWith("/api/v1/retrieval/search", {
      query: "limitation",
      filters: { jurisdiction: "India" },
      limit: 10,
    });
  });

  it("posts case indexing request", async () => {
    const spy = vi.spyOn(apiClient, "post").mockResolvedValue({
      success: true,
      data: {
        case_id: "c1",
        total_chunks: 2,
        indexed_chunks: 2,
        embedding_provider: "hashing",
        embedding_model: "hashing-256",
        dimensions: 256,
      },
    });

    await indexCaseForRetrieval("c1", true);
    expect(spy).toHaveBeenCalledWith(
      "/api/v1/retrieval/cases/c1/index",
      {},
      { params: { force: true } },
    );
  });
});
