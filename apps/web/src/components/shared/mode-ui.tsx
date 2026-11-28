import { CheckCircle2, FileSearch, Quote, ShieldQuestion } from "lucide-react";
import type {
  AdvocateArgumentTier,
  AdvocateSide,
  AnalysisSourceRef,
  AnalysisVerificationSummary,
  AnalysisSupport,
  JudgeAuditStatus,
} from "@nyayasaar/shared";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/**
 * Shared presentation helpers for Stage 10 modes.
 *
 * These components deliberately label the boundary between:
 *  - source evidence (verified document/corpus references), and
 *  - AI analysis (model-generated reasoning and classifications).
 */

export function SupportBadge({ support }: { support: AnalysisSupport }) {
  if (support === "supported") {
    return <Badge variant="success">Source verified</Badge>;
  }
  if (support === "partially_supported") {
    return <Badge variant="warning">Source cited, quote unverified</Badge>;
  }
  return <Badge variant="destructive">No verified support</Badge>;
}

export function TierBadge({ tier }: { tier: AdvocateArgumentTier }) {
  if (tier === "strong_supported") {
    return <Badge variant="success">Strongly supported</Badge>;
  }
  if (tier === "moderate_supported") {
    return <Badge variant="warning">Moderately supported</Badge>;
  }
  return <Badge variant="outline">Speculative</Badge>;
}

export function SideBadge({ side }: { side: AdvocateSide }) {
  return (
    <Badge variant={side === "claimant" ? "secondary" : "outline"}>
      {side === "claimant" ? "Claimant / Petitioner" : "Respondent / Defendant"}
    </Badge>
  );
}

const AUDIT_STATUS_LABELS: Record<JudgeAuditStatus, string> = {
  covered: "Covered",
  partially_covered: "Partially covered",
  unsupported: "Unsupported",
  inconsistent: "Inconsistent",
  missing_citation: "Missing citation",
  unresolved: "Unresolved",
};

export function AuditStatusBadge({ status }: { status: JudgeAuditStatus }) {
  const variant =
    status === "covered"
      ? "success"
      : status === "partially_covered"
        ? "warning"
        : status === "unresolved"
          ? "outline"
          : "destructive";
  return <Badge variant={variant}>{AUDIT_STATUS_LABELS[status]}</Badge>;
}

export function SeverityBadge({ severity }: { severity: "high" | "medium" | "low" }) {
  return (
    <Badge variant={severity === "high" ? "destructive" : "outline"}>
      {severity} severity
    </Badge>
  );
}

/**
 * Render verified source evidence. This is intentionally visually distinct from
 * model reasoning: every item is a document/page reference, not a conclusion.
 */
export function SourceEvidenceList({
  refs,
  label = "Source evidence",
  emptyLabel = "No verified source passage linked.",
  tone = "neutral",
}: {
  refs: AnalysisSourceRef[];
  label?: string;
  emptyLabel?: string;
  tone?: "neutral" | "contrary";
}) {
  return (
    <div
      className={cn(
        "rounded-md border p-3",
        tone === "contrary"
          ? "border-amber-200 bg-amber-50/50"
          : "border-teal-200/70 bg-teal-50/40",
      )}
    >
      <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        <FileSearch className="h-3 w-3" aria-hidden="true" />
        {label}
      </p>
      {refs.length === 0 ? (
        <p className="mt-1.5 flex items-center gap-1.5 text-xs text-muted-foreground">
          <ShieldQuestion className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          {emptyLabel}
        </p>
      ) : (
        <ul className="mt-2 space-y-2">
          {refs.map((ref, index) => (
            <li key={`${ref.source_id}-${index}`} className="text-xs">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="font-mono text-[10px] text-muted-foreground">
                  {ref.source_id}
                </span>
                <span className="font-medium text-foreground">
                  {ref.document_name}
                </span>
                {ref.page_number > 0 && (
                  <span className="text-muted-foreground">p.{ref.page_number}</span>
                )}
                {ref.quote_verified ? (
                  <span className="inline-flex items-center gap-0.5 text-[10px] text-teal-700">
                    <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
                    quote verified
                  </span>
                ) : (
                  <span className="text-[10px] text-amber-700">
                    quote not verified
                  </span>
                )}
              </div>
              {ref.quote && (
                <p className="mt-1 flex gap-1.5 border-l-2 border-border pl-2 text-[11px] italic text-foreground/80">
                  <Quote className="mt-0.5 h-3 w-3 shrink-0 text-muted-foreground" aria-hidden="true" />
                  <span>{ref.quote}</span>
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function VerificationStrip({
  verification,
}: {
  verification: AnalysisVerificationSummary;
}) {
  const items = [
    { label: "Total checks", value: verification.total_claims },
    { label: "Verified", value: verification.supported },
    { label: "Partial", value: verification.partially_supported },
    { label: "Unsupported", value: verification.unsupported },
  ];
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {items.map((item) => (
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
    </div>
  );
}

export function ModeLegend() {
  return (
    <div className="flex flex-wrap gap-x-5 gap-y-1.5 text-[11px] text-muted-foreground">
      <span className="inline-flex items-center gap-1.5">
        <span className="h-2 w-2 rounded-full bg-teal-500" aria-hidden="true" />
        Source evidence — verified document/corpus references
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="h-2 w-2 rounded-full bg-ink-400" aria-hidden="true" />
        AI analysis — model reasoning requiring human review
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="h-2 w-2 rounded-full bg-amber-500" aria-hidden="true" />
        Gap or contrary material — preserve and verify
      </span>
    </div>
  );
}
