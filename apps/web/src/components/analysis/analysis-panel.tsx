"use client";

/**
 * AnalysisPanel — Stage 5 Case Intelligence workflow UI.
 *
 * Everything shown here comes from the API. Long-running analysis is queued
 * server-side and polled; there are no simulated buttons, fake progress bars,
 * or placeholder results. Development-fixture output is explicitly labelled.
 */

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowUpRight,
  Brain,
  CheckCircle2,
  Clock,
  FileSearch,
  Loader2,
  RefreshCw,
  ShieldAlert,
  XCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  getAIStatus,
  getCaseAnalysis,
  isWorkflowActive,
  listCaseAnalyses,
  retryCaseAnalysis,
  startCaseAnalysis,
  supportLabel,
  verificationRate,
  workflowStatusLabel,
} from "@/lib/api/analysis";
import { getDocumentText } from "@/lib/api/documents";
import { ApiClientError } from "@/lib/api-client";
import type {
  AnalysisClaim,
  AnalysisSourceRef,
  AnalysisSupport,
  CaseAnalysisResult,
  WorkflowRun,
} from "@nyayasaar/shared";

// ---------------------------------------------------------------------------
// Small presentational helpers
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: WorkflowRun["status"] }) {
  if (status === "completed")
    return (
      <Badge variant="success" className="gap-1">
        <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
        Completed
      </Badge>
    );
  if (status === "failed")
    return (
      <Badge variant="destructive" className="gap-1">
        <XCircle className="h-3 w-3" aria-hidden="true" />
        Failed
      </Badge>
    );
  return (
    <Badge variant="warning" className="gap-1">
      <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
      {workflowStatusLabel(status)}
    </Badge>
  );
}

function SupportBadge({ support }: { support: AnalysisSupport }) {
  if (support === "supported") return <Badge variant="success">{supportLabel(support)}</Badge>;
  if (support === "partially_supported") return <Badge variant="warning">{supportLabel(support)}</Badge>;
  return <Badge variant="destructive">{supportLabel(support)}</Badge>;
}

function ErrorNotice({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800" role="alert">
      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
      {children}
    </h3>
  );
}

