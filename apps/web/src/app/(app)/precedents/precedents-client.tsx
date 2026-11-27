"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { FolderOpen, Upload } from "lucide-react";
import { listCases } from "@/lib/api/cases";
import { PageHeader } from "@/components/shared/page-header";
import { PrecedentPanel } from "@/components/precedents/precedent-panel";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function PrecedentsClient({
  initialCaseId,
}: {
  initialCaseId?: string;
}) {
  const [caseId, setCaseId] = useState(initialCaseId ?? "");

  const casesQuery = useQuery({
    queryKey: ["cases", "precedents"],
    queryFn: () => listCases({ page_size: 100 }),
    select: (env) => env.data,
  });

  const cases = useMemo(() => casesQuery.data?.items ?? [], [casesQuery.data]);

  useEffect(() => {
    if (cases.length === 0) return;
    if (!cases.some((c) => c.id === caseId)) {
      setCaseId(cases[0].id);
    }
  }, [cases, caseId]);

  const selected = useMemo(
    () => cases.find((c) => c.id === caseId) ?? null,
    [cases, caseId],
  );

  return (
    <div className="flex flex-col gap-6 p-6 pb-10">
      <PageHeader
        title="Precedent Explorer & Conflict Detector"
        description="Search legal records, explore citation relationships, and inspect potential reasoning conflicts with traceable source provenance."
        actions={
          <Button size="sm" variant="teal" asChild>
            <Link href={selected ? `/cases/${selected.id}` : "/cases"}>
              <Upload className="h-3.5 w-3.5" />
              {selected ? "Open case" : "Cases"}
            </Link>
          </Button>
        }
      />

      {casesQuery.isLoading ? (
        <Card>
          <CardContent className="pt-6">
            <Skeleton className="h-9 w-full max-w-md" />
          </CardContent>
        </Card>
      ) : cases.length === 0 ? (
        <div className="space-y-4">
          <Card>
            <CardContent className="flex flex-col items-center gap-3 py-8 text-center">
              <FolderOpen className="h-8 w-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                No case workspace selected yet. You can still search legal
                records below, or create a case to run case-linked precedent
                analysis.
              </p>
              <Button size="sm" variant="teal" asChild>
                <Link href="/cases">Go to Cases</Link>
              </Button>
            </CardContent>
          </Card>
          <PrecedentPanel />
        </div>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <label htmlFor="precedent-case" className="text-xs font-semibold">
              Case workspace:
            </label>
            <select
              id="precedent-case"
              value={caseId}
              onChange={(e) => setCaseId(e.target.value)}
              className="h-9 min-w-[260px] rounded-md border border-input bg-background px-3 text-sm"
            >
              {cases.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title}
                  {c.case_number ? ` (${c.case_number})` : ""}
                </option>
              ))}
            </select>
          </div>

          <PrecedentPanel caseId={selected?.id} />
        </>
      )}
    </div>
  );
}
