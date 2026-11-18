"use client";

/**
 * DocumentUpload — file picker + drag-and-drop upload panel.
 *
 * Validates extension and size client-side before upload (server also validates).
 * Uses multipart/form-data POST. The auth token is injected by the api-client.
 *
 * Security: extracted text is never displayed in this component; only file
 * metadata (name, size, type) is handled here.
 */

import { useCallback, useRef, useState } from "react";
import { Upload, Loader2, AlertTriangle, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { uploadDocument, formatFileSize } from "@/lib/api/documents";
import { ApiClientError } from "@/lib/api-client";
import type { Document } from "@nyayasaar/shared";

const ACCEPTED_EXTENSIONS = [".pdf", ".docx", ".doc", ".txt"];
const MAX_SIZE_BYTES = 50 * 1024 * 1024; // 50 MB (must match backend)

function validateFile(file: File): string | null {
  const name = file.name.toLowerCase();
  const hasValidExt = ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext));
  if (!hasValidExt) {
    return `File type not supported. Accepted: ${ACCEPTED_EXTENSIONS.join(", ")}`;
  }
  if (file.size === 0) {
    return "The file is empty.";
  }
  if (file.size > MAX_SIZE_BYTES) {
    return `File is too large (${formatFileSize(file.size)}). Maximum is 50 MB.`;
  }
  return null;
}

interface DocumentUploadProps {
  caseId: string;
  onUploaded: (doc: Document) => void;
}

export function DocumentUpload({ caseId, onUploaded }: DocumentUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastSuccess, setLastSuccess] = useState<string | null>(null);

  const handleFiles = useCallback(
    async (files: FileList | null) => {
      if (!files || files.length === 0) return;
      const file = files[0]!;

      // Client-side validation (server also validates; this is UX only)
      const validationError = validateFile(file);
      if (validationError) {
        setError(validationError);
        setLastSuccess(null);
        return;
      }

      setError(null);
      setLastSuccess(null);
      setUploading(true);
      try {
        const envelope = await uploadDocument(caseId, file);
        const doc = envelope.data!;
        setLastSuccess(`"${doc.original_name}" uploaded — ${doc.processing_status === "ready" ? "ready" : doc.processing_status}.`);
        onUploaded(doc);
      } catch (err) {
        setError(
          err instanceof ApiClientError
            ? err.message
            : "Upload failed. Please try again.",
        );
      } finally {
        setUploading(false);
        // Reset the input so the same file can be re-selected
        if (inputRef.current) inputRef.current.value = "";
      }
    },
    [caseId, onUploaded],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragging(false);
      void handleFiles(e.dataTransfer.files);
    },
    [handleFiles],
  );

  return (
    <div className="flex flex-col gap-2">
      {/* Drop zone */}
      <div
        role="region"
        aria-label="Document upload area"
        className={[
          "flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed py-8 text-center transition-colors",
          isDragging
            ? "border-teal-400 bg-teal-50/40"
            : "border-border bg-secondary/20 hover:border-teal-300 hover:bg-teal-50/20",
        ].join(" ")}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        {uploading ? (
          <Loader2
            className="h-6 w-6 animate-spin text-teal-600"
            aria-label="Uploading"
          />
        ) : (
          <Upload
            className="h-6 w-6 text-muted-foreground/50"
            aria-hidden="true"
          />
        )}
        <div>
          <p className="text-sm font-medium text-foreground">
            {uploading ? "Uploading…" : "Drop a document here or click Browse"}
          </p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            PDF, DOCX, DOC, TXT · Max 50 MB · OCR flagged for scanned PDFs
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          disabled={uploading}
          onClick={() => inputRef.current?.click()}
          type="button"
        >
          Browse Files
        </Button>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_EXTENSIONS.join(",")}
          className="sr-only"
          aria-label="Choose file to upload"
          onChange={(e) => void handleFiles(e.target.files)}
        />
      </div>

      {/* Error */}
      {error && (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800"
        >
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          {error}
        </div>
      )}

      {/* Success */}
      {lastSuccess && (
        <div
          role="status"
          className="flex items-start gap-2 rounded-md border border-teal-200 bg-teal-50 px-3 py-2 text-xs text-teal-800"
        >
          <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          {lastSuccess}
        </div>
      )}
    </div>
  );
}
