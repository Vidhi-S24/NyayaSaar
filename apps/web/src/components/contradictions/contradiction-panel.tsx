"use client";

/**
 * Contradiction & Gap Hunter workspace (Stage 8).
 *
 * Case-scoped cross-document evidence analysis:
 * - Multi-document selection (ready docs) + partial/failed OCR visibility
 * - Bounded LangGraph execution with live polling & retry
 * - Chronological timeline + side-by-side observed evidence vs model interpretation
 * - Filters by document, category/issue, date, and review status
 * - Review actions (confirmed / dismissed / needs_review) with persistent audit trail
 * - Source viewer dialog & HTML/Markdown report export
 */

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Calendar,
  CheckCircle2,
  Clock,
  Download,
  ExternalLink,
  FileText,
  HelpCircle,
  History,
  Loader2,
  Play,
  RefreshCw,
  ShieldAlert,
  XCircle,
} from "lucide-react";
import type {
  AnalysisSourceRef,
  ContradictionFinding,
  ContradictionFindingCategory,
  ContradictionResult,
  ContradictionReviewStatus,
  Document,
  FindingReview,
  WorkflowRun,
} from "@nyayasaar/shared";
import {
  downloadCaseReport,
  isWorkflowActive,
  listCaseAnalyses,
  listFindingReviews,
  retryCaseAnalysis,
  saveBlob,
  startCaseAnalysis,
  updateFindingReview,
  workflowStatusLabel,
} from "@/lib/api/analysis";
import { getDocumentText, listDocuments } from "@/lib/api/documents";
import { ApiClientError } from "@/lib/api-client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

const CATEGORY_LABELS: Record<ContradictionFindingCategory, string> = {
  direct_contradiction: "Direct Contradiction",
  possible_inconsistency: "Possible Inconsistency",
  evidence_gap: "Evidence Gap",
  unsupported_claim: "Unsupported Claim",
};

const SEVERITY_BADGE: Record<"high" | "medium" | "low", string> = {
  high: "bg-red-100 text-red-900 border-red-200",
  medium: "bg-amber-100 text-amber-900 border-amber-200",
  low: "bg-slate-100 text-slate-800 border-slate-200",
};

const REVIEW_BADGE: Record<ContradictionReviewStatus, string> = {
  unreviewed: "bg-slate-100 text-slate-700 border-slate-200",
  confirmed: "bg-teal-100 text-teal-900 border-teal-200",
  dismissed: "bg-zinc-100 text-zinc-600 border-zinc-200",
  needs_review: "bg-amber-100 text-amber-900 border-amber-200",
};

function renderHighlightedText(
  text: string,
  spanStart?: number | null,
  spanEnd?: number | null,
) {
  if (
    typeof spanStart === "number" &&
    typeof spanEnd === "number" &&
    spanStart >= 0 &&
    spanEnd > spanStart &&
    spanEnd <= text.length
  ) {
    return (
      <>
        {text.slice(0, spanStart)}
        <mark className="rounded bg-amber-200/80 px-0.5 text-ink-900">
          {text.slice(spanStart, spanEnd)}
        </mark>
        {text.slice(spanEnd)}
      </>
    );
  }
  return text;
}

