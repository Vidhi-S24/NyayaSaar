"use client";

/**
 * CaseFormDialog — create and edit case forms in a dialog.
 *
 * Validation runs client-side (zod); the backend re-validates everything.
 */

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { AlertCircle, Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type {
  Case,
  CaseCreateInput,
  CaseStatus,
} from "@nyayasaar/shared";

const caseSchema = z.object({
  title: z.string().min(1, "Title is required").max(255, "At most 255 characters"),
  case_number: z.string().max(100, "At most 100 characters").optional(),
  court: z.string().max(255, "At most 255 characters").optional(),
  jurisdiction: z.string().max(255, "At most 255 characters").optional(),
  status: z.enum(["active", "review", "closed", "archived"]),
  priority: z.enum(["high", "medium", "low"]),
  summary: z.string().optional(),
  tagsText: z.string().optional(),
  issuesText: z.string().optional(),
});

type CaseFormValues = z.infer<typeof caseSchema>;

const emptyValues: CaseFormValues = {
  title: "",
  case_number: "",
  court: "",
  jurisdiction: "",
  status: "active",
  priority: "medium",
  summary: "",
  tagsText: "",
  issuesText: "",
};

function fromCase(c: Case): CaseFormValues {
  return {
    title: c.title,
    case_number: c.case_number ?? "",
    court: c.court ?? "",
    jurisdiction: c.jurisdiction ?? "",
    status: c.status as CaseStatus,
    priority: c.priority,
    summary: c.summary ?? "",
    tagsText: c.tags.join(", "),
    issuesText: c.issues.join("\n"),
  };
}

function toInput(values: CaseFormValues): CaseCreateInput {
  const splitList = (text: string | undefined) =>
    (text ?? "")
      .split(/[\n,]/)
      .map((s) => s.trim())
      .filter(Boolean);

  return {
    title: values.title.trim(),
    case_number: values.case_number?.trim() || null,
    court: values.court?.trim() || null,
    jurisdiction: values.jurisdiction?.trim() || null,
    status: values.status,
    priority: values.priority,
    summary: values.summary?.trim() || null,
    tags: splitList(values.tagsText),
    issues: splitList(values.issuesText),
  };
}

const fieldClass = "h-8 text-sm";
const textareaClass =
  "flex min-h-[64px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50";

interface CaseFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Present = edit mode; absent = create mode. */
  caseData?: Case;
  onSubmit: (input: CaseCreateInput) => Promise<void>;
  /** Error message from the submit mutation, shown inside the dialog. */
  error?: string | null;
}

