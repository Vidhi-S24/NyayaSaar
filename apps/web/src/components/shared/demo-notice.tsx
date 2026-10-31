import { cn } from "@/lib/utils";
import { AlertTriangle } from "lucide-react";

interface DemoNoticeProps {
  className?: string;
  message?: string;
}

export function DemoNotice({ className, message }: DemoNoticeProps) {
  return (
    <div
      className={cn(
        "flex items-start gap-2.5 rounded-md border border-amber-200 bg-amber-50 px-3.5 py-3 text-xs text-amber-800",
        className
      )}
      role="note"
      aria-label="Demo data notice"
    >
      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      <span>
        {message ??
          "This screen displays development demo data only. It is not connected to real AI analysis, legal research, or verified legal authorities. All outputs require professional legal verification."}
      </span>
    </div>
  );
}