function ClaimList({
  claims,
  empty,
  onOpenSource,
}: {
  claims: AnalysisClaim[];
  empty: string;
  onOpenSource: (source: AnalysisSourceRef) => void;
}) {
  if (claims.length === 0) {
    return <p className="text-sm text-muted-foreground">{empty}</p>;
  }
  return (
    <ul className="flex flex-col gap-3">
      {claims.map((claim, index) => (
        <li key={`${claim.claim_type}-${index}`} className="rounded-md border border-border bg-card p-3">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <p className="max-w-[75ch] text-sm text-foreground">{claim.claim}</p>
            <SupportBadge support={claim.support} />
          </div>
          {claim.sources.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {claim.sources.map((source, sourceIndex) => (
                <Button
                  key={`${source.document_id}-${source.page_number}-${sourceIndex}`}
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 gap-1 text-[11px]"
                  onClick={() => onOpenSource(source)}
                >
                  <FileSearch className="h-3 w-3" aria-hidden="true" />
                  {source.document_name} · p.{source.page_number}
                  {source.quote_verified ? " · quote verified" : ""}
                </Button>
              ))}
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}

// ---------------------------------------------------------------------------
// Source viewer
// ---------------------------------------------------------------------------

function SourceDialog({
  caseId,
  source,
  onClose,
}: {
  caseId: string;
  source: AnalysisSourceRef | null;
  onClose: () => void;
}) {
  const textQuery = useQuery({
    queryKey: ["analysis-source", caseId, source?.document_id, source?.page_number],
    queryFn: () =>
      getDocumentText(caseId, source!.document_id, {
        page: source!.page_number,
        max_pages: 1,
      }),
    enabled: source !== null,
    select: (envelope) => envelope.data,
  });

  const chunk = textQuery.data?.chunks.find(
    (item) => item.page_number === source?.page_number,
  );

  return (
    <Dialog open={source !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {source?.document_name} — page {source?.page_number}
          </DialogTitle>
          <DialogDescription>
            Extracted document text is untrusted source material. It is shown for verification only.
          </DialogDescription>
        </DialogHeader>

        {source?.quote && (
          <div className="rounded-md border border-teal-200 bg-teal-50 px-3 py-2 text-sm text-teal-900">
            <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-teal-700">
              Model-supplied quote {source.quote_verified ? "(verified in source)" : "(not found verbatim)"}
            </p>
            <p className="italic">&ldquo;{source.quote}&rdquo;</p>
          </div>
        )}

        {textQuery.isLoading && <Skeleton className="h-32 w-full" />}
        {textQuery.isError && (
          <ErrorNotice
            message={
              textQuery.error instanceof ApiClientError
                ? textQuery.error.message
                : "Could not load the source page."
            }
          />
        )}
        {chunk && (
          <div className="max-h-[50vh] overflow-y-auto rounded-md border border-border bg-muted/30 p-3">
            <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-relaxed text-foreground">
              {chunk.extracted_text}
            </pre>
          </div>
        )}
        {!textQuery.isLoading && !textQuery.isError && !chunk && source && (
          <p className="text-sm text-muted-foreground">
            This page is not available in the extracted text.
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Result view
// ---------------------------------------------------------------------------

function AnalysisResultView({
  result,
  onOpenSource,
}: {
  result: CaseAnalysisResult;
  onOpenSource: (source: AnalysisSourceRef) => void;
}) {
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="secondary">
          {result.provider} / {result.model}
        </Badge>
        {result.is_mock ? (
          <Badge variant="warning">Development fixture — no AI model was called</Badge>
        ) : (
          <Badge variant="outline">AI-generated — requires professional verification</Badge>
        )}
        <span className="text-xs text-muted-foreground">
          {result.verification.total_claims} claim(s) ·{" "}
          {result.verification.supported} supported ·{" "}
          {result.verification.partially_supported} partial ·{" "}
          {result.verification.unsupported} unsupported
        </span>
      </div>

      <div>
        <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
          <span>Source verification score</span>
          <span>{verificationRate(result)}%</span>
        </div>
        <Progress value={verificationRate(result)} aria-label="Source verification score" />
      </div>

      {result.insufficient_sources && (
        <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>
            No usable extracted text was available. Add a document with completed
            text extraction, then run the analysis again.
          </span>
        </div>
      )}

      <div>
        <SectionTitle>Summary</SectionTitle>
        <p className="mt-1.5 whitespace-pre-wrap text-sm leading-relaxed text-foreground/90">
          {result.summary}
        </p>
      </div>

      {result.parties.length > 0 && (
        <div>
          <SectionTitle>Parties identified in the documents</SectionTitle>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {result.parties.map((party, index) => (
              <Badge key={`${party}-${index}`} variant="secondary">{party}</Badge>
            ))}
          </div>
        </div>
      )}

      <Separator />

      <div>
        <SectionTitle>Facts</SectionTitle>
        <div className="mt-1.5">
          <ClaimList claims={result.facts} empty="No facts were extracted." onOpenSource={onOpenSource} />
        </div>
      </div>

      <div>
        <SectionTitle>Legal issues raised by the documents</SectionTitle>
        <div className="mt-1.5">
          <ClaimList
            claims={result.legal_issues}
            empty="No legal issues were extracted."
            onOpenSource={onOpenSource}
          />
        </div>
      </div>

      {result.timeline.length > 0 && (
        <div>
          <SectionTitle>Timeline</SectionTitle>
          <ul className="mt-1.5 flex flex-col gap-2">
            {result.timeline.map((event, index) => (
              <li key={`${event.date_text}-${index}`} className="rounded-md border border-border bg-card p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-teal-700">{event.date_text}</span>
                  <SupportBadge support={event.support} />
                </div>
                <p className="mt-1 text-sm text-foreground">{event.event}</p>
                {event.sources.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {event.sources.map((source, sourceIndex) => (
                      <Button
                        key={`${source.document_id}-${source.page_number}-${sourceIndex}`}
                        type="button"
                        variant="outline"
                        size="sm"
                        className="h-7 gap-1 text-[11px]"
                        onClick={() => onOpenSource(source)}
                      >
                        <FileSearch className="h-3 w-3" aria-hidden="true" />
                        {source.document_name} · p.{source.page_number}
                      </Button>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <SectionTitle>Model inferences (not direct statements)</SectionTitle>
        <div className="mt-1.5">
          <ClaimList
            claims={result.inferences}
            empty="No separate inferences were recorded."
            onOpenSource={onOpenSource}
          />
        </div>
      </div>

      {result.unverified_hypotheses.length > 0 && (
        <div>
          <SectionTitle>Unverified hypotheses</SectionTitle>
          <ul className="mt-1.5 list-disc space-y-1 pl-5 text-sm text-amber-900">
            {result.unverified_hypotheses.map((item, index) => (
              <li key={`${item}-${index}`}>{item}</li>
            ))}
          </ul>
        </div>
      )}

      {result.missing_information.length > 0 && (
        <div>
          <SectionTitle>Missing information</SectionTitle>
          <ul className="mt-1.5 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            {result.missing_information.map((item, index) => (
              <li key={`${item}-${index}`}>{item}</li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <SectionTitle>Limitations and verification notes</SectionTitle>
        <ul className="mt-1.5 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
          {[...result.limitations, ...result.verification.notes].map((item, index) => (
            <li key={`${item}-${index}`}>{item}</li>
          ))}
        </ul>
      </div>

      {result.source_manifest.length > 0 && (
        <details className="rounded-md border border-border bg-muted/20 px-3 py-2">
          <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Sources supplied to the analyst ({result.source_manifest.length} page excerpts)
          </summary>
          <ul className="mt-2 flex flex-col gap-1 text-xs text-muted-foreground">
            {result.source_manifest.map((source) => (
              <li key={source.source_id}>
                <span className="font-mono">{source.source_id}</span> · {source.document_name} · p.
                {source.page_number}
                {source.truncated ? " (truncated)" : ""}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------

export function AnalysisPanel({
  caseId,
  documentCount,
}: {
  caseId: string;
  documentCount: number;
}) {
  const queryClient = useQueryClient();
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [focus, setFocus] = useState("");
  const [source, setSource] = useState<AnalysisSourceRef | null>(null);

  const aiQuery = useQuery({
    queryKey: ["ai-status"],
    queryFn: getAIStatus,
    select: (envelope) => envelope.data,
    staleTime: 60_000,
  });

  const listQuery = useQuery({
    queryKey: ["case-analysis-list", caseId],
    queryFn: () => listCaseAnalyses(caseId, 20),
    select: (envelope) => envelope.data,
  });

  // Select the most recent run once, unless the user has started another.
  useEffect(() => {
    if (!workflowId && listQuery.data?.items.length) {
      setWorkflowId(listQuery.data.items[0].id);
    }
  }, [listQuery.data, workflowId]);

  const runQuery = useQuery({
    queryKey: ["case-analysis", caseId, workflowId],
    queryFn: () => getCaseAnalysis(caseId, workflowId as string),
    enabled: workflowId !== null,
    select: (envelope) => envelope.data,
    refetchInterval: (query) => {
      const run = query.state.data?.data;
      return run && isWorkflowActive(run.status) ? 2000 : false;
    },
  });

  const run = runQuery.data ?? null;

  const startMutation = useMutation({
    mutationFn: () =>
      startCaseAnalysis(caseId, { focus: focus.trim() ? focus.trim() : null }),
    onSuccess: (envelope) => {
      if (envelope.data) setWorkflowId(envelope.data.id);
      void queryClient.invalidateQueries({ queryKey: ["case-analysis-list", caseId] });
    },
  });

  const retryMutation = useMutation({
    mutationFn: () => retryCaseAnalysis(caseId, workflowId as string),
    onSuccess: () => {
      void runQuery.refetch();
      void queryClient.invalidateQueries({ queryKey: ["case-analysis-list", caseId] });
    },
  });

  const active = run ? isWorkflowActive(run.status) : false;
  const actionError = useMemo(() => {
    const error = startMutation.error ?? retryMutation.error;
    if (!error) return null;
    return error instanceof ApiClientError ? error.message : "The request failed. Try again.";
  }, [startMutation.error, retryMutation.error]);

  const ai = aiQuery.data;
  const busy = startMutation.isPending || retryMutation.isPending;

  return (
    <div className="flex flex-col gap-4">
      {/* Provider status */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Brain className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
            Case Intelligence workflow
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {aiQuery.isLoading && <Skeleton className="h-4 w-64" />}
          {aiQuery.isError && (
            <ErrorNotice
              message={
                aiQuery.error instanceof ApiClientError
                  ? aiQuery.error.message
                  : "Could not read AI provider status."
              }
            />
          )}
          {ai && (
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <Badge variant="outline">{ai.provider} / {ai.model}</Badge>
              {ai.is_mock && <Badge variant="warning">Fixture mode</Badge>}
              <span>{ai.message}</span>
            </div>
          )}

          <p className="text-xs text-muted-foreground">
            {documentCount === 0
              ? "No documents are attached. The analysis will report insufficient sources rather than inventing facts."
              : `The analyst reads extracted text from the case's ready documents (${documentCount} attached), cites document IDs and page numbers, and a deterministic verifier checks every quote. No external legal authorities are retrieved.`}
          </p>

          <div className="flex flex-col gap-2">
            <label htmlFor="analysis-focus" className="text-xs font-medium text-foreground">
              Optional focus (treated as untrusted input)
            </label>
            <textarea
              id="analysis-focus"
              value={focus}
              onChange={(event) => setFocus(event.target.value)}
              maxLength={1000}
              rows={2}
              disabled={busy || active}
              placeholder="e.g. Focus on the termination clause and notice dates."
              className="w-full resize-y rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
            />
            <div className="flex flex-wrap items-center gap-2">
              <Button
                type="button"
                size="sm"
                disabled={busy || active || !ai?.configured}
                onClick={() => startMutation.mutate()}
              >
                {startMutation.isPending ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                ) : (
                  <Brain className="h-3.5 w-3.5" aria-hidden="true" />
                )}
                {active ? "Analysis in progress" : "Run analysis"}
              </Button>
              {run?.status === "failed" && (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={busy}
                  onClick={() => retryMutation.mutate()}
                >
                  {retryMutation.isPending ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                  ) : (
                    <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                  )}
                  Retry failed run
                </Button>
              )}
              {run && (
                <span className="text-xs text-muted-foreground">
                  Run {run.id.slice(0, 8)} · attempt {run.attempt_count}
                </span>
              )}
            </div>
            {actionError && <ErrorNotice message={actionError} />}
          </div>
        </CardContent>
      </Card>

      {/* Progress */}
      {run && (active || run.status === "failed") && (
        <Card>
          <CardContent className="flex flex-col gap-3 pt-6">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <StatusBadge status={run.status} />
                <span className="text-xs text-muted-foreground">
                  {run.current_step ? `Step: ${run.current_step}` : "Waiting for the runner"}
                </span>
              </div>
              <span className="text-xs text-muted-foreground">{run.progress}%</span>
            </div>
            <Progress value={run.progress} aria-label="Analysis progress" />
            {run.steps.length > 0 && (
              <ul className="flex flex-col gap-1 text-xs text-muted-foreground">
                {run.steps.slice(-5).map((step, index) => (
                  <li key={`${step.step}-${step.at}-${index}`} className="flex items-center gap-1.5">
                    <Clock className="h-3 w-3" aria-hidden="true" />
                    <span className="font-mono">{step.step}</span>
                    {step.message ? <span>— {step.message}</span> : null}
                  </li>
                ))}
              </ul>
            )}
            {run.error && (
              <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-900">
                <p className="font-medium">Analysis failed ({run.error.code})</p>
                <p className="mt-0.5 text-xs">{run.error.message}</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Results */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center justify-between gap-2 text-sm">
            <span className="flex items-center gap-2">
              <ArrowUpRight className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
              Analysis result
            </span>
            {run && <StatusBadge status={run.status} />}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {listQuery.isLoading && <Skeleton className="h-24 w-full" />}
          {listQuery.isError && (
            <ErrorNotice
              message={
                listQuery.error instanceof ApiClientError
                  ? listQuery.error.message
                  : "Could not load previous analyses."
              }
            />
          )}
          {!listQuery.isLoading && !run && (
            <div className="flex flex-col items-center gap-2 py-8 text-center">
              <Brain className="h-6 w-6 text-muted-foreground" aria-hidden="true" />
              <p className="text-sm font-medium text-foreground">No analysis yet</p>
              <p className="max-w-md text-xs text-muted-foreground">
                Run the workflow to extract source-linked facts and legal issues from
                the documents in this case. Every claim is checked against the cited page.
              </p>
            </div>
          )}
          {run && active && !run.result && (
            <p className="py-6 text-center text-sm text-muted-foreground">
              The workflow is running. This panel refreshes automatically.
            </p>
          )}
          {run?.result && (
            <AnalysisResultView result={run.result} onOpenSource={setSource} />
          )}
        </CardContent>
      </Card>

      <SourceDialog caseId={caseId} source={source} onClose={() => setSource(null)} />
    </div>
  );
}
