"use client";

/**
 * Case workspace — real case detail backed by /api/v1/cases/{id}.
 *
 * Stage 4: Documents tab is now live — real upload, extraction status,
 * text preview, retry, and deletion via /api/v1/cases/{id}/documents.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft, AlertTriangle, Brain, Scale,
  Gavel, BookOpen, Pencil, Loader2, SearchX,
} from "lucide-react";
import { CaseStatusBadge, PriorityDot, EmptyState } from "@/components/shared/case-ui";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { CaseFormDialog } from "@/components/cases/case-form-dialog";
import { DocumentUpload } from "@/components/documents/document-upload";
import { DocumentList } from "@/components/documents/document-list";
import { AnalysisPanel } from "@/components/analysis/analysis-panel";
import { deleteCase, formatRelativeTime, getCase, updateCase } from "@/lib/api/cases";
import { ApiClientError } from "@/lib/api-client";
import type { CaseCreateInput } from "@nyayasaar/shared";

export default function CasePage({ params }: { params: Promise<{ id: string }> }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [caseId, setCaseId] = useState<string | null>(null);
  const [uploadedAt, setUploadedAt] = useState<number>(0);
  const [activeTab, setActiveTab] = useState("documents");

  useEffect(() => {
    params.then((p) => setCaseId(p.id));
  }, [params]);

  const caseQuery = useQuery({
    queryKey: ["case", caseId],
    queryFn: () => getCase(caseId as string),
    enabled: caseId !== null,
    select: (envelope) => envelope.data,
    retry: (failureCount, error) => {
      if (error instanceof ApiClientError && error.status >= 400 && error.status < 500) return false;
      return failureCount < 2;
    },
  });

  const [editOpen, setEditOpen] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const updateMutation = useMutation({
    mutationFn: (input: CaseCreateInput) => updateCase(caseId as string, input),
    onSuccess: () => {
      setEditOpen(false);
      setEditError(null);
      void queryClient.invalidateQueries({ queryKey: ["case", caseId] });
      void queryClient.invalidateQueries({ queryKey: ["cases"] });
    },
    onError: (err) => {
      setEditError(err instanceof ApiClientError ? err.message : "Could not save changes. Try again.");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteCase(caseId as string),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["cases"] });
      router.push("/cases");
    },
    onError: (err) => {
      setConfirmDelete(true);
      setDeleteError(err instanceof ApiClientError ? err.message : "Could not delete the case. Try again.");
    },
  });

  if (caseId === null || caseQuery.isLoading) {
    return (
      <div className="flex flex-col gap-6 p-6 pb-10" role="status" aria-label="Loading case">
        <Skeleton className="h-8 w-24" />
        <Skeleton className="h-6 w-2/3" />
        <Skeleton className="h-5 w-1/3 rounded-full" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  const c = caseQuery.data;

  if (caseQuery.isError && caseQuery.error instanceof ApiClientError && caseQuery.error.status === 404) {
    return (
      <div className="flex flex-col gap-6 p-6 pb-10">
        <Button asChild variant="ghost" size="sm" className="-ml-2 w-fit">
          <Link href="/cases"><ArrowLeft className="h-3.5 w-3.5" />Cases</Link>
        </Button>
        <div className="rounded-lg border border-border bg-card">
          <EmptyState
            icon={<SearchX className="h-5 w-5" />}
            title="Case not found"
            description="This case doesn't exist, or you don't have access to it."
            action={<Button variant="outline" size="sm" asChild><Link href="/cases">Back to all cases</Link></Button>}
          />
        </div>
      </div>
    );
  }

  if (caseQuery.isError || !c) {
    return (
      <div className="flex flex-col gap-6 p-6 pb-10">
        <Button asChild variant="ghost" size="sm" className="-ml-2 w-fit">
          <Link href="/cases"><ArrowLeft className="h-3.5 w-3.5" />Cases</Link>
        </Button>
        <div className="flex flex-col items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-6 py-10 text-center">
          <AlertTriangle className="h-6 w-6 text-red-600" aria-hidden="true" />
          <div>
            <p className="text-sm font-medium text-red-900">Could not load this case</p>
            <p className="mt-1 text-xs text-red-800">
              {caseQuery.error instanceof ApiClientError
                ? caseQuery.error.message
                : "The backend may be unavailable. Check that the API server is running."}
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={() => void caseQuery.refetch()}>Retry</Button>
        </div>
      </div>
    );
  }

  const modules = [
    { href: `/intelligence?caseId=${c.id}`, label: "Case Intelligence", icon: Brain, desc: "Run source-linked analysis" },
    { href: `/contradictions?caseId=${c.id}`, label: "Contradiction & Gap", icon: AlertTriangle, desc: "Detect conflicts and missing evidence" },
    { href: `/precedents?caseId=${c.id}`, label: "Precedent Explorer", icon: BookOpen, desc: "Explore authorities and citation links" },
    { href: `/advocate?caseId=${c.id}`, label: "Advocate Mode", icon: Scale, desc: "Prepare two-sided arguments and gaps" },
    { href: `/judge?caseId=${c.id}`, label: "Judge / Clerk", icon: Gavel, desc: "Audit coverage, reasoning, and citations" },
  ];

  return (
    <div className="flex flex-col gap-6 p-6 pb-10">
      {/* Back + actions */}
      <div className="flex items-center justify-between">
        <Button asChild variant="ghost" size="sm" className="-ml-2 w-fit">
          <Link href="/cases"><ArrowLeft className="h-3.5 w-3.5" />Cases</Link>
        </Button>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => { setEditError(null); setEditOpen(true); }}>
            <Pencil className="h-3.5 w-3.5" />Edit
          </Button>
          <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive"
            onClick={() => { setDeleteError(null); setConfirmDelete(true); }}>
            Delete
          </Button>
        </div>
      </div>

      {/* Title */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-2.5">
          <PriorityDot priority={c.priority} className="mt-2" />
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-foreground">{c.title}</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {[c.case_number, c.court].filter(Boolean).join(" · ") || "No case number or court set"}
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">Updated {formatRelativeTime(c.updated_at)}</p>
          </div>
        </div>
        <CaseStatusBadge status={c.status} />
      </div>

      {/* Tags */}
      {c.tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {c.tags.map((tag) => <Badge key={tag} variant="secondary">{tag}</Badge>)}
        </div>
      )}

      {/* Summary */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Summary</CardTitle>
        </CardHeader>
        <CardContent>
          {c.summary ? (
            <p className="text-sm text-foreground/80 leading-relaxed">{c.summary}</p>
          ) : (
            <p className="text-sm text-muted-foreground">
              No summary yet.{" "}
              <button className="underline hover:text-foreground"
                onClick={() => { setEditError(null); setEditOpen(true); }}>Edit</button>{" "}
              to add a factual background for this case.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Intelligence modules */}
      <div>
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Intelligence modules
        </p>
        <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-5">
          {modules.map((mod) => {
            const Icon = mod.icon;
            return (
              <Link key={mod.href} href={mod.href}
                className="group flex flex-col gap-1 rounded-lg border border-border bg-card p-4 transition-colors hover:border-teal-300 hover:bg-teal-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                <Icon className="h-4 w-4 text-muted-foreground group-hover:text-teal-700" aria-hidden="true" />
                <span className="text-sm font-medium text-foreground">{mod.label}</span>
                <span className="text-xs text-muted-foreground">{mod.desc}</span>
              </Link>
            );
          })}
        </div>
      </div>

      <Separator />

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="issues">Legal Issues ({c.issues.length})</TabsTrigger>
          <TabsTrigger value="documents">Documents ({c.documents_count})</TabsTrigger>
          <TabsTrigger value="analysis">Analysis</TabsTrigger>
        </TabsList>

        <TabsContent value="issues">
          {c.issues.length === 0 ? (
            <div className="mt-4 rounded-lg border border-border bg-card">
              <EmptyState
                title="No legal issues recorded"
                description="Add issues manually via Edit, or run the Analysis tab to extract source-linked legal issues from the documents."
              />
            </div>
          ) : (
            <div className="mt-4 divide-y divide-border rounded-lg border border-border bg-card">
              {c.issues.map((issue, i) => (
                <div key={i} className="flex items-start gap-3 px-5 py-3.5">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-secondary text-[10px] font-semibold text-muted-foreground">
                    {i + 1}
                  </span>
                  <p className="text-sm text-foreground">{issue}</p>
                </div>
              ))}
            </div>
          )}
        </TabsContent>

        {/* Documents tab — Stage 4 live */}
        <TabsContent value="documents">
          <div className="mt-4 flex flex-col gap-4">
            <DocumentUpload
              caseId={c.id}
              onUploaded={() => {
                setUploadedAt(Date.now());
                void queryClient.invalidateQueries({ queryKey: ["case", caseId] });
              }}
            />
            <DocumentList caseId={c.id} uploadedAt={uploadedAt} />
          </div>
        </TabsContent>

        {/* Analysis tab — Stage 5 live workflow */}
        <TabsContent value="analysis">
          <div className="mt-4">
            <AnalysisPanel caseId={c.id} documentCount={c.documents_count} />
          </div>
        </TabsContent>
      </Tabs>

      {/* Edit dialog */}
      <CaseFormDialog
        open={editOpen}
        caseData={c}
        error={editError}
        onOpenChange={(open) => { setEditOpen(open); if (!open) setEditError(null); }}
        onSubmit={async (input) => { setEditError(null); await updateMutation.mutateAsync(input); }}
      />

      {/* Delete confirmation */}
      <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete &ldquo;{c.title}&rdquo;?</AlertDialogTitle>
            <AlertDialogDescription>
              This permanently removes the case workspace and its metadata. This action cannot be undone.
            </AlertDialogDescription>
            {deleteError && <p className="text-xs text-red-700" role="alert">{deleteError}</p>}
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => { setConfirmDelete(false); setDeleteError(null); }}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={deleteMutation.isPending}
              onClick={(e) => { e.preventDefault(); deleteMutation.mutate(); }}
            >
              {deleteMutation.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />}
              Delete case
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