export function ContradictionPanel({ caseId }: { caseId: string }) {
  const queryClient = useQueryClient();
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [focus, setFocus] = useState("");
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Filters
  const [filterDocId, setFilterDocId] = useState<string>("all");
  const [filterCategory, setFilterCategory] = useState<string>("all");
  const [filterIssue, setFilterIssue] = useState<string>("");
  const [filterReview, setFilterReview] = useState<string>("all");
  const [filterDate, setFilterDate] = useState<string>("");

  // Review note drafts & expanded audit trails
  const [noteDrafts, setNoteDrafts] = useState<Record<string, string>>({});
  const [openHistory, setOpenHistory] = useState<Record<string, boolean>>({});
  const [viewerRef, setViewerRef] = useState<AnalysisSourceRef | null>(null);

  const docsQuery = useQuery({
    queryKey: ["case-documents", caseId],
    queryFn: () => listDocuments(caseId, { page: 1, page_size: 100 }),
    select: (env) => env.data?.items ?? [],
  });

  const readyDocs = useMemo(
    () => (docsQuery.data ?? []).filter((d: Document) => d.processing_status === "ready"),
    [docsQuery.data],
  );
  const incompleteDocs = useMemo(
    () => (docsQuery.data ?? []).filter((d: Document) => d.processing_status !== "ready"),
    [docsQuery.data],
  );

  // Default to selecting all ready documents on case change
  useEffect(() => {
    setSelectedDocIds(readyDocs.map((d) => d.id));
    setActiveRunId(null);
    setActionError(null);
  }, [caseId, readyDocs.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const runsQuery = useQuery({
    queryKey: ["contradictions", caseId],
    queryFn: () => listCaseAnalyses(caseId, 15, "contradiction"),
    select: (env) => env.data?.items ?? [],
    refetchInterval: (q) => {
      const items = q.state.data?.data?.items ?? [];
      const current = items.find((r) => r.id === activeRunId) ?? items[0];
      return current && isWorkflowActive(current.status) ? 1500 : false;
    },
  });

  const runs = useMemo(() => runsQuery.data ?? [], [runsQuery.data]);
  const currentRun: WorkflowRun | null = useMemo(() => {
    if (activeRunId) return runs.find((r) => r.id === activeRunId) ?? runs[0] ?? null;
    return runs[0] ?? null;
  }, [runs, activeRunId]);

  const result = useMemo<ContradictionResult | null>(() => {
    if (!currentRun || currentRun.status !== "completed" || !currentRun.result) {
      return null;
    }
    return currentRun.result as unknown as ContradictionResult;
  }, [currentRun]);

  const reviewsQuery = useQuery({
    queryKey: ["contradiction-reviews", caseId, currentRun?.id],
    queryFn: () => listFindingReviews(caseId, currentRun!.id),
    select: (env) => env.data?.items ?? [],
    enabled: Boolean(currentRun?.id && currentRun.status === "completed"),
  });

  const reviewByFinding = useMemo(() => {
    const map: Record<string, FindingReview> = {};
    for (const r of reviewsQuery.data ?? []) {
      map[r.finding_id] = r;
    }
    return map;
  }, [reviewsQuery.data]);

  const viewerDocQuery = useQuery({
    queryKey: ["doc-content", caseId, viewerRef?.document_id],
    queryFn: () => getDocumentText(caseId, viewerRef!.document_id),
    select: (env) => env.data,
    enabled: Boolean(viewerRef?.document_id),
  });

  const startMutation = useMutation({
    mutationFn: () =>
      startCaseAnalysis(caseId, {
        workflow_type: "contradiction",
        document_ids: selectedDocIds,
        focus: focus.trim() || undefined,
      }),
    onSuccess: (env) => {
      setActionError(null);
      if (env.data) setActiveRunId(env.data.id);
      queryClient.invalidateQueries({ queryKey: ["contradictions", caseId] });
    },
    onError: (err) => {
      setActionError(
        err instanceof ApiClientError ? err.message : "Could not start analysis.",
      );
    },
  });

  const retryMutation = useMutation({
    mutationFn: (workflowId: string) => retryCaseAnalysis(caseId, workflowId),
    onSuccess: (env) => {
      setActionError(null);
      if (env.data) setActiveRunId(env.data.id);
      queryClient.invalidateQueries({ queryKey: ["contradictions", caseId] });
    },
    onError: (err) => {
      setActionError(
        err instanceof ApiClientError ? err.message : "Retry failed.",
      );
    },
  });

  const reviewMutation = useMutation({
    mutationFn: (vars: {
      findingId: string;
      status: ContradictionReviewStatus;
      note?: string | null;
    }) =>
      updateFindingReview(caseId, currentRun!.id, vars.findingId, {
        status: vars.status,
        note: vars.note,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["contradiction-reviews", caseId, currentRun?.id],
      });
    },
    onError: (err) => {
      setActionError(
        err instanceof ApiClientError ? err.message : "Could not save review.",
      );
    },
  });

  const filteredFindings = useMemo(() => {
    if (!result) return [];
    return result.findings.filter((f: ContradictionFinding) => {
      const revStatus: ContradictionReviewStatus =
        reviewByFinding[f.finding_id]?.status ?? "unreviewed";
      if (filterCategory !== "all" && f.category !== filterCategory) return false;
      if (filterReview !== "all" && revStatus !== filterReview) return false;
      if (filterDocId !== "all") {
        const allDocs = [...f.side_a_sources, ...f.side_b_sources].map(
          (s) => s.document_id,
        );
        if (!allDocs.includes(filterDocId)) return false;
      }
      if (filterDate.trim()) {
        const q = filterDate.trim().toLowerCase();
        const dt = (f.date_text ?? "").toLowerCase();
        if (!dt.includes(q)) return false;
      }
      if (filterIssue.trim()) {
        const q = filterIssue.trim().toLowerCase();
        const issue = `${f.issue_tag ?? ""} ${f.title} ${f.dimension}`.toLowerCase();
        if (!issue.includes(q)) return false;
      }
      return true;
    });
  }, [result, reviewByFinding, filterCategory, filterReview, filterDocId, filterDate, filterIssue]);

  const toggleDoc = (id: string) => {
    setSelectedDocIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  };

  const handleExport = async (format: "html" | "markdown") => {
    if (!currentRun) return;
    try {
      const { blob, filename } = await downloadCaseReport(
        caseId,
        currentRun.id,
        format,
      );
      saveBlob(blob, filename || `contradictions-${currentRun.id.slice(0, 8)}.${format === "html" ? "html" : "md"}`);
    } catch (err) {
      setActionError(
        err instanceof ApiClientError ? err.message : "Report export failed.",
      );
    }
  };

  return (
    <div className="flex flex-col gap-5">
      {/* Run configuration */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Select Documents to Compare</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {docsQuery.isLoading ? (
            <Skeleton className="h-16 w-full" />
          ) : readyDocs.length === 0 ? (
            <div className="rounded-md border border-border bg-secondary/40 p-4 text-sm text-muted-foreground">
              No ready documents in this case yet. Upload and extract documents in the
              case workspace first.
            </div>
          ) : (
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {readyDocs.map((doc) => {
                const checked = selectedDocIds.includes(doc.id);
                return (
                  <label
                    key={doc.id}
                    className={`flex cursor-pointer items-center gap-2.5 rounded-md border px-3 py-2 text-xs transition-colors ${
                      checked
                        ? "border-teal-600 bg-teal-50/70 text-ink-900"
                        : "border-border bg-card text-muted-foreground"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleDoc(doc.id)}
                      className="h-3.5 w-3.5 accent-teal-700"
                    />
                    <FileText className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                    <span className="truncate font-medium">{doc.original_name}</span>
                    {doc.page_count ? (
                      <span className="ml-auto shrink-0 text-[11px] text-muted-foreground">
                        {doc.page_count}p
                      </span>
                    ) : null}
                  </label>
                );
              })}
            </div>
          )}

          {incompleteDocs.length > 0 && (
            <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
              <strong>Partial / pending extraction:</strong> {incompleteDocs.length}{" "}
              document(s) are not yet ready ({incompleteDocs.map((d) => `${d.original_name}: ${d.processing_status}`).join(", ")}).
            </div>
          )}

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <Input
              value={focus}
              onChange={(e) => setFocus(e.target.value)}
              placeholder="Optional focus (e.g. payment dates, delivery quantities, notice date)"
              maxLength={1000}
              className="flex-1"
            />
            <Button
              variant="teal"
              disabled={
                readyDocs.length === 0 ||
                selectedDocIds.length === 0 ||
                startMutation.isPending ||
                Boolean(currentRun && isWorkflowActive(currentRun.status))
              }
              onClick={() => startMutation.mutate()}
            >
              {startMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              Run Contradiction & Gap Hunt
            </Button>
          </div>

          {actionError && (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-900">
              {actionError}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Active / Failed Status */}
      {currentRun && isWorkflowActive(currentRun.status) && (
        <Card>
          <CardContent className="flex items-center gap-3 py-5 text-sm">
            <Loader2 className="h-4 w-4 animate-spin text-teal-700" />
            <div>
              <div className="font-medium">
                {workflowStatusLabel(currentRun.status)} ({currentRun.progress}%)
              </div>
              <div className="text-xs text-muted-foreground">
                Step: {currentRun.current_step ?? "queued"}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {currentRun && currentRun.status === "failed" && (
        <Card className="border-red-200">
          <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
            <div className="flex items-center gap-2 text-sm text-red-900">
              <XCircle className="h-4 w-4 shrink-0" />
              <span>
                {currentRun.error?.message ?? "Contradiction analysis failed."}
              </span>
            </div>
            <Button
              size="sm"
              variant="outline"
              disabled={retryMutation.isPending}
              onClick={() => retryMutation.mutate(currentRun.id)}
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Completed Result */}
      {result && (
        <>
          <div className="rounded-md border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-xs text-amber-900">
            <strong>Analytical flags only — professional review required.</strong>{" "}
            Potential contradictions and inconsistencies are flagged for human inspection
            and never constitute proof of dishonesty or wrongdoing.
            {result.is_mock && (
              <span className="ml-1 font-semibold">
                [Development fixture — no AI model was called.]
              </span>
            )}
          </div>

          {/* Summary & Exports */}
          <Card>
            <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3 pb-2">
              <div>
                <CardTitle className="text-base">Analysis Summary</CardTitle>
                <p className="mt-1 text-xs text-muted-foreground">
                  Verified: {result.verification.supported} supported ·{" "}
                  {result.verification.partially_supported} source-cited ·{" "}
                  {result.verification.unsupported} unsupported
                </p>
              </div>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => handleExport("html")}>
                  <Download className="h-3.5 w-3.5" />
                  HTML Report
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleExport("markdown")}
                >
                  <Download className="h-3.5 w-3.5" />
                  Markdown
                </Button>
              </div>
            </CardHeader>
            <CardContent className="text-sm leading-relaxed text-foreground">
              {result.summary}
            </CardContent>
          </Card>

          {/* Filters + Severity Legend */}
          <Card>
            <CardContent className="flex flex-col gap-3 pt-4">
              <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                <span className="font-semibold text-foreground">Severity definitions:</span>
                <span><strong>High:</strong> Direct conflict on material fact/date/amount or missing core proof</span>
                <span>· <strong>Medium:</strong> Contextual inconsistency or secondary gap</span>
                <span>· <strong>Low:</strong> Minor ambiguity</span>
              </div>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
                <select
                  aria-label="Filter by document"
                  value={filterDocId}
                  onChange={(e) => setFilterDocId(e.target.value)}
                  className="h-9 rounded-md border border-input bg-background px-2.5 text-xs"
                >
                  <option value="all">All documents</option>
                  {readyDocs.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.original_name}
                    </option>
                  ))}
                </select>
                <select
                  aria-label="Filter by category"
                  value={filterCategory}
                  onChange={(e) => setFilterCategory(e.target.value)}
                  className="h-9 rounded-md border border-input bg-background px-2.5 text-xs"
                >
                  <option value="all">All finding types</option>
                  <option value="direct_contradiction">Direct Contradiction</option>
                  <option value="possible_inconsistency">Possible Inconsistency</option>
                  <option value="evidence_gap">Evidence Gap</option>
                  <option value="unsupported_claim">Unsupported Claim</option>
                </select>
                <Input
                  aria-label="Filter by issue"
                  value={filterIssue}
                  onChange={(e) => setFilterIssue(e.target.value)}
                  placeholder="Filter by issue..."
                  className="h-9 text-xs"
                />
                <select
                  aria-label="Filter by review status"
                  value={filterReview}
                  onChange={(e) => setFilterReview(e.target.value)}
                  className="h-9 rounded-md border border-input bg-background px-2.5 text-xs"
                >
                  <option value="all">All review statuses</option>
                  <option value="unreviewed">Unreviewed</option>
                  <option value="confirmed">Confirmed</option>
                  <option value="needs_review">Needs Further Review</option>
                  <option value="dismissed">Dismissed</option>
                </select>
                <Input
                  aria-label="Filter by date"
                  value={filterDate}
                  onChange={(e) => setFilterDate(e.target.value)}
                  placeholder="Filter by date..."
                  className="h-9 text-xs"
                />
              </div>
            </CardContent>
          </Card>

          {/* Findings */}
          <div className="flex flex-col gap-4">
            {filteredFindings.length === 0 ? (
              <Card>
                <CardContent className="py-8 text-center text-sm text-muted-foreground">
                  No findings match the current filters.
                </CardContent>
              </Card>
            ) : (
              filteredFindings.map((f) => {
                const rev = reviewByFinding[f.finding_id];
                const currentStatus: ContradictionReviewStatus =
                  rev?.status ?? "unreviewed";
                const noteVal =
                  noteDrafts[f.finding_id] ?? rev?.reviewer_note ?? "";
                const historyOpen = Boolean(openHistory[f.finding_id]);

                return (
                  <Card key={f.finding_id} className="overflow-hidden">
                    <CardHeader className="border-b border-border/60 bg-secondary/20 pb-3">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div className="flex flex-col gap-1">
                          <div className="flex flex-wrap items-center gap-1.5">
                            <span className="font-mono text-xs text-muted-foreground">
                              {f.finding_id}
                            </span>
                            <Badge variant="outline">
                              {CATEGORY_LABELS[f.category]}
                            </Badge>
                            <Badge className={SEVERITY_BADGE[f.severity]}>
                              {f.severity.toUpperCase()}
                            </Badge>
                            <Badge className={REVIEW_BADGE[currentStatus]}>
                              {currentStatus.replace("_", " ")}
                            </Badge>
                            {f.date_text && (
                              <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                                <Calendar className="h-3 w-3" />
                                {f.date_text}
                              </span>
                            )}
                          </div>
                          <CardTitle className="text-sm font-semibold">
                            {f.title}
                          </CardTitle>
                        </div>
                      </div>
                    </CardHeader>

                    <CardContent className="flex flex-col gap-4 pt-4">
                      {/* Observed vs Model Interpretation */}
                      <div className="grid gap-3 md:grid-cols-2">
                        <div className="rounded-md border border-border bg-secondary/30 p-3">
                          <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-ink-800">
                            Observed Evidence
                          </div>
                          <p className="text-xs leading-relaxed text-foreground">
                            {f.observed_evidence_summary}
                          </p>
                        </div>
                        <div className="rounded-md border border-amber-200/80 bg-amber-50/40 p-3">
                          <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-amber-900">
                            Model Interpretation (Why Flagged)
                          </div>
                          <p className="text-xs leading-relaxed text-foreground">
                            {f.model_interpretation}
                          </p>
                        </div>
                      </div>

                      {/* Side-by-side passages */}
                      <div className="grid gap-3 md:grid-cols-2">
                        <div className="rounded-md border border-border p-3">
                          <div className="mb-2 text-xs font-semibold text-ink-900">
                            {f.side_a_label}
                          </div>
                          {f.side_a_sources.length === 0 ? (
                            <p className="text-xs text-muted-foreground">
                              No verified passage attached.
                            </p>
                          ) : (
                            <div className="flex flex-col gap-2">
                              {f.side_a_sources.map((s, idx) => (
                                <div
                                  key={`${s.source_id}-${idx}`}
                                  className="rounded bg-secondary/40 p-2 text-xs"
                                >
                                  {s.quote && (
                                    <p className="mb-1.5 italic text-foreground">
                                      &ldquo;{s.quote}&rdquo;
                                    </p>
                                  )}
                                  <button
                                    type="button"
                                    onClick={() => setViewerRef(s)}
                                    className="inline-flex items-center gap-1 font-medium text-teal-800 hover:underline"
                                  >
                                    {s.document_name} · p.{s.page_number}
                                    <ExternalLink className="h-3 w-3" />
                                  </button>
                                  <span className="ml-2 text-[11px] text-muted-foreground">
                                    {s.quote_verified ? "verified quote" : "page cited"}
                                  </span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                        <div className="rounded-md border border-border p-3">
                          <div className="mb-2 text-xs font-semibold text-ink-900">
                            {f.side_b_label ?? "Comparison / Missing Support"}
                          </div>
                          {f.side_b_sources.length === 0 ? (
                            <p className="text-xs text-muted-foreground">
                              No opposing or supporting passage in the selected record.
                            </p>
                          ) : (
                            <div className="flex flex-col gap-2">
                              {f.side_b_sources.map((s, idx) => (
                                <div
                                  key={`${s.source_id}-${idx}`}
                                  className="rounded bg-secondary/40 p-2 text-xs"
                                >
                                  {s.quote && (
                                    <p className="mb-1.5 italic text-foreground">
                                      &ldquo;{s.quote}&rdquo;
                                    </p>
                                  )}
                                  <button
                                    type="button"
                                    onClick={() => setViewerRef(s)}
                                    className="inline-flex items-center gap-1 font-medium text-teal-800 hover:underline"
                                  >
                                    {s.document_name} · p.{s.page_number}
                                    <ExternalLink className="h-3 w-3" />
                                  </button>
                                  <span className="ml-2 text-[11px] text-muted-foreground">
                                    {s.quote_verified ? "verified quote" : "page cited"}
                                  </span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Review controls + audit trail */}
                      <div className="flex flex-col gap-2 border-t border-border/60 pt-3">
                        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                          <Input
                            value={noteVal}
                            onChange={(e) =>
                              setNoteDrafts((prev) => ({
                                ...prev,
                                [f.finding_id]: e.target.value,
                              }))
                            }
                            placeholder="Optional reviewer note..."
                            className="h-8 flex-1 text-xs"
                          />
                          <div className="flex flex-wrap gap-1.5">
                            <Button
                              size="sm"
                              variant={currentStatus === "confirmed" ? "teal" : "outline"}
                              disabled={reviewMutation.isPending}
                              onClick={() =>
                                reviewMutation.mutate({
                                  findingId: f.finding_id,
                                  status: "confirmed",
                                  note: noteVal,
                                })
                              }
                            >
                              <CheckCircle2 className="h-3.5 w-3.5" />
                              Confirm
                            </Button>
                            <Button
                              size="sm"
                              variant={currentStatus === "needs_review" ? "default" : "outline"}
                              disabled={reviewMutation.isPending}
                              onClick={() =>
                                reviewMutation.mutate({
                                  findingId: f.finding_id,
                                  status: "needs_review",
                                  note: noteVal,
                                })
                              }
                            >
                              <HelpCircle className="h-3.5 w-3.5" />
                              Needs Review
                            </Button>
                            <Button
                              size="sm"
                              variant={currentStatus === "dismissed" ? "secondary" : "outline"}
                              disabled={reviewMutation.isPending}
                              onClick={() =>
                                reviewMutation.mutate({
                                  findingId: f.finding_id,
                                  status: "dismissed",
                                  note: noteVal,
                                })
                              }
                            >
                              <XCircle className="h-3.5 w-3.5" />
                              Dismiss
                            </Button>
                            {rev && rev.history.length > 0 && (
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() =>
                                  setOpenHistory((prev) => ({
                                    ...prev,
                                    [f.finding_id]: !historyOpen,
                                  }))
                                }
                              >
                                <History className="h-3.5 w-3.5" />
                                Audit ({rev.history.length})
                              </Button>
                            )}
                          </div>
                        </div>

                        {historyOpen && rev && rev.history.length > 0 && (
                          <div className="rounded bg-secondary/40 p-2.5 text-[11px] text-muted-foreground">
                            <div className="mb-1 font-semibold text-foreground">
                              Review Audit Trail
                            </div>
                            <ul className="space-y-1">
                              {rev.history.map((ev, i) => (
                                <li key={i}>
                                  {ev.at}:{" "}
                                  <strong>{ev.previous_status ?? "unreviewed"}</strong>{" "}
                                  &rarr; <strong>{ev.new_status}</strong>
                                  {ev.user_email ? ` by ${ev.user_email}` : ""}
                                  {ev.note ? ` — "${ev.note}"` : ""}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                );
              })
            )}
          </div>

          {/* Chronological Timeline */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <Clock className="h-4 w-4 text-teal-700" />
                Chronological Timeline ({result.timeline.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              {result.timeline.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No dated events were extracted from the selected documents.
                </p>
              ) : (
                <ol className="space-y-3 border-l-2 border-teal-200 pl-4">
                  {result.timeline.map((ev, idx) => (
                    <li key={idx} className="text-xs">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-semibold text-ink-900">
                          {ev.date_text}
                        </span>
                        {ev.date_ambiguous && (
                          <Badge variant="outline" className="text-[10px]">
                            <AlertTriangle className="mr-1 h-2.5 w-2.5" />
                            Ambiguous date
                          </Badge>
                        )}
                      </div>
                      <p className="mt-0.5 text-foreground">{ev.event}</p>
                      <div className="mt-1 flex flex-wrap gap-2">
                        {ev.sources.map((s, sIdx) => (
                          <button
                            key={sIdx}
                            type="button"
                            onClick={() => setViewerRef(s)}
                            className="inline-flex items-center gap-1 text-[11px] text-teal-800 hover:underline"
                          >
                            {s.document_name} · p.{s.page_number}
                            <ExternalLink className="h-2.5 w-2.5" />
                          </button>
                        ))}
                      </div>
                    </li>
                  ))}
                </ol>
              )}
            </CardContent>
          </Card>

          {/* Limitations */}
          {result.limitations.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-sm">
                  <ShieldAlert className="h-4 w-4 text-amber-600" />
                  Limitations &amp; Verification Notes
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="list-disc space-y-1 pl-5 text-xs text-muted-foreground">
                  {result.limitations.map((lim, i) => (
                    <li key={i}>{lim}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </>
      )}

      {/* Source Passage Viewer Dialog */}
      <Dialog
        open={Boolean(viewerRef)}
        onOpenChange={(open) => !open && setViewerRef(null)}
      >
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="text-sm">
              {viewerRef?.document_name} — Page {viewerRef?.page_number}
            </DialogTitle>
          </DialogHeader>
          {viewerDocQuery.isLoading ? (
            <Skeleton className="h-40 w-full" />
          ) : viewerDocQuery.isError ? (
            <p className="text-xs text-red-700">Could not load source page.</p>
          ) : (
            (() => {
              const pageObj = viewerDocQuery.data?.chunks.find(
                (p) => p.page_number === viewerRef?.page_number,
              );
              const text = pageObj?.extracted_text ?? "Page text unavailable.";
              return (
                <pre className="max-h-[60vh] overflow-auto whitespace-pre-wrap rounded-md border border-border bg-secondary/30 p-3 font-mono text-xs leading-relaxed text-foreground">
                  {renderHighlightedText(
                    text,
                    viewerRef?.span_start,
                    viewerRef?.span_end,
                  )}
                </pre>
              );
            })()
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