export function CaseFormDialog({
  open,
  onOpenChange,
  caseData,
  onSubmit,
  error,
}: CaseFormDialogProps) {
  const isEdit = !!caseData;
  const [confirmCancel, setConfirmCancel] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors, isSubmitting, isDirty },
  } = useForm<CaseFormValues>({
    resolver: zodResolver(caseSchema),
    defaultValues: caseData ? fromCase(caseData) : emptyValues,
  });

  // Reset the form each time the dialog opens for a different purpose.
  useEffect(() => {
    if (open) {
      reset(caseData ? fromCase(caseData) : emptyValues);
    }
  }, [open, caseData, reset]);

  const onValid = handleSubmit(async (values) => {
    await onSubmit(toInput(values));
    onOpenChange(false);
  });

  const submitForm = (e: React.FormEvent) => {
    e.preventDefault();
    // Errors from the submit mutation are surfaced via the `error` prop;
    // swallow the rejection here to avoid unhandled promise warnings.
    void onValid(e).catch(() => undefined);
  };

  const dirtyCount = [
    watch("title"),
    watch("case_number"),
    watch("court"),
    watch("jurisdiction"),
    watch("summary"),
    watch("tagsText"),
    watch("issuesText"),
  ].filter((v) => v && v.trim()).length;

  const handleDialogChange = (next: boolean) => {
    if (!next && isDirty && !isSubmitting) {
      setConfirmCancel(true); // ask before discarding changes
      return;
    }
    onOpenChange(next);
  };

  return (
    <>
      <Dialog open={open} onOpenChange={handleDialogChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{isEdit ? "Edit case" : "New case"}</DialogTitle>
            <DialogDescription>
              {isEdit
                ? "Update the case details. Changes are saved to your workspace immediately."
                : "Create a case workspace. It will be visible only to you."}
            </DialogDescription>
          </DialogHeader>

          {error && (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-800"
            >
              <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              {error}
            </div>
          )}

          <form
            onSubmit={submitForm}
            noValidate
            className="grid gap-4"
          >
            <div className="grid gap-1.5">
              <Label htmlFor="case-title">Title *</Label>
              <Input
                id="case-title"
                placeholder="e.g. Sharma vs. Municipal Corporation"
                aria-invalid={!!errors.title}
                {...register("title")}
                className={fieldClass}
              />
              {errors.title && (
                <p className="text-xs text-red-700" role="alert">
                  {errors.title.message}
                </p>
              )}
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="grid gap-1.5">
                <Label htmlFor="case-number">Case number</Label>
                <Input
                  id="case-number"
                  placeholder="WP/4521/2024"
                  {...register("case_number")}
                  className={fieldClass}
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="case-court">Court</Label>
                <Input
                  id="case-court"
                  placeholder="High Court of Delhi"
                  {...register("court")}
                  className={fieldClass}
                />
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <div className="grid gap-1.5">
                <Label htmlFor="case-status">Status</Label>
                <select
                  id="case-status"
                  {...register("status")}
                  className="h-8 rounded-md border border-input bg-background px-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <option value="active">Active</option>
                  <option value="review">Under review</option>
                  <option value="closed">Closed</option>
                  <option value="archived">Archived</option>
                </select>
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="case-priority">Priority</Label>
                <select
                  id="case-priority"
                  {...register("priority")}
                  className="h-8 rounded-md border border-input bg-background px-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="case-jurisdiction">Jurisdiction</Label>
                <Input
                  id="case-jurisdiction"
                  placeholder="India"
                  {...register("jurisdiction")}
                  className={fieldClass}
                />
              </div>
            </div>

            <div className="grid gap-1.5">
              <Label htmlFor="case-summary">Summary</Label>
              <textarea
                id="case-summary"
                placeholder="Brief factual and procedural background…"
                {...register("summary")}
                className={textareaClass}
                rows={3}
              />
            </div>

            <div className="grid gap-1.5">
              <Label htmlFor="case-tags">Tags</Label>
              <Input
                id="case-tags"
                placeholder="Land Acquisition, Constitutional"
                {...register("tagsText")}
                className={fieldClass}
              />
              <p className="text-[11px] text-muted-foreground">Comma-separated.</p>
            </div>

            <div className="grid gap-1.5">
              <Label htmlFor="case-issues">Legal issues</Label>
              <textarea
                id="case-issues"
                placeholder={"One issue per line, e.g.\nValidity of Section 4 notification"}
                {...register("issuesText")}
                className={textareaClass}
                rows={3}
              />
              <p className="text-[11px] text-muted-foreground">One issue per line.</p>
            </div>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => (isDirty ? setConfirmCancel(true) : onOpenChange(false))}
                disabled={isSubmitting}
              >
                Cancel
              </Button>
              <Button type="submit" variant="teal" size="sm" disabled={isSubmitting}>
                {isSubmitting && (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                )}
                {isEdit ? "Save changes" : "Create case"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Unsaved-changes confirmation */}
      <AlertDialog open={confirmCancel} onOpenChange={setConfirmCancel}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Discard unsaved changes?</AlertDialogTitle>
            <AlertDialogDescription>
              {isEdit
                ? "Your edits to this case will be lost."
                : "The new case details you entered will be lost."}
              {dirtyCount > 0 && ` ${dirtyCount} field(s) were filled in.`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setConfirmCancel(false)}>
              Keep editing
            </AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                setConfirmCancel(false);
                onOpenChange(false);
              }}
            >
              Discard
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
