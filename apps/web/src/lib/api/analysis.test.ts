import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  getAIStatus,
  getCaseAnalysis,
  isWorkflowActive,
  listAdvocateAnalyses,
  listJudgeAnalyses,
  startAdvocateAnalysis,
  startCaseAnalysis,
  startJudgeAnalysis,
  supportLabel,
  verificationRate,
  workflowStatusLabel,
} from "@/lib/api/analysis";
import type { CaseAnalysisResult } from "@nyayasaar/shared";

const fetchMock = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockClear();
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

function result(overrides: Partial<CaseAnalysisResult> = {}): CaseAnalysisResult {
  return {
    workflow_id: "wf-1",
    case_id: "case-1",
    generated_at: "2026-11-20T00:00:00Z",
    provider: "mock",
    model: "fixture",
    is_mock: true,
    workflow_version: "6.0.0",
    prompt_version: "2026-11-case-intelligence-v1",
    result_schema_version: "6.0",
    insufficient_sources: false,
    summary: "Fixture summary.",
    parties: [],
    entities: [],
    amounts: [],
    facts: [],
    procedural_history: [],
    legal_issues: [],
    issue_analysis: [],
    evidence_questions: [],
    ambiguities: [],
    timeline: [],
    inferences: [],
    unverified_hypotheses: [],
    missing_information: [],
    limitations: ["Development fixture only."],
    verification: {
      total_claims: 0,
      supported: 0,
      partially_supported: 0,
      unsupported: 0,
      invalid_source_refs: 0,
      verified_spans: 0,
      unverified_quotes: 0,
      retried: false,
      categories: [],
      notes: [],
    },
    source_manifest: [],
    source_stats: {
      documents_available: 0,
      documents_analyzed: 0,
      pages_available: 0,
      pages_included: 0,
      characters_included: 0,
      duplicate_pages_skipped: 0,
      short_pages: 0,
      truncated_pages: 0,
      omitted_pages: 0,
      failed_documents: 0,
      ocr_required_documents: 0,
      incomplete_extraction_documents: 0,
      instruction_like_sources: 0,
    },
    professional_review_required: true,
    input_metadata: {},
    ...overrides,
  };
}

describe("analysis API wrappers", () => {
  it("starts a workflow with the case-scoped endpoint", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(202, {
        success: true,
        data: {
          id: "wf-1",
          case_id: "case-1",
          workflow_type: "case_analysis",
          status: "queued",
          progress: 0,
        },
      }),
    );

    const envelope = await startCaseAnalysis("case-1", { focus: "notice dates" });

    expect(envelope.data?.id).toBe("wf-1");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/api/v1/cases/case-1/analysis");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ focus: "notice dates" });
  });

  it("polls a single workflow run", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(200, {
        success: true,
        data: { id: "wf-1", status: "completed", result: result() },
      }),
    );

    const envelope = await getCaseAnalysis("case-1", "wf-1");

    expect(envelope.data?.result?.is_mock).toBe(true);
    expect(fetchMock.mock.calls[0][0]).toContain(
      "/api/v1/cases/case-1/analysis/wf-1",
    );
  });

  it("reads safe provider status without a key", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(200, {
        success: true,
        data: {
          provider: "mock",
          requested_provider: "gemini",
          model: "fixture",
          is_mock: true,
          configured: true,
          message: "Development fixture mode is active.",
        },
      }),
    );

    const envelope = await getAIStatus();

    expect(envelope.data?.is_mock).toBe(true);
    expect(JSON.stringify(envelope.data)).not.toContain("api_key");
  });

  it("starts Advocate Mode with the selected side and document scope", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(202, {
        success: true,
        data: {
          id: "wf-adv",
          case_id: "case-1",
          workflow_type: "advocate",
          status: "queued",
          progress: 0,
        },
      }),
    );

    const envelope = await startAdvocateAnalysis("case-1", {
      document_ids: ["doc-1"],
      focus: "limitation",
      preferred_side: "respondent",
    });

    expect(envelope.data?.workflow_type).toBe("advocate");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/api/v1/cases/case-1/analysis");
    expect(JSON.parse(init.body)).toEqual({
      document_ids: ["doc-1"],
      focus: "limitation",
      preferred_side: "respondent",
      workflow_type: "advocate",
    });
  });

  it("starts Judge/Clerk Mode and lists runs by workflow type", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(202, {
        success: true,
        data: {
          id: "wf-judge",
          case_id: "case-1",
          workflow_type: "judge",
          status: "queued",
          progress: 0,
        },
      }),
    );

    const started = await startJudgeAnalysis("case-1", { focus: "citations" });
    expect(started.data?.workflow_type).toBe("judge");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      focus: "citations",
      workflow_type: "judge",
    });

    fetchMock.mockResolvedValueOnce(
      jsonResponse(200, { success: true, data: { items: [], total: 0 } }),
    );
    await listJudgeAnalyses("case-1");
    expect(fetchMock.mock.calls[1][0]).toContain("workflow_type=judge");

    fetchMock.mockResolvedValueOnce(
      jsonResponse(200, { success: true, data: { items: [], total: 0 } }),
    );
    await listAdvocateAnalyses("case-1");
    expect(fetchMock.mock.calls[2][0]).toContain("workflow_type=advocate");
  });
});

describe("analysis view helpers", () => {
  it("identifies active workflow states", () => {
    expect(isWorkflowActive("queued")).toBe(true);
    expect(isWorkflowActive("running")).toBe(true);
    expect(isWorkflowActive("completed")).toBe(false);
    expect(isWorkflowActive("failed")).toBe(false);
  });

  it("labels workflow and support states honestly", () => {
    expect(workflowStatusLabel("running")).toBe("Analysing");
    expect(supportLabel("supported")).toBe("Supported by source");
    expect(supportLabel("partially_supported")).toBe(
      "Source cited, quote unverified",
    );
    expect(supportLabel("unsupported")).toBe("Unsupported");
  });

  it("computes a verification score that counts partial support at half", () => {
    expect(
      verificationRate(
        result({
          verification: {
            total_claims: 4,
            supported: 2,
            partially_supported: 1,
            unsupported: 1,
            invalid_source_refs: 0,
            verified_spans: 2,
            unverified_quotes: 1,
            retried: false,
            categories: [],
            notes: [],
          },
        }),
      ),
    ).toBe(63);
  });

  it("returns 0 for a result with no claims", () => {
    expect(verificationRate(result())).toBe(0);
  });
});
