"use client";

/**
 * Case Intelligence workspace — Stage 6.
 *
 * Everything shown here comes from the API. Long-running analysis is queued
 * server-side and polled; there are no simulated buttons, fake progress bars,
 * or placeholder results. Development-fixture output is explicitly labelled.
 *
 * Design principles:
 * - Source facts, model inferences, and open questions are visually separated.
 * - Every citation opens the real document page. If the verifier could not
 *   locate a quote, the UI says so instead of implying verification.
 * - The export buttons download the persisted, verified result only.
 */

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowUpRight,
  Brain,
  CheckCircle2,
  Clock,
  Download,
  FileSearch,
  FileText,
  Gavel,
  HelpCircle,
  Landmark,
  Loader2,
  Printer,
  RefreshCw,
  Scale,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Users,
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
  downloadCaseReport,
  getAIStatus,
  getCaseAnalysis,
  isWorkflowActive,
  listCaseAnalyses,
  retryCaseAnalysis,
  saveBlob,
  startCaseAnalysis,
  supportLabel,
  verificationRate,
  workflowStatusLabel,
} from "@/lib/api/analysis";
import { formatFileSize, getDocumentText, listDocuments } from "@/lib/api/documents";
import { ApiClientError } from "@/lib/api-client";
import type {
  AnalysisAmount,
  AnalysisClaim,
  AnalysisEntity,
  AnalysisEvidenceQuestion,
  AnalysisLegalIssue,
  AnalysisParty,
  AnalysisProceduralEvent,
  AnalysisSourceRef,
  AnalysisSupport,
  AnalysisTimelineEvent,
  AnalysisUncertainty,
  CaseAnalysisResult,
  Document,
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
  if (support === "supported")
    return <Badge variant="success">{supportLabel(support)}</Badge>;
  if (support === "partially_supported")
    return <Badge variant="warning">{supportLabel(support)}</Badge>;
  return <Badge variant="destructive">{supportLabel(support)}</Badge>;
}

function SeverityBadge({ severity }: { severity: "high" | "medium" | "low" }) {
  if (severity === "high") return <Badge variant="destructive">High uncertainty</Badge>;
  if (severity === "medium") return <Badge variant="warning">Medium uncertainty</Badge>;
  return <Badge variant="secondary">Low uncertainty</Badge>;
}

function ErrorNotice({ message }: { message: string }) {
  return (
    <div
      className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800"
      role="alert"
    >
      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}

function SectionHeading({
  icon,
  title,
  count,
  hint,
}: {
  icon?: React.ReactNode;
  title: string;
  count?: number;
  hint?: string;
}) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-2">
      <h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {icon}
        {title}
        {typeof count === "number" && (
          <span className="rounded-full bg-secondary px-1.5 text-[10px] font-medium text-muted-foreground">
            {count}
          </span>
        )}
      </h3>
      {hint && <p className="text-[11px] text-muted-foreground">{hint}</p>}
    </div>
  );
}

function sourceKey(source: AnalysisSourceRef, index: number): string {
  return `${source.document_id}-${source.page_number}-${source.source_id}-${index}`;
}

function SourceChips({
  sources,
  onOpenSource,
}: {
  sources: AnalysisSourceRef[];
  onOpenSource: (source: AnalysisSourceRef) => void;
}) {
  if (sources.length === 0) {
    return (
      <p className="mt-2 text-[11px] text-amber-800">
        No source reference was verified for this item.
      </p>
    );
  }
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {sources.map((source, index) => (
        <Button
          key={sourceKey(source, index)}
          type="button"
          variant="outline"
          size="sm"
          className="h-7 gap-1 text-[11px]"
          onClick={() => onOpenSource(source)}
          title={
            source.quote_verified
              ? "Quote verified against the extracted page text"
              : "Source cited, but the quote was not found verbatim"
          }
        >
          <FileSearch className="h-3 w-3" aria-hidden="true" />
          <span className="font-mono">{source.source_id}</span>
          <span className="max-w-[16rem] truncate">
            {source.document_name} · p.{source.page_number}
          </span>
          {source.quote_verified ? (
            <ShieldCheck className="h-3 w-3 text-teal-700" aria-label="quote verified" />
          ) : (
            <AlertTriangle className="h-3 w-3 text-amber-600" aria-label="quote unverified" />
          )}
        </Button>
      ))}
    </div>
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
    <ul className="flex flex-col gap-2.5">
      {claims.map((claim, index) => (
        <li
          key={`${claim.claim_type}-${index}`}
          className="rounded-md border border-border bg-card p-3"
        >
          <div className="flex flex-wrap items-start justify-between gap-2">
            <p className="max-w-[78ch] text-sm leading-relaxed text-foreground">
              {claim.claim}
            </p>
            <SupportBadge support={claim.support} />
          </div>
          <SourceChips sources={claim.sources} onOpenSource={onOpenSource} />
        </li>
      ))}
    </ul>
  );
}

