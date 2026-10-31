import {
  FolderOpen,
  FileText,
  AlertTriangle,
  TrendingUp,
  Clock,
  Plus,
  ArrowRight,
} from "lucide-react";
import Link from "next/link";
import { DEMO_CASES, DEMO_ACTIVITY, DEMO_STATS } from "@/lib/demo-data";
import { PageHeader } from "@/components/shared/page-header";
import { DemoNotice } from "@/components/shared/demo-notice";
import { StatCard, CaseStatusBadge, PriorityDot } from "@/components/shared/case-ui";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";

export const metadata = { title: "Dashboard" };

const activityIcons: Record<string, string> = {
  document_uploaded: "📄",
  analysis_complete: "✅",
  case_created: "📁",
  report_saved: "💾",
  contradiction_found: "⚠️",
};

export default function DashboardPage() {
  const activeCases = DEMO_CASES.filter((c) => c.status === "active");

  return (
    <div className="flex flex-col gap-6 p-6 pb-10">
      <DemoNotice />

      <PageHeader
        title="Dashboard"
        description="Legal case intelligence workspace"
        actions={
          <Button asChild size="sm" variant="teal">
            <Link href="/cases">
              <Plus className="h-3.5 w-3.5" />
              New Case
            </Link>
          </Button>
        }
      />

      {/* Stats row */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Active Cases"
          value={DEMO_STATS.activeCases}
          icon={<FolderOpen className="h-4 w-4" />}
          trend="3 in progress"
        />
        <StatCard
          label="Documents Processed"
          value={DEMO_STATS.documentsProcessed}
          icon={<FileText className="h-4 w-4" />}
          trend="Across all workspaces"
        />
        <StatCard
          label="Reports Generated"
          value={DEMO_STATS.reportsGenerated}
          icon={<TrendingUp className="h-4 w-4" />}
          trend="This month"
        />
        <StatCard
          label="Contradictions Found"
          value={DEMO_STATS.contradictionsFound}
          icon={<AlertTriangle className="h-4 w-4" />}
          trend="Across all cases"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Active cases */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                  Active Cases
                </CardTitle>
                <Button asChild variant="ghost" size="sm" className="text-xs text-muted-foreground">
                  <Link href="/cases">
                    View all <ArrowRight className="ml-1 h-3 w-3" />
                  </Link>
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <div className="divide-y divide-border">
                {activeCases.map((c) => (
                  <Link
                    key={c.id}
                    href={`/cases/${c.id}`}
                    className="flex items-start gap-3 px-6 py-4 transition-colors hover:bg-secondary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
                  >
                    <PriorityDot priority={c.priority} className="mt-1.5 shrink-0" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-foreground">{c.title}</p>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        {c.caseNumber} · {c.court}
                      </p>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-1.5">
                      <CaseStatusBadge status={c.status} />
                      <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
                        <Clock className="h-3 w-3" />
                        {c.lastActivity}
                      </span>
                    </div>
                  </Link>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Activity feed */}
        <div>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                Recent Activity
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="divide-y divide-border">
                {DEMO_ACTIVITY.map((act) => (
                  <div key={act.id} className="px-5 py-3.5">
                    <div className="flex items-start gap-2.5">
                      <span className="mt-0.5 text-sm" aria-hidden="true">
                        {activityIcons[act.type]}
                      </span>
                      <div className="min-w-0">
                        <p className="text-xs font-medium text-foreground leading-snug">
                          {act.description}
                        </p>
                        <p className="mt-1 text-[10px] text-muted-foreground">
                          {act.caseTitle}
                        </p>
                        <p className="text-[10px] text-muted-foreground/60">{act.timestamp}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Quick access modules */}
      <div>
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Intelligence Modules
        </p>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {[
            { href: "/intelligence", label: "Case Intelligence", desc: "Extract facts, issues, authorities" },
            { href: "/contradictions", label: "Contradiction & Gap", desc: "Detect conflicts, missing evidence" },
            { href: "/precedents", label: "Precedent Explorer", desc: "Citation relationships, authorities" },
            { href: "/advocate", label: "Advocate Mode", desc: "Opposing arguments, evidentiary gaps" },
            { href: "/judge", label: "Judge / Clerk", desc: "Audit reasoning, issue coverage" },
          ].map((mod) => (
            <Link
              key={mod.href}
              href={mod.href}
              className="group flex flex-col gap-1 rounded-lg border border-border bg-card p-4 transition-colors hover:border-teal-300 hover:bg-teal-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <span className="text-sm font-medium text-foreground group-hover:text-teal-800">
                {mod.label}
              </span>
              <span className="text-xs text-muted-foreground">{mod.desc}</span>
              <Badge variant="outline" className="mt-1 w-fit text-[10px]">
                Stage 5
              </Badge>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

