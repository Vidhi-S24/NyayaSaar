"use client";

/**
 * Case Intelligence — live Stage 6 workflow.
 *
 * Analysis is case-scoped, so this page selects a case and renders the real
 * AnalysisPanel. No demo data and no simulated progress.
 */

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, FolderOpen, Upload } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { AnalysisPanel } from "@/components/analysis/analysis-panel";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { listCases } from "@/lib/api/cases";
import { ApiClientError } from "@/lib/api-client";

export function IntelligenceClient({
  initialCaseId,
}: {
  initialCaseId?: string;
}) {
  const [caseId, setCaseId] = useState(initialCaseId ?? "");

  const casesQuery = useQuery({
    queryKey: ["cases", "intelligence"],
    queryFn: () => listCases({ page_size: 100 }),
    select: (envelope) => envelope.data,
  });

  const cases = useMemo(
    () => casesQuery.data?.items ?? [],
    [casesQuery.data],
  );

  // Keep the selection valid as the case list loads or changes.
  useEffect(() => {
    if (cases.length === 0) return;
    if (!cases.some((item) => item.id === caseId)) {
      setCaseId(cases[0].id);
    }
  }, [cases, caseId]);

  const selected = useMemo(
    () => cases.find((item) => item.id === caseId) ?? null,
    [cases, caseId],
  );

  return (
    <div className="flex flex-col gap-6 p-6 pb-10">
      <PageHeader
        title="Case Intelligence"
        description="Build a source-grounded case analysis from selected documents, with entities, chronology, legal questions, uncertainty flags, and a deterministic verification pass."
        actions={
          <Button size="sm" variant="teal" asChild>
            <Link href={selected ? `/cases/${selected.id}` : "/cases"}>
              <Upload className="h-3.5 w-3.5" />
              {selected ? "Upload to case" : "Open cases"}
            </Link>
          </Button>
        }
      />

      <div className="rounded-md border border-teal-200 bg-teal-50 px-3.5 py-3 text-xs text-teal-900">
        <strong>Stage 6 Case Intelligence is live.</strong> It reads only the selected
        case&apos;s ready documents, preserves document IDs and page numbers, and flags
        anything the verifier could not support. External authority research,
        contradictions, precedent, advocate, and judge modules remain later-stage work.
      </div>

      {casesQuery.isLoading && (
        <Card>
          <CardContent className="flex flex-col gap-3 pt-6">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-9 w-full max-w-md" />
            <Skeleton className="h-24 w-full" />
          </CardContent>
        </Card>
      )}

      {casesQuery.isError && (
        <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <div className="flex-1">
            <p className="font-medium">Could not load your cases</p>
            <p className="mt-0.5 text-xs">
              {casesQuery.error instanceof ApiClientError
                ? casesQuery.error.message
                : "Check that the API server is running."}
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={() => void casesQuery.refetch()}>
            Retry
          </Button>
        </div>
      )}

      {!casesQuery.isLoading && !casesQuery.isError && cases.length === 0 && (
        <div className="flex flex-col items-center gap-3 rounded-lg border border-border bg-card px-6 py-14 text-center">
          <FolderOpen className="h-8 w-8 text-muted-foreground/40" aria-hidden="true" />
          <div>
            <p className="text-sm font-medium text-foreground">No cases yet</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Create a case, upload a document, then return here to run the analysis.
            </p>
          </div>
          <Button variant="teal" size="sm" asChild>
            <Link href="/cases">Create a case</Link>
          </Button>
        </div>
      )}

      {selected && (
        <>
          <Card>
            <CardContent className="flex flex-col gap-3 pt-6">
              <div className="flex flex-col gap-1.5">
                <label htmlFor="intelligence-case" className="text-xs font-medium text-foreground">
                  Case
                </label>
                <select
                  id="intelligence-case"
                  value={selected.id}
                  onChange={(event) => setCaseId(event.target.value)}
                  className="h-9 w-full max-w-xl rounded-md border border-input bg-background px-3 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {cases.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.title}
                      {item.case_number ? ` · ${item.case_number}` : ""}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <Badge variant="secondary">
                  {selected.documents_count} document
                  {selected.documents_count === 1 ? "" : "s"}
                </Badge>
                {[selected.case_number, selected.court].filter(Boolean).length > 0 && (
                  <span>{[selected.case_number, selected.court].filter(Boolean).join(" · ")}</span>
                )}
                <Link
                  href={`/cases/${selected.id}`}
                  className="underline hover:text-foreground"
                >
                  Open case workspace
                </Link>
              </div>
            </CardContent>
          </Card>

          <AnalysisPanel
            key={selected.id}
            caseId={selected.id}
            documentCount={selected.documents_count}
          />
        </>
      )}
    </div>
  );
}
