"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeftRight,
  Download,
  FileText,
  Gavel,
  Loader2,
  Play,
  RefreshCw,
  Scale,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import type {
  AdvocateArgument,
  AdvocatePreferredSide,
  AdvocateResult,
  Document,
  WorkflowRun,
} from "@nyayasaar/shared";
import {
  downloadCaseReport,
  isWorkflowActive,
  listAdvocateAnalyses,
  retryCaseAnalysis,
  saveBlob,
  startAdvocateAnalysis,
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
  ModeLegend,
  SideBadge,
  SourceEvidenceList,
  SupportBadge,
  TierBadge,
  VerificationStrip,
} from "@/components/shared/mode-ui";

const SIDE_LABELS: Record<AdvocatePreferredSide, string> = {
  both: "Both sides (balanced)",
  claimant: "Claimant / Petitioner",
  respondent: "Respondent / Defendant",
};

function isAdvocateResult(run: WorkflowRun | undefined): AdvocateResult | null {
  if (!run || run.status !== "completed" || !run.result) return null;
  if (!("claimant_arguments" in run.result)) return null;
  return run.result as AdvocateResult;
}

function ArgumentCard({ argument }: { argument: AdvocateArgument }) {
  return (
    <article className="rounded-lg border border-border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
            <span className="font-mono font-semibold text-foreground">
              {argument.argument_id}
            </span>
            <SideBadge side={argument.side} />
            {argument.issue && <span>Issue: {argument.issue}</span>}
          </div>
          <h4 className="mt-1.5 text-sm font-semibold leading-snug text-foreground">
            {argument.claim}
          </h4>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <TierBadge tier={argument.tier} />
          <SupportBadge support={argument.support} />
        </div>
      </div>

      <div className="mt-3 rounded-md border border-border bg-muted/20 p-3">
        <p className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          <Sparkles className="h-3 w-3" aria-hidden="true" />
          AI reasoning — verify before reliance
        </p>
        <p className="mt-1.5 text-xs leading-relaxed text-foreground/90">
          {argument.reasoning || "No reasoning supplied."}
        </p>
      </div>

      {argument.counterarguments.length > 0 && (
        <div className="mt-3 rounded-md border border-amber-200 bg-amber-50/50 p-3">
          <p className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-amber-800">
            <ArrowLeftRight className="h-3 w-3" aria-hidden="true" />
            Anticipated counterarguments
          </p>
          <ul className="mt-1.5 list-disc space-y-1 pl-4 text-xs text-amber-950">
            {argument.counterarguments.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
        </div>
      )}

      {argument.evidentiary_gap && (
        <div className="mt-3 flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/5 p-2.5 text-xs text-destructive">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          <span>
            <strong>Evidentiary gap:</strong>{" "}
            {argument.gap_description || "Supporting evidence is missing or partial."}
          </span>
        </div>
      )}

      <div className="mt-3 grid gap-2">
        <SourceEvidenceList refs={argument.supporting_sources} />
        {argument.opposing_sources.length > 0 && (
          <SourceEvidenceList
            refs={argument.opposing_sources}
            label="Contrary source evidence"
            tone="contrary"
          />
        )}
      </div>

      {argument.authority_refs.length > 0 && (
        <div className="mt-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Retrieved authorities cited
          </p>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {argument.authority_refs.map((ref, index) => (
              <Badge key={`${ref}-${index}`} variant="outline" className="font-mono text-[10px]">
                {ref}
              </Badge>
            ))}
          </div>
          <p className="mt-1 text-[10px] text-muted-foreground">
            Authority text is available in the run source manifest. Precedential
            status is never asserted without reliable corpus data.
          </p>
        </div>
      )}
    </article>
  );
}

function SideColumn({
  title,
  description,
  arguments: items,
  preferred,
}: {
  title: string;
  description: string;
  arguments: AdvocateArgument[];
  preferred: boolean;
}) {
  return (
    <section
      className={`rounded-lg border p-4 ${
        preferred ? "border-ink-300 bg-ink-50/40" : "border-border bg-muted/10"
      }`}
      aria-label={title}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="font-serif text-base font-semibold text-foreground">{title}</h3>
          <p className="text-xs text-muted-foreground">{description}</p>
        </div>
        <div className="flex items-center gap-1.5">
          {preferred && <Badge variant="secondary">Selected focus</Badge>}
          <Badge variant="outline">{items.length} argument(s)</Badge>
        </div>
      </div>
      <div className="mt-3 space-y-3">
        {items.length === 0 ? (
          <p className="rounded-md border border-dashed border-border p-4 text-xs text-muted-foreground">
            No arguments were generated for this side from the available record.
          </p>
        ) : (
          items.map((argument) => (
            <ArgumentCard key={argument.argument_id} argument={argument} />
          ))
        )}
      </div>
    </section>
  );
}

export function AdvocatePanel({ caseId }: { caseId?: string }) {
  const queryClient = useQueryClient();
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [focus, setFocus] = useState("");
  const [preferredSide, setPreferredSide] =
    useState<AdvocatePreferredSide>("both");
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const docsQuery = useQuery({
    queryKey: ["documents", caseId],
    queryFn: () => listDocuments(caseId!),
    enabled: Boolean(caseId),
    select: (env) => env.data?.items ?? [],
  });

  const runsQuery = useQuery({
    queryKey: ["analysis", "advocate", caseId],
    queryFn: () => listAdvocateAnalyses(caseId!, 15),
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
      startAdvocateAnalysis(caseId!, {
        document_ids: selectedDocIds.length > 0 ? selectedDocIds : undefined,
        focus: focus.trim() || undefined,
        preferred_side: preferredSide,
      }),
    onSuccess: (env) => {
      if (env.data) setActiveRunId(env.data.id);
      void queryClient.invalidateQueries({
        queryKey: ["analysis", "advocate", caseId],
      });
    },
  });

  const retryMutation = useMutation({
    mutationFn: (workflowId: string) => retryCaseAnalysis(caseId!, workflowId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["analysis", "advocate", caseId],
      });
    },
  });

  const result = useMemo(() => isAdvocateResult(activeRun), [activeRun]);

  const allArguments = useMemo(
    () => [
      ...(result?.claimant_arguments ?? []),
      ...(result?.respondent_arguments ?? []),
    ],
    [result],
  );

  const strongest = useMemo(
    () =>
      allArguments.filter(
        (a) => a.tier === "strong_supported" && a.support !== "unsupported",
      ),
    [allArguments],
  );

  const speculative = useMemo(
    () =>
      allArguments.filter(
        (a) => a.tier === "speculative" || a.support === "unsupported",
      ),
    [allArguments],
  );

  const sideOrder: Array<"claimant" | "respondent"> =
    result?.preferred_side === "respondent"
      ? ["respondent", "claimant"]
      : ["claimant", "respondent"];

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
          <Scale className="h-8 w-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            Select a case workspace to prepare a two-sided argument analysis.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-ink-200 bg-ink-50/60 p-4 text-sm">
        <div className="flex items-start gap-3">
          <Scale className="mt-0.5 h-4 w-4 shrink-0 text-ink-700" aria-hidden="true" />
          <div className="space-y-1">
            <p className="font-semibold text-ink-900">
              Both sides are prepared. A side focus adds depth — it never hides
              contrary material.
            </p>
            <p className="text-xs text-ink-800/80">
              Advocate Mode is a research and argument-preparation tool. It is not
              legal advice, does not replace counsel, and never files or submits
              documents.
            </p>
          </div>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Scale className="h-4 w-4 text-ink-700" />
            Prepare arguments
          </CardTitle>
          <CardDescription>
            The workflow reads only the selected case documents plus any legal
            records available from the configured corpus.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-3">
            <div className="md:col-span-2">
              <label htmlFor="advocate-focus" className="mb-1 block text-xs font-medium">
                Issue or argument focus (optional)
              </label>
              <Input
                id="advocate-focus"
                placeholder="e.g., enforceability of Clause 4, limitation, fiduciary accounting..."
                value={focus}
                onChange={(e) => setFocus(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="advocate-side" className="mb-1 block text-xs font-medium">
                Side focus
              </label>
              <select
                id="advocate-side"
                value={preferredSide}
                onChange={(e) =>
                  setPreferredSide(e.target.value as AdvocatePreferredSide)
                }
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
              >
                {(Object.keys(SIDE_LABELS) as AdvocatePreferredSide[]).map((side) => (
                  <option key={side} value={side}>
                    {SIDE_LABELS[side]}
                  </option>
                ))}
              </select>
            </div>
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
              Run Advocate Mode
            </Button>
            <p className="text-[11px] text-muted-foreground">
              Requires at least one document with extracted text.
            </p>
          </div>

          {startMutation.isError && (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
              Could not start Advocate Mode:{" "}
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
                    aria-label="Select advocate run"
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
                  <span>{activeRun.error?.message || "Advocate run failed."}</span>
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
                    {result.selected_issue || "Argument preparation brief"}
                  </CardTitle>
                  <CardDescription>
                    Side focus: {SIDE_LABELS[result.preferred_side] ?? result.preferred_side}{" "}
                    · Provider: {result.provider}/{result.model}
                  </CardDescription>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {result.is_mock && <Badge variant="warning">Development fixture</Badge>}
                  <Badge variant="outline">Advocate v{result.workflow_version}</Badge>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <ModeLegend />
              <p className="text-sm leading-relaxed text-foreground/90">{result.summary}</p>
              <VerificationStrip verification={result.verification} />
              {result.insufficient_sources && (
                <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                  No usable extracted document text was available. Upload and process
                  documents, then run Advocate Mode again.
                </div>
              )}
            </CardContent>
          </Card>

          {result.relevant_facts.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Facts selected for argument</CardTitle>
                <CardDescription>
                  Model-selected facts. Verify each against the linked document pages
                  before relying on it.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ol className="space-y-2">
                  {result.relevant_facts.map((fact, index) => (
                    <li key={index} className="flex gap-3 text-sm">
                      <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-secondary text-[10px] font-semibold text-muted-foreground">
                        {index + 1}
                      </span>
                      <span className="text-foreground/90">{fact}</span>
                    </li>
                  ))}
                </ol>
              </CardContent>
            </Card>
          )}

          <div className="grid gap-4 xl:grid-cols-2">
            {sideOrder.map((side) => (
              <SideColumn
                key={side}
                title={side === "claimant" ? "Claimant / Petitioner" : "Respondent / Defendant"}
                description={
                  side === "claimant"
                    ? "Affirmative case, relief sought, and supporting record."
                    : "Defence, contrary material, and weaknesses in the claim."
                }
                arguments={
                  side === "claimant"
                    ? result.claimant_arguments
                    : result.respondent_arguments
                }
                preferred={result.preferred_side === side}
              />
            ))}
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-sm">
                  <Gavel className="h-4 w-4 text-teal-700" />
                  Strongest supported points ({strongest.length})
                </CardTitle>
                <CardDescription>
                  Points classified as strongly supported and linked to verified
                  evidence.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {strongest.length === 0 ? (
                  <p className="text-xs text-muted-foreground">
                    No argument reached the strongly supported tier. Treat the analysis
                    as preparatory only.
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {strongest.map((argument) => (
                      <li key={argument.argument_id} className="text-xs">
                        <span className="font-mono text-[10px] text-muted-foreground">
                          {argument.argument_id}
                        </span>{" "}
                        <span className="font-medium text-foreground">
                          {argument.claim}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-sm">
                  <ShieldAlert className="h-4 w-4 text-amber-700" />
                  Speculative or unsupported ({speculative.length})
                </CardTitle>
                <CardDescription>
                  Preserved explicitly so they are not mistaken for established points.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {speculative.length === 0 ? (
                  <p className="text-xs text-muted-foreground">
                    No speculative arguments were classified in this run.
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {speculative.map((argument) => (
                      <li key={argument.argument_id} className="text-xs">
                        <span className="font-mono text-[10px] text-muted-foreground">
                          {argument.argument_id}
                        </span>{" "}
                        <span className="text-foreground/90">{argument.claim}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">
                  Evidentiary gaps ({result.evidentiary_gaps.length})
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {result.evidentiary_gaps.length === 0 ? (
                  <p className="text-xs text-muted-foreground">
                    No evidentiary gaps were recorded.
                  </p>
                ) : (
                  result.evidentiary_gaps.map((gap, index) => (
                    <div key={index} className="rounded-md border border-amber-200 bg-amber-50/50 p-3">
                      <p className="text-xs font-medium text-amber-950">
                        {gap.missing_evidence_type}: {gap.description}
                      </p>
                      {gap.affected_claim && (
                        <p className="mt-1 text-[11px] text-amber-900">
                          Affects: {gap.affected_claim}
                        </p>
                      )}
                      {gap.source_refs.length > 0 && (
                        <div className="mt-2">
                          <SourceEvidenceList
                            refs={gap.source_refs}
                            label="Related source evidence"
                          />
                        </div>
                      )}
                    </div>
                  ))
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Unresolved legal questions</CardTitle>
              </CardHeader>
              <CardContent>
                {result.unresolved_questions.length === 0 ? (
                  <p className="text-xs text-muted-foreground">
                    No unresolved questions were recorded.
                  </p>
                ) : (
                  <ul className="list-disc space-y-1.5 pl-4 text-xs text-foreground/90">
                    {result.unresolved_questions.map((question, index) => (
                      <li key={index}>{question}</li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Record strengths</CardTitle>
              </CardHeader>
              <CardContent>
                {result.strengths.length === 0 ? (
                  <p className="text-xs text-muted-foreground">None recorded.</p>
                ) : (
                  <ul className="list-disc space-y-1 pl-4 text-xs text-foreground/90">
                    {result.strengths.map((item, index) => (
                      <li key={index}>{item}</li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Record weaknesses</CardTitle>
              </CardHeader>
              <CardContent>
                {result.weaknesses.length === 0 ? (
                  <p className="text-xs text-muted-foreground">None recorded.</p>
                ) : (
                  <ul className="list-disc space-y-1 pl-4 text-xs text-foreground/90">
                    {result.weaknesses.map((item, index) => (
                      <li key={index}>{item}</li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Verification, limitations &amp; provenance</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-xs text-muted-foreground">
                {result.research_tool_disclaimer}
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
              <Scale className="h-8 w-8 text-muted-foreground" />
              <div>
                <p className="text-sm font-medium text-foreground">
                  No argument brief yet
                </p>
                <p className="mt-1 max-w-md text-xs text-muted-foreground">
                  Run Advocate Mode to generate a two-sided, source-linked argument
                  preparation brief. Every factual and legal assertion will be marked
                  as supported, partially supported, or unsupported.
                </p>
              </div>
            </CardContent>
          </Card>
        )
      )}
    </div>
  );
}
