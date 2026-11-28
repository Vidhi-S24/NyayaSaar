"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  FileText,
  Gavel,
  Loader2,
  Play,
  RefreshCw,
  Scale,
  SearchCheck,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import type {
  Document,
  JudgeAuditItem,
  JudgeResult,
  WorkflowRun,
} from "@nyayasaar/shared";
import {
  downloadCaseReport,
  isWorkflowActive,
  listJudgeAnalyses,
  retryCaseAnalysis,
  saveBlob,
  startJudgeAnalysis,
  workflowStatusLabel,
} from "@/lib/api/analysis";
import { listDocuments } from "@/lib/api/documents";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import {
  AuditStatusBadge,
  ModeLegend,
  SeverityBadge,
  SourceEvidenceList,
  SupportBadge,
  VerificationStrip,
} from "@/components/shared/mode-ui";

function isJudgeResult(run: WorkflowRun | undefined): JudgeResult | null {
  if (!run || run.status !== "completed" || !run.result) return null;
  if (!("issue_coverage" in run.result)) return null;
  return run.result as JudgeResult;
}

function AuditCard({ item }: { item: JudgeAuditItem }) {
  return (
    <article className="rounded-lg border border-border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
            <span className="font-mono font-semibold text-foreground">
              {item.audit_id}
            </span>
            <span>{item.item}</span>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <AuditStatusBadge status={item.status} />
          <SeverityBadge severity={item.severity} />
          <SupportBadge support={item.support} />
        </div>
      </div>

      <div className="mt-3 rounded-md border border-border bg-muted/20 p-3">
        <p className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          <Sparkles className="h-3 w-3" aria-hidden="true" />
          Audit finding — AI analysis, not a judicial determination
        </p>
        <p className="mt-1.5 text-xs leading-relaxed text-foreground/90">
          {item.finding || "No finding text supplied."}
        </p>
      </div>

      {item.opposing_considered !== null && (
        <p
          className={`mt-3 inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] ${
            item.opposing_considered
              ? "border-teal-200 bg-teal-50 text-teal-800"
              : "border-amber-200 bg-amber-50 text-amber-900"
          }`}
        >
          {item.opposing_considered ? (
            <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
          ) : (
            <ShieldAlert className="h-3 w-3" aria-hidden="true" />
          )}
          Opposing arguments / contrary authorities considered:{" "}
          {item.opposing_considered ? "yes" : "no"}
        </p>
      )}

      <div className="mt-3">
        <SourceEvidenceList
          refs={item.source_refs}
          label="Source evidence for this finding"
        />
      </div>
    </article>
  );
}

const AUDIT_SECTIONS: Array<{
  key: keyof Pick<
    JudgeResult,
    | "issue_coverage"
    | "reasoning_consistency"
    | "source_support_audit"
    | "citation_integrity"
    | "opposing_consideration_audit"
    | "unresolved_questions"
  >;
  title: string;
  description: string;
  icon: typeof Scale;
}> = [
  {
    key: "issue_coverage",
    title: "Issue coverage",
    description: "Are identified legal issues addressed with reasoned analysis?",
    icon: CheckCircle2,
  },
  {
    key: "reasoning_consistency",
    title: "Reasoning consistency",
    description: "Internal inconsistencies and unresolved factual conflicts.",
    icon: Scale,
  },
  {
    key: "source_support_audit",
    title: "Source support",
    description: "Are conclusions and assertions backed by cited evidence?",
    icon: SearchCheck,
  },
  {
    key: "citation_integrity",
    title: "Citation integrity",
    description: "Missing, incomplete, or unsupported citations.",
    icon: FileText,
  },
  {
    key: "opposing_consideration_audit",
    title: "Opposing arguments & contrary authorities",
    description: "Were material opposing positions and contrary authorities considered?",
    icon: AlertTriangle,
  },
  {
    key: "unresolved_questions",
    title: "Unresolved questions",
    description: "Questions that remain unanswered and require human review.",
    icon: ShieldAlert,
  },
];