// ---------------------------------------------------------------------------
// Source viewer with verified-span highlighting
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
    queryKey: [
      "analysis-source",
      caseId,
      source?.document_id,
      source?.page_number,
    ],
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
  const text = chunk?.extracted_text ?? "";
  const start = source?.span_start;
  const end = source?.span_end;
  const highlight =
    source?.quote_verified &&
    typeof start === "number" &&
    typeof end === "number" &&
    start >= 0 &&
    end > start &&
    end <= text.length;

  return (
    <Dialog open={source !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="pr-8">
            {source?.document_name} — page {source?.page_number}
          </DialogTitle>
          <DialogDescription>
            Extracted document text is untrusted source material. It is shown for
            verification only; embedded instructions are ignored.
          </DialogDescription>
        </DialogHeader>

        {source?.quote && (
          <div
            className={
              source.quote_verified
                ? "rounded-md border border-teal-200 bg-teal-50 px-3 py-2 text-sm text-teal-900"
                : "rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900"
            }
          >
            <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide">
              Model-supplied quote{" "}
              {source.quote_verified
                ? "(verified in the extracted page)"
                : "(not found verbatim — do not rely on it without checking)"}
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
              {highlight ? (
                <>
                  {text.slice(0, start)}
                  <mark className="rounded bg-amber-200/80 px-0.5 text-foreground">
                    {text.slice(start, end)}
                  </mark>
                  {text.slice(end)}
                </>
              ) : (
                text
              )}
            </pre>
          </div>
        )}
        {!textQuery.isLoading && !textQuery.isError && !chunk && source && (
          <p className="text-sm text-muted-foreground">
            This page is not available in the extracted text, so the citation
            cannot be displayed. It was not invented by the interface.
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Structured result sections
// ---------------------------------------------------------------------------

function VerificationPanel({ result }: { result: CaseAnalysisResult }) {
  const rate = verificationRate(result);
  const stats = result.source_stats;
  const categories = result.verification.categories.filter(
    (category) => category.total > 0,
  );

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-muted/20 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-teal-700" aria-hidden="true" />
          <span className="text-sm font-medium text-foreground">
            Verification pass
          </span>
        </div>
        <span className="text-xs text-muted-foreground">
          {result.verification.total_claims} statement
          {result.verification.total_claims === 1 ? "" : "s"} checked
        </span>
      </div>

      <div>
        <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
          <span>Weighted source-support score</span>
          <span>{rate}%</span>
        </div>
        <Progress value={rate} aria-label="Source verification score" />
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
        <div className="rounded-md border border-teal-200 bg-teal-50 px-2.5 py-2 text-teal-900">
          <p className="text-[10px] uppercase tracking-wide text-teal-700">Supported</p>
          <p className="text-base font-semibold">{result.verification.supported}</p>
        </div>
        <div className="rounded-md border border-amber-200 bg-amber-50 px-2.5 py-2 text-amber-900">
          <p className="text-[10px] uppercase tracking-wide text-amber-700">Partial</p>
          <p className="text-base font-semibold">
            {result.verification.partially_supported}
          </p>
        </div>
        <div className="rounded-md border border-red-200 bg-red-50 px-2.5 py-2 text-red-900">
          <p className="text-[10px] uppercase tracking-wide text-red-700">Unsupported</p>
          <p className="text-base font-semibold">{result.verification.unsupported}</p>
        </div>
        <div className="rounded-md border border-border bg-card px-2.5 py-2 text-foreground">
          <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
            Verified spans
          </p>
          <p className="text-base font-semibold">{result.verification.verified_spans}</p>
        </div>
      </div>

      {categories.length > 0 && (
        <details className="text-xs text-muted-foreground">
          <summary className="cursor-pointer font-medium text-foreground">
            Verification by category
          </summary>
          <ul className="mt-1.5 grid gap-1 sm:grid-cols-2">
            {categories.map((category) => (
              <li key={category.category} className="flex justify-between gap-2">
                <span className="capitalize">{category.category.replace(/_/g, " ")}</span>
                <span>
                  {category.supported} supported · {category.partially_supported} partial ·{" "}
                  {category.unsupported} unsupported
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}

      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px] text-muted-foreground sm:grid-cols-3">
        <span>
          Documents analysed: {stats.documents_analyzed}/{stats.documents_available}
        </span>
        <span>
          Pages included: {stats.pages_included}/{stats.pages_available}
        </span>
        <span>Characters included: {stats.characters_included.toLocaleString()}</span>
        <span>Duplicate pages skipped: {stats.duplicate_pages_skipped}</span>
        <span>Short pages: {stats.short_pages}</span>
        <span>Truncated pages: {stats.truncated_pages}</span>
        <span>OCR required: {stats.ocr_required_documents}</span>
        <span>Incomplete extraction: {stats.incomplete_extraction_documents}</span>
        <span>Invalid source refs rejected: {result.verification.invalid_source_refs}</span>
      </div>

      {result.verification.retried && (
        <p className="text-[11px] text-muted-foreground">
          The verifier rejected unsupported statements once and requested a revision
          before this report was accepted.
        </p>
      )}
    </div>
  );
}

function PartyList({
  parties,
  onOpenSource,
}: {
  parties: AnalysisParty[];
  onOpenSource: (source: AnalysisSourceRef) => void;
}) {
  if (parties.length === 0)
    return <p className="text-sm text-muted-foreground">No parties were extracted.</p>;
  return (
    <ul className="grid gap-2 sm:grid-cols-2">
      {parties.map((party, index) => (
        <li
          key={`${party.name}-${index}`}
          className="rounded-md border border-border bg-card p-3"
        >
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <p className="text-sm font-medium text-foreground">{party.name}</p>
              <p className="text-[11px] text-muted-foreground">
                {party.role ? party.role : "Role not stated in the sources"}
              </p>
            </div>
            <SupportBadge support={party.support} />
          </div>
          <SourceChips sources={party.sources} onOpenSource={onOpenSource} />
        </li>
      ))}
    </ul>
  );
}

function EntityList({
  entities,
  onOpenSource,
}: {
  entities: AnalysisEntity[];
  onOpenSource: (source: AnalysisSourceRef) => void;
}) {
  if (entities.length === 0)
    return <p className="text-sm text-muted-foreground">No named entities were extracted.</p>;
  return (
    <ul className="grid gap-2 sm:grid-cols-2">
      {entities.map((entity, index) => (
        <li
          key={`${entity.name}-${index}`}
          className="rounded-md border border-border bg-card p-3"
        >
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <p className="text-sm font-medium text-foreground">{entity.name}</p>
              <p className="text-[11px] capitalize text-muted-foreground">
                {entity.entity_type.replace(/_/g, " ")}
                {entity.role ? ` · ${entity.role}` : ""}
              </p>
            </div>
            <SupportBadge support={entity.support} />
          </div>
          <SourceChips sources={entity.sources} onOpenSource={onOpenSource} />
        </li>
      ))}
    </ul>
  );
}

function AmountList({
  amounts,
  onOpenSource,
}: {
  amounts: AnalysisAmount[];
  onOpenSource: (source: AnalysisSourceRef) => void;
}) {
  if (amounts.length === 0)
    return <p className="text-sm text-muted-foreground">No amounts were extracted.</p>;
  return (
    <ul className="grid gap-2 sm:grid-cols-2">
      {amounts.map((amount, index) => (
        <li
          key={`${amount.amount_text}-${index}`}
          className="rounded-md border border-border bg-card p-3"
        >
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <p className="text-sm font-semibold text-foreground">{amount.amount_text}</p>
              <p className="text-xs text-muted-foreground">{amount.description}</p>
            </div>
            <SupportBadge support={amount.support} />
          </div>
          <SourceChips sources={amount.sources} onOpenSource={onOpenSource} />
        </li>
      ))}
    </ul>
  );
}

function ProceduralList({
  events,
  onOpenSource,
}: {
  events: AnalysisProceduralEvent[];
  onOpenSource: (source: AnalysisSourceRef) => void;
}) {
  if (events.length === 0)
    return (
      <p className="text-sm text-muted-foreground">
        No procedural history was extracted from the supplied pages.
      </p>
    );
  return (
    <ol className="flex flex-col gap-2.5">
      {events.map((event, index) => (
        <li key={`${event.stage}-${index}`} className="rounded-md border border-border bg-card p-3">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <p className="text-sm font-medium text-foreground">{event.stage}</p>
              <p className="text-[11px] text-muted-foreground">
                {event.date_text ? event.date_text : "Date not stated"}
                {event.forum ? ` · ${event.forum}` : ""}
                {event.date_ambiguous ? " · ambiguous date" : ""}
              </p>
            </div>
            <SupportBadge support={event.support} />
          </div>
          <p className="mt-1 text-sm text-foreground/90">{event.description}</p>
          <SourceChips sources={event.sources} onOpenSource={onOpenSource} />
        </li>
      ))}
    </ol>
  );
}

function ChronologyList({
  events,
  onOpenSource,
}: {
  events: AnalysisTimelineEvent[];
  onOpenSource: (source: AnalysisSourceRef) => void;
}) {
  if (events.length === 0)
    return (
      <p className="text-sm text-muted-foreground">
        No dated events were extracted. Missing dates are not invented.
      </p>
    );
  return (
    <ol className="relative flex flex-col gap-2.5 border-l border-border pl-4">
      {events.map((event, index) => (
        <li key={`${event.date_text}-${index}`} className="relative">
          <span
            className="absolute -left-[21px] top-3 h-2 w-2 rounded-full bg-teal-600"
            aria-hidden="true"
          />
          <div className="rounded-md border border-border bg-card p-3">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="text-sm font-semibold text-teal-800">{event.date_text}</p>
                <p className="text-[11px] capitalize text-muted-foreground">
                  {event.significance}
                  {event.date_precision !== "unknown"
                    ? ` · ${event.date_precision} precision`
                    : " · date not normalised"}
                  {event.date_ambiguous ? " · ambiguous" : ""}
                </p>
              </div>
              <SupportBadge support={event.support} />
            </div>
            <p className="mt-1 text-sm text-foreground">{event.event}</p>
            {event.date_ambiguous && event.date_ambiguity_note && (
              <p className="mt-1 rounded border border-amber-200 bg-amber-50 px-2 py-1 text-[11px] text-amber-900">
                {event.date_ambiguity_note}
              </p>
            )}
            <SourceChips sources={event.sources} onOpenSource={onOpenSource} />
          </div>
        </li>
      ))}
    </ol>
  );
}

function IssueList({
  issues,
  onOpenSource,
}: {
  issues: AnalysisLegalIssue[];
  onOpenSource: (source: AnalysisSourceRef) => void;
}) {
  if (issues.length === 0)
    return (
      <p className="text-sm text-muted-foreground">
        No potential legal issues were identified. This is not a legal opinion.
      </p>
    );
  return (
    <ol className="flex flex-col gap-2.5">
      {issues.map((issue, index) => (
        <li key={`${issue.question}-${index}`} className="rounded-md border border-border bg-card p-3">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <p className="max-w-[78ch] text-sm font-medium text-foreground">
              {issue.question}
            </p>
            <div className="flex flex-wrap items-center gap-1">
              <Badge variant="outline" className="capitalize">
                {issue.issue_type.replace(/_/g, " ")}
              </Badge>
              <SupportBadge support={issue.support} />
            </div>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">{issue.why_it_matters}</p>
          <SourceChips sources={issue.sources} onOpenSource={onOpenSource} />
        </li>
      ))}
    </ol>
  );
}

function EvidenceQuestionList({
  questions,
  onOpenSource,
}: {
  questions: AnalysisEvidenceQuestion[];
  onOpenSource: (source: AnalysisSourceRef) => void;
}) {
  if (questions.length === 0)
    return (
      <p className="text-sm text-muted-foreground">
        No further-evidence questions were identified.
      </p>
    );
  return (
    <ol className="flex flex-col gap-2.5">
      {questions.map((question, index) => (
        <li key={`${question.question}-${index}`} className="rounded-md border border-border bg-card p-3">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <p className="max-w-[78ch] text-sm font-medium text-foreground">
              {question.question}
            </p>
            <SupportBadge support={question.support} />
          </div>
          <p className="mt-1 text-xs text-muted-foreground">{question.why_it_matters}</p>
          <p className="mt-1.5 rounded border border-border bg-muted/30 px-2 py-1 text-[11px] text-foreground/80">
            <span className="font-semibold">Evidence needed:</span>{" "}
            {question.evidence_needed}
          </p>
          <SourceChips sources={question.sources} onOpenSource={onOpenSource} />
        </li>
      ))}
    </ol>
  );
}

function AmbiguityList({
  ambiguities,
  onOpenSource,
}: {
  ambiguities: AnalysisUncertainty[];
  onOpenSource: (source: AnalysisSourceRef) => void;
}) {
  if (ambiguities.length === 0)
    return (
      <p className="text-sm text-muted-foreground">
        No ambiguity was recorded. Absence of a flag is not proof of certainty.
      </p>
    );
  return (
    <ol className="flex flex-col gap-2.5">
      {ambiguities.map((item, index) => (
        <li
          key={`${item.statement}-${index}`}
          className="rounded-md border border-amber-200 bg-amber-50/60 p-3"
        >
          <div className="flex flex-wrap items-start justify-between gap-2">
            <p className="max-w-[78ch] text-sm font-medium text-amber-950">
              {item.statement}
            </p>
            <SeverityBadge severity={item.severity} />
          </div>
          <p className="mt-1 text-xs text-amber-900">{item.reason}</p>
          <SourceChips sources={item.sources} onOpenSource={onOpenSource} />
        </li>
      ))}
    </ol>
  );
}

function ResultView({
  result,
  onOpenSource,
  onExport,
  exporting,
  exportError,
  onRerun,
  rerunning,
}: {
  result: CaseAnalysisResult;
  onOpenSource: (source: AnalysisSourceRef) => void;
  onExport: (format: "html" | "markdown", mode?: "open" | "download") => void;
  exporting: "html" | "markdown" | null;
  exportError: string | null;
  onRerun: () => void;
  rerunning: boolean;
}) {
  const generated = new Date(result.generated_at);
  const legalIssues = result.issue_analysis;

  return (
    <div className="flex flex-col gap-6">
      {/* Header metadata + export */}
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary">
            {result.provider} / {result.model}
          </Badge>
          {result.is_mock ? (
            <Badge variant="warning">Development fixture — no AI model was called</Badge>
          ) : (
            <Badge variant="outline">AI-assisted — requires professional verification</Badge>
          )}
          <span className="text-xs text-muted-foreground">
            Workflow {result.workflow_version} · prompt {result.prompt_version} · schema{" "}
            {result.result_schema_version}
          </span>
          {!Number.isNaN(generated.getTime()) && (
            <span className="text-xs text-muted-foreground">
              Generated {generated.toLocaleString()}
            </span>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={exporting !== null || result.insufficient_sources}
            onClick={() => onExport("html", "open")}
          >
            {exporting === "html" ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
            ) : (
              <Printer className="h-3.5 w-3.5" aria-hidden="true" />
            )}
            Print / save PDF
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={exporting !== null || result.insufficient_sources}
            onClick={() => onExport("html", "download")}
          >
            {exporting === "html" ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
            ) : (
              <Download className="h-3.5 w-3.5" aria-hidden="true" />
            )}
            HTML report
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={exporting !== null || result.insufficient_sources}
            onClick={() => onExport("markdown")}
          >
            {exporting === "markdown" ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
            ) : (
              <FileText className="h-3.5 w-3.5" aria-hidden="true" />
            )}
            Markdown
          </Button>
          <Button type="button" size="sm" variant="ghost" disabled={rerunning} onClick={onRerun}>
            {rerunning ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
            )}
            Run again
          </Button>
        </div>
        {exportError && <ErrorNotice message={exportError} />}
      </div>

      {result.is_mock && (
        <div className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 px-3.5 py-2.5 text-sm text-amber-950">
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>
            <strong>Development fixture.</strong> No AI model was called. The structure
            is real, but the content is deterministic sample text and is not legal
            analysis.
          </span>
        </div>
      )}

      {result.insufficient_sources ? (
        <div className="flex flex-col items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-6 py-10 text-center">
          <FileText className="h-7 w-7 text-amber-700" aria-hidden="true" />
          <p className="text-sm font-medium text-amber-950">Insufficient source text</p>
          <p className="max-w-lg text-xs text-amber-900">
            No usable extracted text was available, so no facts, issues, or dates were
            inferred. Add or repair a document with completed text extraction and run the
            analysis again.
          </p>
        </div>
      ) : (
        <>
          <section className="flex flex-col gap-2">
            <SectionHeading icon={<Sparkles className="h-3.5 w-3.5" aria-hidden="true" />} title="Executive summary" />
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground/90">
              {result.summary}
            </p>
          </section>

          <VerificationPanel result={result} />

          {result.parties.length > 0 && (
            <section className="flex flex-col gap-2">
              <SectionHeading
                icon={<Users className="h-3.5 w-3.5" aria-hidden="true" />}
                title="Parties"
                count={result.parties.length}
              />
              <PartyList parties={result.parties} onOpenSource={onOpenSource} />
            </section>
          )}

          <Separator />

          <section className="flex flex-col gap-2">
            <SectionHeading
              icon={<Users className="h-3.5 w-3.5" aria-hidden="true" />}
              title="Named entities"
              count={result.entities.length}
            />
            <EntityList entities={result.entities} onOpenSource={onOpenSource} />
          </section>

          <section className="flex flex-col gap-2">
            <SectionHeading
              icon={<Landmark className="h-3.5 w-3.5" aria-hidden="true" />}
              title="Amounts"
              count={result.amounts.length}
            />
            <AmountList amounts={result.amounts} onOpenSource={onOpenSource} />
          </section>

          <section className="flex flex-col gap-2">
            <SectionHeading
              icon={<FileText className="h-3.5 w-3.5" aria-hidden="true" />}
              title="Material facts"
              count={result.facts.length}
              hint="Directly supported by the cited pages"
            />
            <ClaimList
              claims={result.facts}
              empty="No facts were extracted from the supplied pages."
              onOpenSource={onOpenSource}
            />
          </section>

          <section className="flex flex-col gap-2">
            <SectionHeading
              icon={<Clock className="h-3.5 w-3.5" aria-hidden="true" />}
              title="Procedural history"
              count={result.procedural_history.length}
            />
            <ProceduralList
              events={result.procedural_history}
              onOpenSource={onOpenSource}
            />
          </section>

          <section className="flex flex-col gap-2">
            <SectionHeading
              icon={<Clock className="h-3.5 w-3.5" aria-hidden="true" />}
              title="Chronology"
              count={result.timeline.length}
              hint="Ordered by normalised date where possible"
            />
            <ChronologyList events={result.timeline} onOpenSource={onOpenSource} />
          </section>

          <Separator />

          <section className="flex flex-col gap-2">
            <SectionHeading
              icon={<Scale className="h-3.5 w-3.5" aria-hidden="true" />}
              title="Potential legal issues"
              count={legalIssues.length}
              hint="Questions for professional review, not conclusions"
            />
            {legalIssues.length > 0 ? (
              <IssueList issues={legalIssues} onOpenSource={onOpenSource} />
            ) : result.legal_issues.length > 0 ? (
              <ClaimList
                claims={result.legal_issues}
                empty="No legal issues were identified."
                onOpenSource={onOpenSource}
              />
            ) : (
              <p className="text-sm text-muted-foreground">
                No potential legal issues were identified. This is not a legal opinion.
              </p>
            )}
          </section>

          <section className="flex flex-col gap-2">
            <SectionHeading
              icon={<HelpCircle className="h-3.5 w-3.5" aria-hidden="true" />}
              title="Questions requiring further evidence"
              count={result.evidence_questions.length}
            />
            <EvidenceQuestionList
              questions={result.evidence_questions}
              onOpenSource={onOpenSource}
            />
          </section>

          <section className="flex flex-col gap-2">
            <SectionHeading
              icon={<AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />}
              title="Ambiguity and uncertainty"
              count={result.ambiguities.length}
            />
            <AmbiguityList
              ambiguities={result.ambiguities}
              onOpenSource={onOpenSource}
            />
          </section>

          <section className="flex flex-col gap-2">
            <SectionHeading
              icon={<Brain className="h-3.5 w-3.5" aria-hidden="true" />}
              title="Model inferences"
              count={result.inferences.length}
              hint="Reasoning beyond a direct statement"
            />
            <ClaimList
              claims={result.inferences}
              empty="No separate model inferences were recorded."
              onOpenSource={onOpenSource}
            />
          </section>

          {result.unverified_hypotheses.length > 0 && (
            <section className="flex flex-col gap-2">
              <SectionHeading title="Unverified hypotheses" count={result.unverified_hypotheses.length} />
              <ul className="list-disc space-y-1 pl-5 text-sm text-amber-900">
                {result.unverified_hypotheses.map((item, index) => (
                  <li key={`${item}-${index}`}>{item}</li>
                ))}
              </ul>
            </section>
          )}

          {result.missing_information.length > 0 && (
            <section className="flex flex-col gap-2">
              <SectionHeading title="Missing information" count={result.missing_information.length} />
              <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                {result.missing_information.map((item, index) => (
                  <li key={`${item}-${index}`}>{item}</li>
                ))}
              </ul>
            </section>
          )}

          <section className="flex flex-col gap-2">
            <SectionHeading title="Limitations and verification notes" />
            <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
              {[...result.verification.notes, ...result.limitations].map((item, index) => (
                <li key={`${item}-${index}`}>{item}</li>
              ))}
            </ul>
          </section>

          {result.source_manifest.length > 0 && (
            <details className="rounded-md border border-border bg-muted/20 px-3 py-2">
              <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Sources supplied to the analysts ({result.source_manifest.length} page
                excerpts)
              </summary>
              <ul className="mt-2 grid gap-1 text-xs text-muted-foreground sm:grid-cols-2">
                {result.source_manifest.map((source) => (
                  <li key={source.source_id}>
                    <span className="font-mono">{source.source_id}</span> ·{" "}
                    {source.document_name} · p.{source.page_number}
                    {source.truncated ? " · truncated" : ""}
                    {source.short ? " · short page" : ""}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

function DocumentSelector({
  documents,
  selected,
  onToggle,
  onSelectAll,
  onClear,
  disabled,
}: {
  documents: Document[];
  selected: string[];
  onToggle: (id: string) => void;
  onSelectAll: () => void;
  onClear: () => void;
  disabled: boolean;
}) {
  const ready = documents.filter((doc) => doc.processing_status === "ready");
  const usingAll = selected.length === 0;

  if (documents.length === 0) {
    return (
      <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
        No documents are attached. The analysis will report insufficient sources rather
        than inventing facts.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          {usingAll
            ? `All ${ready.length} ready document${ready.length === 1 ? "" : "s"} will be analysed.`
            : `${selected.length} of ${ready.length} ready document${
                ready.length === 1 ? "" : "s"
              } selected.`}
        </p>
        <div className="flex items-center gap-1.5">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={disabled || ready.length === 0}
            onClick={onSelectAll}
          >
            Select all
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={disabled || usingAll}
            onClick={onClear}
          >
            Use all
          </Button>
        </div>
      </div>

      <ul className="max-h-56 overflow-y-auto rounded-md border border-border">
        {documents.map((doc) => {
          const isReady = doc.processing_status === "ready";
          const checked = selected.includes(doc.id);
          return (
            <li
              key={doc.id}
              className="flex items-start gap-2.5 border-b border-border px-3 py-2 last:border-b-0"
            >
              <input
                type="checkbox"
                id={`doc-select-${doc.id}`}
                className="mt-0.5 h-4 w-4 rounded border-input accent-teal-600"
                checked={checked}
                disabled={disabled || !isReady}
                onChange={() => onToggle(doc.id)}
              />
              <label
                htmlFor={`doc-select-${doc.id}`}
                className={
                  isReady
                    ? "flex min-w-0 flex-1 cursor-pointer flex-col"
                    : "flex min-w-0 flex-1 cursor-not-allowed flex-col opacity-70"
                }
              >
                <span className="truncate text-sm text-foreground">{doc.original_name}</span>
                <span className="text-[11px] text-muted-foreground">
                  {formatFileSize(doc.file_size)}
                  {doc.page_count ? ` · ${doc.page_count} page${doc.page_count === 1 ? "" : "s"}` : ""}
                  {` · ${doc.processing_status}`}
                  {doc.is_ocr_required ? " · OCR required" : ""}
                  {doc.extraction_completeness !== null && doc.extraction_completeness < 100
                    ? ` · ${doc.extraction_completeness}% extracted`
                    : ""}
                </span>
              </label>
              {!isReady && <Badge variant="warning">{doc.processing_status}</Badge>}
            </li>
          );
        })}
      </ul>
      {ready.length === 0 && (
        <p className="text-[11px] text-amber-900">
          No document has completed text extraction yet. The workflow will report
          insufficient sources rather than guessing.
        </p>
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
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [source, setSource] = useState<AnalysisSourceRef | null>(null);
  const [exporting, setExporting] = useState<"html" | "markdown" | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const aiQuery = useQuery({
    queryKey: ["ai-status"],
    queryFn: getAIStatus,
    select: (envelope) => envelope.data,
    staleTime: 60_000,
  });

  const docsQuery = useQuery({
    queryKey: ["case-documents", caseId, "analysis"],
    queryFn: () => listDocuments(caseId, { page_size: 100 }),
    select: (envelope) => envelope.data,
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
  const docs = docsQuery.data?.items ?? [];

  const startMutation = useMutation({
    mutationFn: () =>
      startCaseAnalysis(caseId, {
        focus: focus.trim() ? focus.trim() : null,
        document_ids: selectedDocIds.length > 0 ? selectedDocIds : null,
      }),
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

  function toggleDocument(id: string) {
    setSelectedDocIds((current) =>
      current.includes(id)
        ? current.filter((item) => item !== id)
        : [...current, id],
    );
  }

  async function handleExport(
    format: "html" | "markdown",
    mode: "open" | "download" = "download",
  ) {
    if (!run) return;
    setExporting(format);
    setExportError(null);
    try {
      const { blob, filename } = await downloadCaseReport(caseId, run.id, format);
      if (format === "html" && mode === "open") {
        // Open the self-contained print view. If the popup is blocked, save it.
        const url = window.URL.createObjectURL(blob);
        const opened = window.open(url, "_blank", "noopener,noreferrer");
        if (!opened) saveBlob(blob, filename);
        window.setTimeout(() => window.URL.revokeObjectURL(url), 60_000);
      } else {
        saveBlob(blob, filename);
      }
    } catch (error) {
      setExportError(
        error instanceof ApiClientError
          ? error.message
          : "Could not download the report. Try again.",
      );
    } finally {
      setExporting(null);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Configuration */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Brain className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
            Analysis configuration
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
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
              <Badge variant="outline">
                {ai.provider} / {ai.model}
              </Badge>
              {ai.is_mock && <Badge variant="warning">Fixture mode</Badge>}
              <span>{ai.message}</span>
            </div>
          )}

          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-foreground">Documents to analyse</span>
              <span className="text-[11px] text-muted-foreground">
                {documentCount} attached
              </span>
            </div>
            {docsQuery.isLoading ? (
              <Skeleton className="h-16 w-full" />
            ) : (
              <DocumentSelector
                documents={docs}
                selected={selectedDocIds}
                onToggle={toggleDocument}
                onSelectAll={() =>
                  setSelectedDocIds(
                    docs
                      .filter((doc) => doc.processing_status === "ready")
                      .map((doc) => doc.id),
                  )
                }
                onClear={() => setSelectedDocIds([])}
                disabled={busy || active}
              />
            )}
          </div>

          <div className="flex flex-col gap-2">
            <label htmlFor="analysis-focus" className="text-xs font-medium text-foreground">
              Optional analyst focus (treated as untrusted input)
            </label>
            <textarea
              id="analysis-focus"
              value={focus}
              onChange={(event) => setFocus(event.target.value)}
              maxLength={1000}
              rows={2}
              disabled={busy || active}
              placeholder="e.g. Focus on the termination clause, notice dates, and amounts claimed."
              className="w-full resize-y rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
            />
            <div className="flex flex-wrap items-center gap-2">
              <Button
                type="button"
                size="sm"
                variant="teal"
                disabled={busy || active || !ai?.configured}
                onClick={() => startMutation.mutate()}
              >
                {startMutation.isPending ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                ) : (
                  <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
                )}
                {active ? "Analysis in progress" : run ? "Run new analysis" : "Run analysis"}
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
            <p className="text-[11px] text-muted-foreground">
              The analysts read only extracted text from the selected ready documents.
              A deterministic verifier checks every quote against the cited page. No
              external legal authority database is consulted.
            </p>
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
                {run.steps.slice(-6).map((step, index) => (
                  <li
                    key={`${step.step}-${step.at}-${index}`}
                    className="flex items-center gap-1.5"
                  >
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
              Case Intelligence report
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
            <div className="flex flex-col items-center gap-2 py-10 text-center">
              <Gavel className="h-7 w-7 text-muted-foreground/50" aria-hidden="true" />
              <p className="text-sm font-medium text-foreground">No analysis yet</p>
              <p className="max-w-md text-xs text-muted-foreground">
                Select documents and run the workflow to extract source-linked facts,
                entities, chronology, legal questions, and uncertainty. Every statement
                is checked against the cited page before it is shown.
              </p>
            </div>
          )}
          {run && active && !run.result && (
            <div className="flex flex-col items-center gap-2 py-10 text-center">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" aria-hidden="true" />
              <p className="text-sm text-muted-foreground">
                The workflow is running. This panel refreshes automatically.
              </p>
            </div>
          )}
          {run?.result && (
            <ResultView
              result={run.result}
              onOpenSource={setSource}
              onExport={handleExport}
              exporting={exporting}
              exportError={exportError}
              onRerun={() => startMutation.mutate()}
              rerunning={startMutation.isPending || active}
            />
          )}
        </CardContent>
      </Card>

      <SourceDialog caseId={caseId} source={source} onClose={() => setSource(null)} />
    </div>
  );
}
