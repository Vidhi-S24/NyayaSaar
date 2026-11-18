"use client";

/**
 * Document Library — cross-case view of all uploaded documents.
 *
 * Stage 4: Displays real documents from the API for each case the user owns.
 * The global library is a convenience view; upload happens inside a case workspace.
 */

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { FileText, Search, Upload, AlertTriangle, Loader2, ScanText } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { listCases } from "@/lib/api/cases";
import { listDocuments, formatFileSize, formatContentType } from "@/lib/api/documents";
import { ApiClientError } from "@/lib/api-client";
import type { Document } from "@nyayasaar/shared";


function StatusBadge({ status }: { status: Document["processing_status"] }) {
  const map = {
    ready: "success",
    processing: "warning",
    pending: "secondary",
    failed: "destructive",
  } as const;
  return (
    <Badge variant={map[status] ?? "outline"} className="capitalize text-[10px]">
      {status === "processing" && <Loader2 className="mr-1 h-2.5 w-2.5 animate-spin" aria-hidden="true" />}
      {status}
    </Badge>
  );
}

// One case + its documents collapsed into rows
function CaseDocuments({ caseId, caseTitle, search }: { caseId: string; caseTitle: string; search: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["documents", caseId],
    queryFn: () => listDocuments(caseId, { page_size: 100 }),
    select: (env) => env.data,
    refetchInterval: 10000,
  });

  if (isLoading) return <Skeleton className="h-12 w-full rounded-lg" />;
  if (isError) return null;

  const docs = (data?.items ?? []).filter((d) =>
    !search || d.original_name.toLowerCase().includes(search.toLowerCase()),
  );

  if (docs.length === 0) return null;

  return (
    <>
      {docs.map((doc) => (
        <div key={doc.id} className="grid grid-cols-12 gap-3 px-5 py-3.5 transition-colors hover:bg-secondary/30">
          <div className="col-span-5 flex items-center gap-2.5 min-w-0">
            <FileText className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-foreground" title={doc.original_name}>
                {doc.original_name}
              </p>
              <p className="text-xs text-muted-foreground">
                {formatFileSize(doc.file_size)}
                {doc.is_ocr_required && (
                  <span className="ml-1.5 inline-flex items-center gap-0.5 text-amber-600">
                    <ScanText className="h-3 w-3" aria-hidden="true" /> OCR needed
                  </span>
                )}
              </p>
            </div>
          </div>
          <div className="col-span-3 hidden sm:flex items-center">
            <Link href={`/cases/${caseId}`} className="truncate text-xs text-muted-foreground hover:text-foreground hover:underline">
              {caseTitle}
            </Link>
          </div>
          <div className="col-span-2 flex items-center">
            <Badge variant="secondary" className="text-[10px] uppercase">{formatContentType(doc.content_type)}</Badge>
          </div>
          <div className="col-span-1 hidden sm:flex items-center justify-center">
            <span className="text-xs text-muted-foreground">{doc.page_count ?? "—"}</span>
          </div>
          <div className="col-span-1 flex items-center justify-end">
            <StatusBadge status={doc.processing_status} />
          </div>
        </div>
      ))}
    </>
  );
}

export default function DocumentsPage() {
  const [search, setSearch] = useState("");

  const casesQuery = useQuery({
    queryKey: ["cases"],
    queryFn: () => listCases({ page_size: 50 }),
    select: (env) => env.data,
  });

  const cases = casesQuery.data?.items ?? [];
  const totalDocs = cases.reduce((sum, c) => sum + c.documents_count, 0);

  return (
    <div className="flex flex-col gap-6 p-6 pb-10">
      <PageHeader
        title="Document Library"
        description={
          casesQuery.isLoading
            ? "Loading…"
            : `${totalDocs} document${totalDocs !== 1 ? "s" : ""} across ${cases.length} case${cases.length !== 1 ? "s" : ""}`
        }
        actions={
          <Button size="sm" variant="teal" asChild>
            <Link href="/cases"><Upload className="h-3.5 w-3.5" />Upload via Case</Link>
          </Button>
        }
      />

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
        <Input
          placeholder="Search documents…"
          className="pl-8 h-8 text-sm"
          aria-label="Search documents"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {/* Upload hint */}
      <div className="flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed border-border bg-secondary/30 py-8 text-center">
        <Upload className="h-6 w-6 text-muted-foreground/50" aria-hidden="true" />
        <div>
          <p className="text-sm font-medium text-foreground">Upload documents inside a case workspace</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            PDF, DOCX, DOC, TXT · Max 50 MB · Text extracted automatically
          </p>
        </div>
        <Button variant="outline" size="sm" asChild>
          <Link href="/cases">Go to Cases</Link>
        </Button>
      </div>

      {/* Loading */}
      {casesQuery.isLoading && (
        <div className="flex flex-col gap-2">
          {[1, 2, 3].map((i) => <Skeleton key={i} className="h-12 w-full rounded-lg" />)}
        </div>
      )}

      {/* Error */}
      {casesQuery.isError && (
        <div className="flex items-center gap-2 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
          <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
          {casesQuery.error instanceof ApiClientError ? casesQuery.error.message : "Could not load documents."}
        </div>
      )}

      {/* Documents table */}
      {cases.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-border bg-card">
          <div className="grid grid-cols-12 gap-3 border-b border-border bg-secondary/50 px-5 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            <div className="col-span-5">Name</div>
            <div className="col-span-3 hidden sm:block">Case</div>
            <div className="col-span-2">Type</div>
            <div className="col-span-1 text-center hidden sm:block">Pages</div>
            <div className="col-span-1 text-right">Status</div>
          </div>
          <div className="divide-y divide-border">
            {cases.map((c) => (
              <CaseDocuments key={c.id} caseId={c.id} caseTitle={c.title} search={search} />
            ))}
          </div>
        </div>
      )}

      {!casesQuery.isLoading && cases.length === 0 && (
        <div className="flex flex-col items-center gap-2 py-10 text-center">
          <FileText className="h-8 w-8 text-muted-foreground/30" aria-hidden="true" />
          <p className="text-sm font-medium text-muted-foreground">No cases yet</p>
          <p className="text-xs text-muted-foreground">Create a case first, then upload documents.</p>
          <Button variant="outline" size="sm" asChild><Link href="/cases">Go to Cases</Link></Button>
        </div>
      )}
    </div>
  );
}
