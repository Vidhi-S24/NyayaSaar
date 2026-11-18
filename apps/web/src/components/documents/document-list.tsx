"use client";

/**
 * DocumentList — live list of documents for a case workspace.
 *
 * Shows processing status, page count, file type, extracted-text preview link,
 * retry button (for failed docs), and delete confirmation.
 *
 * Uses TanStack Query for data fetching. All server-enforced authorization;
 * this component only surfaces the data the API returns.
 */

import { useState } from "react";
import {
  FileText,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  Clock,
  RefreshCw,
  Trash2,
  Eye,
  ScanText,
} from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
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
import {
  listDocuments,
  deleteDocument,
  retryDocumentExtraction,
  formatFileSize,
  formatContentType,
} from "@/lib/api/documents";
import { ApiClientError } from "@/lib/api-client";
import type { Document } from "@nyayasaar/shared";
import { DocumentTextPreviewDialog } from "./document-text-preview";

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

function ProcessingBadge({ status }: { status: Document["processing_status"] }) {
  if (status === "ready")
    return (
      <Badge variant="success" className="gap-1 text-[10px]">
        <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
        Ready
      </Badge>
    );
  if (status === "processing")
    return (
      <Badge variant="warning" className="gap-1 text-[10px]">
        <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
        Processing
      </Badge>
    );
  if (status === "pending")
    return (
      <Badge variant="secondary" className="gap-1 text-[10px]">
        <Clock className="h-3 w-3" aria-hidden="true" />
        Pending
      </Badge>
    );
  // failed
  return (
    <Badge variant="destructive" className="gap-1 text-[10px]">
      <AlertTriangle className="h-3 w-3" aria-hidden="true" />
      Failed
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Single document row
// ---------------------------------------------------------------------------

interface DocumentRowProps {
  doc: Document;
  caseId: string;
  onDelete: () => void;
  onRetry: () => void;
}

function DocumentRow({ doc, caseId, onDelete, onRetry }: DocumentRowProps) {
  const [previewOpen, setPreviewOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  return (
    <>
      <div className="grid grid-cols-12 gap-3 px-5 py-3.5 transition-colors hover:bg-secondary/30">
        {/* Name + size */}
        <div className="col-span-5 flex items-center gap-2.5 min-w-0">
          <FileText
            className="h-4 w-4 shrink-0 text-muted-foreground"
            aria-hidden="true"
          />
          <div className="min-w-0">
            <p
              className="truncate text-sm font-medium text-foreground"
              title={doc.original_name}
            >
              {doc.original_name}
            </p>
            <p className="text-xs text-muted-foreground">
              {formatFileSize(doc.file_size)}
              {doc.is_ocr_required && (
                <span
                  className="ml-1.5 inline-flex items-center gap-0.5 text-amber-600"
                  title="Scanned PDF — text extraction may be incomplete"
                >
                  <ScanText className="h-3 w-3" aria-hidden="true" />
                  OCR needed
                </span>
              )}
            </p>
          </div>
        </div>

        {/* Type */}
        <div className="col-span-2 hidden sm:flex items-center">
          <Badge variant="secondary" className="text-[10px] uppercase">
            {formatContentType(doc.content_type)}
          </Badge>
        </div>

        {/* Pages */}
        <div className="col-span-2 hidden sm:flex items-center">
          <span className="text-xs text-muted-foreground">
            {doc.page_count != null ? `${doc.page_count} pg` : "—"}
          </span>
        </div>

        {/* Status */}
        <div className="col-span-2 flex items-center">
          <ProcessingBadge status={doc.processing_status} />
        </div>

        {/* Actions */}
        <div className="col-span-1 flex items-center justify-end gap-1">
          {/* View extracted text */}
          {doc.processing_status === "ready" && (
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              title="View extracted text"
              aria-label={`View extracted text for ${doc.original_name}`}
              onClick={() => setPreviewOpen(true)}
            >
              <Eye className="h-3.5 w-3.5" aria-hidden="true" />
            </Button>
          )}

          {/* Retry extraction */}
          {doc.processing_status === "failed" && doc.retry_count < 3 && (
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-amber-600 hover:text-amber-700"
              title="Retry text extraction"
              aria-label={`Retry extraction for ${doc.original_name}`}
              onClick={onRetry}
            >
              <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
            </Button>
          )}

          {/* Delete */}
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-muted-foreground hover:text-destructive"
            title="Delete document"
            aria-label={`Delete ${doc.original_name}`}
            onClick={() => setConfirmDelete(true)}
          >
            <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
          </Button>
        </div>
      </div>

      {/* Failure reason */}
      {doc.processing_status === "failed" && doc.failure_reason && (
        <div className="border-t border-red-100 bg-red-50/50 px-5 py-2">
          <p className="text-xs text-red-700">
            <span className="font-medium">Extraction issue: </span>
            {doc.failure_reason}
          </p>
          {doc.retry_count >= 3 && (
            <p className="mt-0.5 text-xs text-red-600">
              Maximum retries reached. Please re-upload the document.
            </p>
          )}
        </div>
      )}

      {/* Text preview dialog */}
      {previewOpen && (
        <DocumentTextPreviewDialog
          open={previewOpen}
          onOpenChange={setPreviewOpen}
          caseId={caseId}
          documentId={doc.id}
          documentName={doc.original_name}
          totalPages={doc.page_count ?? 0}
        />
      )}

      {/* Delete confirmation */}
      <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete &ldquo;{doc.original_name}&rdquo;?</AlertDialogTitle>
            <AlertDialogDescription>
              This permanently removes the document, all extracted text, and the
              stored file. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                setConfirmDelete(false);
                onDelete();
              }}
            >
              Delete document
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

// ---------------------------------------------------------------------------
// Document list
// ---------------------------------------------------------------------------

interface DocumentListProps {
  caseId: string;
  /** Key to trigger re-fetch after a new upload */
  uploadedAt?: number;
}

export function DocumentList({ caseId, uploadedAt }: DocumentListProps) {
  const queryClient = useQueryClient();

  const listQuery = useQuery({
    queryKey: ["documents", caseId, uploadedAt],
    queryFn: () => listDocuments(caseId),
    select: (env) => env.data,
    refetchInterval: 5000, // poll; stops being expensive when nothing changes
  });

  const deleteMutation = useMutation({
    mutationFn: ({ docId }: { docId: string }) =>
      deleteDocument(caseId, docId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["documents", caseId] });
      void queryClient.invalidateQueries({ queryKey: ["case", caseId] });
    },
  });

  const retryMutation = useMutation({
    mutationFn: ({ docId }: { docId: string }) =>
      retryDocumentExtraction(caseId, docId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["documents", caseId] });
    },
  });

  // --- Loading skeleton ---
  if (listQuery.isLoading) {
    return (
      <div
        className="flex flex-col gap-2 py-2"
        role="status"
        aria-label="Loading documents"
      >
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full rounded-lg" />
        ))}
      </div>
    );
  }

  // --- Error ---
  if (listQuery.isError) {
    return (
      <div
        className="flex items-center gap-2 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
        role="alert"
      >
        <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
        {listQuery.error instanceof ApiClientError
          ? listQuery.error.message
          : "Could not load documents. Check that the API is running."}
      </div>
    );
  }

  const docs = listQuery.data?.items ?? [];

  if (docs.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 py-10 text-center">
        <FileText className="h-8 w-8 text-muted-foreground/30" aria-hidden="true" />
        <p className="text-sm font-medium text-muted-foreground">No documents yet</p>
        <p className="text-xs text-muted-foreground">
          Upload a PDF, DOCX, or TXT file above to begin.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card">
      {/* Header */}
      <div className="grid grid-cols-12 gap-3 border-b border-border bg-secondary/50 px-5 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        <div className="col-span-5">Name</div>
        <div className="col-span-2 hidden sm:block">Type</div>
        <div className="col-span-2 hidden sm:block">Pages</div>
        <div className="col-span-2">Status</div>
        <div className="col-span-1 text-right">Actions</div>
      </div>

      {/* Rows */}
      <div className="divide-y divide-border">
        {docs.map((doc) => (
          <DocumentRow
            key={doc.id}
            doc={doc}
            caseId={caseId}
            onDelete={() => deleteMutation.mutate({ docId: doc.id })}
            onRetry={() => retryMutation.mutate({ docId: doc.id })}
          />
        ))}
      </div>

      {/* Footer */}
      {(listQuery.data?.total ?? 0) > docs.length && (
        <div className="border-t border-border px-5 py-3 text-center text-xs text-muted-foreground">
          Showing {docs.length} of {listQuery.data?.total} documents.
        </div>
      )}
    </div>
  );
}
