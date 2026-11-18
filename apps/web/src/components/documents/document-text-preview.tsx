"use client";

/**
 * DocumentTextPreviewDialog — shows page-referenced extracted text chunks.
 *
 * Security note: extracted_text is UNTRUSTED content from uploaded documents.
 * It is rendered as plain text only (no dangerouslySetInnerHTML, no eval).
 * This prevents XSS and prompt-injection from malicious document content.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import {
  ChevronLeft,
  ChevronRight,
  AlertTriangle,
  FileText,
} from "lucide-react";
import { getDocumentText } from "@/lib/api/documents";
import { ApiClientError } from "@/lib/api-client";

interface DocumentTextPreviewDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  caseId: string;
  documentId: string;
  documentName: string;
  totalPages: number;
}

export function DocumentTextPreviewDialog({
  open,
  onOpenChange,
  caseId,
  documentId,
  documentName,
  totalPages,
}: DocumentTextPreviewDialogProps) {
  const [currentPage, setCurrentPage] = useState<number | undefined>(
    totalPages > 0 ? 1 : undefined,
  );

  const textQuery = useQuery({
    queryKey: ["document-text", caseId, documentId, currentPage],
    queryFn: () =>
      getDocumentText(caseId, documentId, {
        page: currentPage,
        max_pages: currentPage === undefined ? 5 : undefined,
      }),
    select: (env) => env.data,
    enabled: open,
    staleTime: 60_000, // text doesn't change between views
  });

  const preview = textQuery.data;
  const chunks = preview?.chunks ?? [];
  const displayedPage = currentPage ?? 1;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[80vh] flex flex-col gap-0 p-0 overflow-hidden">
        <DialogHeader className="border-b border-border px-6 py-4">
          <DialogTitle className="flex items-center gap-2 text-sm font-semibold">
            <FileText className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            <span className="truncate">{documentName}</span>
            {totalPages > 0 && (
              <Badge variant="secondary" className="ml-auto shrink-0 text-[10px]">
                {totalPages} pages
              </Badge>
            )}
          </DialogTitle>
          <p className="mt-1 text-xs text-muted-foreground">
            Extracted text — page references are stable and can be cited in AI
            analysis. Content is displayed as plain text only.
          </p>
        </DialogHeader>

        {/* Page navigation */}
        {totalPages > 1 && (
          <div className="flex items-center gap-2 border-b border-border bg-secondary/30 px-6 py-2.5">
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              disabled={displayedPage <= 1}
              onClick={() => setCurrentPage(Math.max(1, displayedPage - 1))}
              aria-label="Previous page"
            >
              <ChevronLeft className="h-4 w-4" aria-hidden="true" />
            </Button>
            <span className="text-xs text-muted-foreground">
              Page {displayedPage} of {totalPages}
            </span>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              disabled={displayedPage >= totalPages}
              onClick={() =>
                setCurrentPage(Math.min(totalPages, displayedPage + 1))
              }
              aria-label="Next page"
            >
              <ChevronRight className="h-4 w-4" aria-hidden="true" />
            </Button>
            <span className="ml-auto text-[10px] text-muted-foreground">
              Cite as: document_id={documentId.slice(0, 8)}…,
              page={displayedPage}
            </span>
          </div>
        )}

        {/* Content area */}
        <div className="flex-1 overflow-y-auto px-6 py-4" role="document">
          {textQuery.isLoading && (
            <div className="flex flex-col gap-3" role="status" aria-label="Loading text">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className={`h-4 w-${i % 2 === 0 ? "full" : "4/5"}`} />
              ))}
            </div>
          )}

          {textQuery.isError && (
            <div
              className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
              role="alert"
            >
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              <div>
                <p className="font-medium">Could not load extracted text</p>
                <p className="mt-0.5 text-xs">
                  {textQuery.error instanceof ApiClientError
                    ? textQuery.error.message
                    : "An error occurred. Please try again."}
                </p>
              </div>
            </div>
          )}

          {!textQuery.isLoading && !textQuery.isError && chunks.length === 0 && (
            <div className="flex flex-col items-center gap-2 py-10 text-center">
              <p className="text-sm text-muted-foreground">
                No text extracted for this page.
              </p>
            </div>
          )}

          {/* Text chunks — rendered as plain text, never HTML */}
          {chunks.map((chunk) => (
            <div key={chunk.id} className="mb-6 last:mb-0">
              <div className="mb-2 flex items-center gap-2">
                <Badge variant="outline" className="text-[10px]">
                  Page {chunk.page_number}
                </Badge>
                <span className="text-[10px] text-muted-foreground">
                  {chunk.char_count.toLocaleString()} characters
                </span>
              </div>
              {/* SECURITY: whitespace-pre-wrap displays untrusted text safely.
                  Never use dangerouslySetInnerHTML with extracted content. */}
              <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed text-foreground/80">
                {chunk.extracted_text}
              </pre>
            </div>
          ))}

          {preview?.is_partial && (
            <p className="mt-4 text-center text-xs text-muted-foreground">
              Showing first {chunks.length} pages. Use the page navigator to
              browse additional pages.
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
