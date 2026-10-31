import { cn } from "@/lib/utils";
import type { CaseStatus, Priority } from "@/lib/demo-data";
import { Badge } from "@/components/ui/badge";

export function CaseStatusBadge({ status }: { status: CaseStatus }) {
  const config = {
    active: { variant: "success" as const, label: "Active" },
    review: { variant: "warning" as const, label: "Under Review" },
    closed: { variant: "secondary" as const, label: "Closed" },
    archived: { variant: "outline" as const, label: "Archived" },
  };
  const { variant, label } = config[status];
  return <Badge variant={variant}>{label}</Badge>;
}

export function PriorityDot({ priority, className }: { priority: Priority; className?: string }) {
  const colors = {
    high: "bg-red-400",
    medium: "bg-amber-400",
    low: "bg-green-400",
  };
  return (
    <span
      className={cn("inline-block h-2 w-2 rounded-full", colors[priority], className)}
      aria-label={`${priority} priority`}
    />
  );
}

interface StatCardProps {
  label: string;
  value: string | number;
  icon?: React.ReactNode;
  trend?: string;
  className?: string;
}

export function StatCard({ label, value, icon, trend, className }: StatCardProps) {
  return (
    <div
      className={cn(
        "flex flex-col gap-1 rounded-lg border border-border bg-card p-5",
        className
      )}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
        {icon && (
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-secondary text-muted-foreground">
            {icon}
          </span>
        )}
      </div>
      <span className="text-2xl font-semibold tabular-nums text-foreground">{value}</span>
      {trend && <span className="text-xs text-muted-foreground">{trend}</span>}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
      {icon && (
        <span className="flex h-12 w-12 items-center justify-center rounded-full bg-secondary text-muted-foreground">
          {icon}
        </span>
      )}
      <div>
        <p className="text-sm font-medium text-foreground">{title}</p>
        {description && (
          <p className="mt-1 text-xs text-muted-foreground">{description}</p>
        )}
      </div>
      {action}
    </div>
  );
}

export function ComingSoonState({ feature }: { feature: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
      <div className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-secondary">
        <span className="text-lg" aria-hidden="true">⚡</span>
      </div>
      <div>
        <p className="text-sm font-medium text-foreground">{feature}</p>
        <p className="mt-1 text-xs text-muted-foreground">
          This module will be connected in a future stage (Stage 5 — AI/LangGraph).
          <br />
          Navigation and interface are functional; AI analysis is not yet wired.
        </p>
      </div>
    </div>
  );
}