export function JudgePanel({ caseId }: { caseId?: string }) {
  const queryClient = useQueryClient();
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [focus, setFocus] = useState("");
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const docsQuery = useQuery({
    queryKey: ["documents", caseId],
    queryFn: () => listDocuments(caseId!),
    enabled: Boolean(caseId),
    select: (env) => env.data?.items ?? [],
  });

  const runsQuery = useQuery({
    queryKey: ["analysis", "judge", caseId],
    queryFn: () => listJudgeAnalyses(caseId!, 15),
    enabled: Boolean(caseId),
    select: (env) => env.data?.items ?? [],
    refetchInterval: (query) => {
      const items = query.state.data?.data?.items ?? [];
      return items.some((r) => isWorkflowActive(r.status)) ? 1500 : false;
    },
  });

  const runs = useMemo(() => runsQuery.data ?? [], [runsQuery.data]);
  const activeRun: WorkflowRun | undefined = useMemo(() => {
    if (activeRunId) return runs.find((r) => r.id === activeRunId) ?? runs[0];
    return runs[0];
  }, [runs, activeRunId]);

  useEffect(() => {
    if (runs.length > 0 && !activeRunId) setActiveRunId(runs[0].id);
  }, [runs, activeRunId]);

  const startMutation = useMutation({
    mutationFn: () =>
      startJudgeAnalysis(caseId!, {
        document_ids: selectedDocIds.length > 0 ? selectedDocIds : undefined,
        focus: focus.trim() || undefined,
      }),
    onSuccess: (env) => {
      if (env.data) setActiveRunId(env.data.id);
      void queryClient.invalidateQueries({
        queryKey: ["analysis", "judge", caseId],
      });
    },
  });

  const retryMutation = useMutation({
    mutationFn: (workflowId: string) => retryCaseAnalysis(caseId!, workflowId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["analysis", "judge", caseId],
      });
    },
  });

  const result = useMemo(() => isJudgeResult(activeRun), [activeRun]);

  const coverageSummary = useMemo(() => {
    if (!result) return null;
    const all = [
      ...result.issue_coverage,
      ...result.reasoning_consistency,
      ...result.source_support_audit,
      ...result.citation_integrity,
      ...result.opposing_consideration_audit,
      ...result.unresolved_questions,
    ];
    return {
      total: all.length,
      covered: all.filter((item) => item.status === "covered").length,
      partial: all.filter((item) => item.status === "partially_covered").length,
      problems: all.filter((item) =>
        ["unsupported", "inconsistent", "missing_citation"].includes(item.status),
      ).length,
      unresolved: all.filter((item) => item.status === "unresolved").length,
      opposingMissing: all.filter((item) => item.opposing_considered === false).length,
    };
  }, [result]);

  async function handleDownload(format: "html" | "markdown") {
    if (!caseId || !activeRun) return;
    setExportError(null);
    try {
      const { blob, filename } = await downloadCaseReport(
        caseId,
        activeRun.id,
        format,
      );
      saveBlob(blob, filename);
    } catch (err) {
      setExportError(
        err instanceof Error ? err.message : "Could not download report.",
      );
    }
  }

  if (!caseId) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <Gavel className="h-8 w-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            Select a case workspace to run a reasoning and issue-coverage audit.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-amber-200 bg-amber-50/70 p-4 text-sm">
        <div className="flex items-start gap-3">
          <Gavel className="mt-0.5 h-4 w-4 shrink-0 text-amber-800" aria-hidden="true" />
          <div className="space-y-1">
            <p className="font-semibold text-amber-950">
              This is a reasoning-audit assistant — not a simulated judge or an
              official court decision.
            </p>
            <p className="text-xs text-amber-900/85">
              Judge/Clerk Mode checks issue coverage, source support, citation
              integrity, reasoning consistency, and whether contrary material was
              considered. It does not decide who should win and does not issue a
              judgment.
            </p>
          </div>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <SearchCheck className="h-4 w-4 text-ink-700" />
            Run a reasoning audit
          </CardTitle>
          <CardDescription>
            The workflow reads only the selected case documents plus any legal
            records available from the configured corpus.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label htmlFor="judge-focus" className="mb-1 block text-xs font-medium">
              Issue or audit focus (optional)
            </label>
            <Input
              id="judge-focus"
              placeholder="e.g., limitation, evidentiary burden, consistency of dates, citation support..."
              value={focus}
              onChange={(e) => setFocus(e.target.value)}
            />
          </div>

          {(docsQuery.data ?? []).length > 0 && (
            <div className="space-y-1.5">
              <span className="text-xs font-medium text-muted-foreground">
                Limit to specific case documents (optional — default uses all ready
                documents):
              </span>
              <div className="flex flex-wrap gap-2">
                {(docsQuery.data ?? []).map((doc: Document) => {
                  const checked = selectedDocIds.includes(doc.id);
                  return (
                    <button
                      key={doc.id}
                      type="button"
                      aria-pressed={checked}
                      onClick={() =>
                        setSelectedDocIds((prev) =>
                          checked
                            ? prev.filter((id) => id !== doc.id)
                            : [...prev, doc.id],
                        )
                      }
                      className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs transition-colors ${
                        checked
                          ? "border-ink-600 bg-ink-50 text-ink-900"
                          : "border-border bg-background text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      <FileText className="h-3 w-3" />
                      {doc.original_name}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="teal"
              disabled={
                startMutation.isPending ||
                (activeRun ? isWorkflowActive(activeRun.status) : false)
              }
              onClick={() => startMutation.mutate()}
            >
              {startMutation.isPending ||
              (activeRun && isWorkflowActive(activeRun.status)) ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              Run Judge/Clerk audit
            </Button>
            <p className="text-[11px] text-muted-foreground">
              Requires at least one document with extracted text.
            </p>
          </div>

          {startMutation.isError && (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
              Could not start Judge/Clerk Mode:{" "}
              {startMutation.error instanceof Error
                ? startMutation.error.message
                : "Unknown error"}
            </div>
          )}

          {runs.length > 0 && activeRun && (
            <div className="space-y-3 rounded-lg border border-border bg-muted/20 p-3.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-semibold">Run:</span>
                  <select
                    aria-label="Select judge/clerk run"
                    value={activeRun.id}
                    onChange={(e) => setActiveRunId(e.target.value)}
                    className="h-8 rounded-md border border-input bg-background px-2 text-xs"
                  >
                    {runs.map((run) => (
                      <option key={run.id} value={run.id}>
                        {new Date(run.created_at).toLocaleString()} —{" "}
                        {workflowStatusLabel(run.status)}
                        {run.is_mock ? " (Fixture)" : ""}
                      </option>
                    ))}
                  </select>
                  <Badge
                    variant={
                      activeRun.status === "completed"
                        ? "success"
                        : activeRun.status === "failed"
                          ? "destructive"
                          : "warning"
                    }
                  >
                    {workflowStatusLabel(activeRun.status)}
                  </Badge>
                  {activeRun.is_mock && (
                    <Badge variant="warning">Development fixture</Badge>
                  )}
                </div>
                {activeRun.status === "completed" && (
                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => void handleDownload("html")}
                    >
                      <Download className="h-3.5 w-3.5" />
                      HTML report
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => void handleDownload("markdown")}
                    >
                      <Download className="h-3.5 w-3.5" />
                      Markdown
                    </Button>
                  </div>
                )}
              </div>

              {isWorkflowActive(activeRun.status) && (
                <div className="space-y-1">
                  <Progress value={activeRun.progress} />
                  <p className="text-xs text-muted-foreground">
                    Step: {activeRun.current_step ?? "queued"} ({activeRun.progress}%)
                  </p>
                </div>
              )}

              {activeRun.status === "failed" && (
                <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
                  <span>{activeRun.error?.message || "Judge/Clerk run failed."}</span>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={retryMutation.isPending}
                    onClick={() => retryMutation.mutate(activeRun.id)}
                  >
                    <RefreshCw className="h-3.5 w-3.5" />
                    Retry
                  </Button>
                </div>
              )}

              {exportError && <p className="text-xs text-destructive">{exportError}</p>}
            </div>
          )}
        </CardContent>
      </Card>

      {result ? (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <CardTitle className="font-serif text-lg">
                    Reasoning audit report
                  </CardTitle>
                  <CardDescription>
                    Provider: {result.provider}/{result.model} · Schema v
                    {result.result_schema_version}
                  </CardDescription>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {result.is_mock && <Badge variant="warning">Development fixture</Badge>}
                  <Badge variant="outline">Judge/Clerk v{result.workflow_version}</Badge>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <ModeLegend />
              <p className="text-sm leading-relaxed text-foreground/90">{result.summary}</p>
              {result.overall_assessment && (
                <div className="rounded-md border border-ink-200 bg-ink-50/60 p-3">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-ink-700">
                    Overall audit assessment
                  </p>
                  <p className="mt-1 text-xs leading-relaxed text-ink-900">
                    {result.overall_assessment}
                  </p>
                </div>
              )}
              <VerificationStrip verification={result.verification} />
              {result.insufficient_sources && (
                <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                  No usable extracted document text was available. Upload and process
                  documents, then run the audit again.
                </div>
              )}
            </CardContent>
          </Card>

          {coverageSummary && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Coverage overview</CardTitle>
                <CardDescription>
                  A quick audit posture. Counts describe findings, not a decision on
                  the merits.
                </CardDescription>
              </CardHeader>
              <CardContent className="grid grid-cols-2 gap-2 sm:grid-cols-5">
                {[
                  { label: "Findings", value: coverageSummary.total },
                  { label: "Covered", value: coverageSummary.covered },
                  { label: "Partial", value: coverageSummary.partial },
                  { label: "Problems", value: coverageSummary.problems },
                  { label: "Opposing missing", value: coverageSummary.opposingMissing },
                ].map((item) => (
                  <div
                    key={item.label}
                    className="rounded-md border border-border bg-muted/20 px-3 py-2"
                  >
                    <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                      {item.label}
                    </p>
                    <p className="text-lg font-semibold tabular-nums text-foreground">
                      {item.value}
                    </p>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {AUDIT_SECTIONS.map((section) => {
            const items = result[section.key] as JudgeAuditItem[];
            const Icon = section.icon;
            return (
              <Card key={section.key}>
                <CardHeader>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <CardTitle className="flex items-center gap-2 text-base">
                        <Icon className="h-4 w-4 text-ink-700" aria-hidden="true" />
                        {section.title}
                      </CardTitle>
                      <CardDescription>{section.description}</CardDescription>
                    </div>
                    <Badge variant="outline">{items.length} finding(s)</Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  {items.length === 0 ? (
                    <p className="rounded-md border border-dashed border-border p-4 text-xs text-muted-foreground">
                      No findings recorded for this audit dimension.
                    </p>
                  ) : (
                    items.map((item) => <AuditCard key={item.audit_id} item={item} />)
                  )}
                </CardContent>
              </Card>
            );
          })}

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Limitations &amp; provenance</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-xs text-muted-foreground">
                {result.judicial_audit_disclaimer}
              </p>
              {result.verification.notes.length > 0 && (
                <ul className="list-disc space-y-1 pl-4 text-xs text-muted-foreground">
                  {result.verification.notes.map((note, index) => (
                    <li key={index}>{note}</li>
                  ))}
                </ul>
              )}
              <ul className="list-disc space-y-1 pl-4 text-xs text-muted-foreground">
                {result.limitations.map((limitation, index) => (
                  <li key={index}>{limitation}</li>
                ))}
              </ul>
              {result.source_manifest.length > 0 && (
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Source manifest
                  </p>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {result.source_manifest.map((source) => (
                      <Badge
                        key={source.source_id}
                        variant="outline"
                        className="font-mono text-[10px]"
                      >
                        {source.source_id}: {source.document_name}
                        {source.page_number > 0 ? ` p.${source.page_number}` : ""}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      ) : (
        !runsQuery.isLoading && (
          <Card>
            <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
              <Gavel className="h-8 w-8 text-muted-foreground" />
              <div>
                <p className="text-sm font-medium text-foreground">
                  No reasoning audit yet
                </p>
                <p className="mt-1 max-w-md text-xs text-muted-foreground">
                  Run Judge/Clerk Mode to audit issue coverage, source support,
                  citation integrity, reasoning consistency, and consideration of
                  opposing material. Findings require human legal review.
                </p>
              </div>
            </CardContent>
          </Card>
        )
      )}
    </div>
  );
}
