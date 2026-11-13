"use client";

/**
 * Cases — real case list backed by the FastAPI cases API.
 *
 * Create, search, filter, and delete are wired to /api/v1/cases.
 * Authorization is enforced by the backend; this page reflects its state.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Filter, Search, FileText, Clock, AlertCircle, Loader2 } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { CaseStatusBadge, PriorityDot, EmptyState } from "@/components/shared/case-ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { CaseFormDialog } from "@/components/cases/case-form-dialog";
import {
  createCase,
  deleteCase,
  formatRelativeTime,
  listCases,
} from "@/lib/api/cases";
import { ApiClientError } from "@/lib/api-client";
import type { Case, CaseCreateInput } from "@nyayasaar/shared";

const PAGE_SIZE = 20;

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "active", label: "Active" },
  { value: "review", label: "Under review" },
  { value: "closed", label: "Closed" },
  { value: "archived", label: "Archived" },
];

export default function CasesPage() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);

  // Debounce search input → query term.
  useEffect(() => {
    const t = setTimeout(() => {
      setSearch(searchInput);
      setPage(1);
    }, 300);
    return () => clearTimeout(t);
  }, [searchInput]);

  const casesQuery = useQuery({
    queryKey: ["cases", { page, search, status: statusFilter }],
    queryFn: () => listCases({ page, page_size: PAGE_SIZE, search, status: statusFilter }),
    select: (envelope) => envelope.data,
  });

  const [createOpen, setCreateOpen] = useState(false);
  const [caseToDelete, setCaseToDelete] = useState<Case | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["cases"] });

  const createMutation = useMutation({
    mutationFn: (input: CaseCreateInput) => createCase(input),
    onSuccess: async (envelope) => {
      await invalidate();
      setCreateOpen(false);
      setFormError(null);
      const newId = envelope.data?.id;
      if (newId) router.push(`/cases/${newId}`);
    },
    onError: (err) => {
      setFormError(
        err instanceof ApiClientError ? err.message : "Could not create the case. Try again.",
      );
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (caseId: string) => deleteCase(caseId),
    onSuccess: () => {
      void invalidate();
      setCaseToDelete(null);
      setDeleteError(null);
    },
    onError: (err) => {
      setDeleteError(
        err instanceof ApiClientError ? err.message : "Could not delete the case. Try again.",
      );
    },
  });

  const cases = casesQuery.data?.items ?? [];
  const total = casesQuery.data?.total ?? 0;
  const hasNext = casesQuery.data?.has_next ?? false;
  const isInitialLoading = casesQuery.isLoading;
  const isError = casesQuery.isError;

  return (
    <div className="flex flex-col gap-6 p-6 pb-10">
      <PageHeader
        title="Cases"
        description={
          isInitialLoading
            ? "Loading your cases…"
            : `${total} ${total === 1 ? "case" : "cases"} in your workspace`
        }
        actions={
          <Button size="sm" variant="teal" onClick={() => setCreateOpen(true)}>
            <Plus className="h-3.5 w-3.5" />
            New Case
          </Button>
        }
      />

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1 max-w-sm">
          <Search
            className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            placeholder="Search cases…"
            className="pl-8 h-8 text-sm"
            aria-label="Search cases"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
        </div>
        <div className="flex items-center gap-1.5">
          <Filter className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
          <select
            aria-label="Filter by status"
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="h-8 rounded-md border border-input bg-background px-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Error state */}
      {isError && (
        <div className="flex flex-col items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-6 py-10 text-center">
          <AlertCircle className="h-6 w-6 text-red-600" aria-hidden="true" />
          <div>
            <p className="text-sm font-medium text-red-900">Could not load cases</p>
            <p className="mt-1 text-xs text-red-800">
              {casesQuery.error instanceof ApiClientError
                ? casesQuery.error.message
                : "The backend may be unavailable. Check that the API server is running."}
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={() => void casesQuery.refetch()}>
            Retry
          </Button>
        </div>
      )}

      {/* Loading skeleton */}
      {isInitialLoading && (
        <div className="overflow-hidden rounded-lg border border-border bg-card">
          <div className="grid grid-cols-12 gap-3 border-b border-border bg-secondary/50 px-5 py-2.5">
            <Skeleton className="col-span-5 h-3" />
            <Skeleton className="col-span-2 h-3" />
            <Skeleton className="col-span-2 h-3" />
            <Skeleton className="col-span-1 h-3" />
            <Skeleton className="col-span-2 h-3" />
          </div>
          <div className="divide-y divide-border">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="grid grid-cols-12 gap-3 px-5 py-4">
                <div className="col-span-5 flex items-start gap-2.5">
                  <Skeleton className="mt-1.5 h-2 w-2 rounded-full" />
                  <div className="flex-1 space-y-1.5">
                    <Skeleton className="h-3.5 w-3/4" />
                    <Skeleton className="h-2.5 w-1/3" />
                  </div>
                </div>
                <Skeleton className="col-span-2 h-3" />
                <Skeleton className="col-span-2 h-5 w-20 rounded-full" />
                <Skeleton className="col-span-1 h-3" />
                <Skeleton className="col-span-2 h-3" />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Cases list */}
      {!isInitialLoading && !isError && (
        cases.length === 0 ? (
          <div className="rounded-lg border border-border bg-card">
            <EmptyState
              icon={<FileText className="h-5 w-5" />}
              title={search || statusFilter ? "No cases match your filters" : "No cases yet"}
              description={
                search || statusFilter
                  ? "Try a different search term or clear the status filter."
                  : "Create your first case workspace to start organising documents and analysis."
              }
              action={
                search || statusFilter ? (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setSearchInput("");
                      setStatusFilter("");
                    }}
                  >
                    Clear filters
                  </Button>
                ) : (
                  <Button variant="teal" size="sm" onClick={() => setCreateOpen(true)}>
                    <Plus className="h-3.5 w-3.5" />
                    New Case
                  </Button>
                )
              }
            />
          </div>
        ) : (
          <div className="overflow-hidden rounded-lg border border-border bg-card">
            {/* Table header */}
            <div className="grid grid-cols-12 gap-3 border-b border-border bg-secondary/50 px-5 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              <div className="col-span-5">Case</div>
              <div className="col-span-2 hidden sm:block">Court</div>
              <div className="col-span-2">Status</div>
              <div className="col-span-1 text-center">Docs</div>
              <div className="col-span-2 text-right">Updated</div>
            </div>

            <div className="divide-y divide-border">
              {cases.map((c) => (
                <div key={c.id} className="group relative">
                  <Link
                    href={`/cases/${c.id}`}
                    className="grid grid-cols-12 gap-3 px-5 py-4 transition-colors hover:bg-secondary/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
                  >
                    <div className="col-span-5 flex min-w-0 items-start gap-2.5">
                      <PriorityDot priority={c.priority} className="mt-1.5 shrink-0" />
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-foreground">{c.title}</p>
                        <p className="mt-0.5 text-xs text-muted-foreground">{c.case_number ?? "—"}</p>
                        <div className="mt-1.5 hidden gap-1.5 lg:flex flex-wrap">
                          {c.tags.slice(0, 2).map((tag) => (
                            <Badge key={tag} variant="secondary" className="text-[10px]">
                              {tag}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    </div>

                    <div className="col-span-2 hidden sm:flex items-start">
                      <span className="text-xs text-muted-foreground leading-snug">{c.court ?? "—"}</span>
                    </div>

                    <div className="col-span-2 flex items-start">
                      <CaseStatusBadge status={c.status} />
                    </div>

                    <div className="col-span-1 flex items-start justify-center">
                      <span className="flex items-center gap-1 text-xs text-muted-foreground">
                        <FileText className="h-3 w-3" aria-hidden="true" />
                        {c.documents_count}
                      </span>
                    </div>

                    <div className="col-span-2 flex items-start justify-end">
                      <span className="flex items-center gap-1 text-xs text-muted-foreground">
                        <Clock className="h-3 w-3" aria-hidden="true" />
                        {formatRelativeTime(c.updated_at)}
                      </span>
                    </div>
                  </Link>
                  {/* Delete (kept outside the link so it stays keyboard accessible) */}
                  <button
                    type="button"
                    onClick={() => {
                      setDeleteError(null);
                      setCaseToDelete(c);
                    }}
                    aria-label={`Delete case ${c.title}`}
                    className="absolute bottom-3 right-2 rounded px-2 py-1 text-[11px] text-muted-foreground opacity-0 transition-opacity hover:text-destructive focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring group-hover:opacity-100"
                  >
                    Delete
                  </button>
                </div>
              ))}
            </div>

            {/* Pagination */}
            {(page > 1 || hasNext) && (
              <div className="flex items-center justify-between border-t border-border px-5 py-3">
                <p className="text-xs text-muted-foreground">
                  Page {page} — {cases.length} of {total} cases
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!hasNext}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </div>
        )
      )}

      {/* Create dialog */}
      <CaseFormDialog
        open={createOpen}
        error={formError}
        onOpenChange={(open) => {
          setCreateOpen(open);
          if (!open) setFormError(null);
        }}
        onSubmit={async (input) => {
          setFormError(null);
          await createMutation.mutateAsync(input);
        }}
      />

      {formError && !createOpen && (
        <p className="text-xs text-red-700" role="alert">
          {formError}
        </p>
      )}

      {/* Delete confirmation */}
      <AlertDialog
        open={caseToDelete !== null}
        onOpenChange={(open) => {
          if (!open) {
            setCaseToDelete(null);
            setDeleteError(null);
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete “{caseToDelete?.title}”?</AlertDialogTitle>
            <AlertDialogDescription>
              This permanently removes the case workspace and its metadata.
              Documents uploaded to it will no longer be accessible. This action
              cannot be undone.
            </AlertDialogDescription>
            {deleteError && (
              <p className="text-xs text-red-700" role="alert">
                {deleteError}
              </p>
            )}
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => {
              setCaseToDelete(null);
              setDeleteError(null);
            }}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={deleteMutation.isPending}
              onClick={(e) => {
                e.preventDefault();
                if (caseToDelete) deleteMutation.mutate(caseToDelete.id);
              }}
            >
              {deleteMutation.isPending && (
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
              )}
              Delete case
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
