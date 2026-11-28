"use client";

/**
 * Dashboard — live statistics from the authenticated user's real cases.
 *
 * Statistics that depend on document processing or cross-case AI aggregation
 * are shown honestly as unavailable — no fake numbers.
 */

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  FolderOpen,
  FileText,
  AlertTriangle,
  TrendingUp,
  Clock,
  Plus,
  ArrowRight,
} from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { StatCard, CaseStatusBadge, PriorityDot, EmptyState } from "@/components/shared/case-ui";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { listCases, formatRelativeTime } from "@/lib/api/cases";
import { ApiClientError } from "@/lib/api-client";
import type { Case } from "@nyayasaar/shared";

function computeStats(cases: Case[]) {
  const active = cases.filter((c) => c.status === "active").length;
  const review = cases.filter((c) => c.status === "review").length;
  const documents = cases.reduce((sum, c) => sum + c.documents_count, 0);
  return { total: cases.length, active, review, documents };
}

export default function DashboardPage() {
  const casesQuery = useQuery({
    queryKey: ["cases", { page: 1, page_size: 100 }],
    queryFn: () => listCases({ page: 1, page_size: 100 }),
    select: (envelope) => envelope.data,
  });

  const cases = casesQuery.data?.items ?? [];
  const stats = computeStats(cases);
  const recentCases = [...cases]
    .sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1))
    .slice(0, 5);

  const activeCasesList = recentCases.filter((c) => c.status === "active");
  const shownCases = activeCasesList.length > 0 ? activeCasesList : recentCases;

  return (
    <div className="flex flex-col gap-6 p-6 pb-10">
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
          label="Total Cases"
          value={casesQuery.isLoading ? <Skeleton className="h-8 w-12" /> : stats.total}
          icon={<FolderOpen className="h-4 w-4" />}
          trend={`${stats.active} active · ${stats.review} under review`}
        />
        <StatCard
          label="Documents"
          value={casesQuery.isLoading ? <Skeleton className="h-8 w-12" /> : stats.documents}
          icon={<FileText className="h-4 w-4" />}
          trend="Upload in any case workspace"
        />
        <StatCard
          label="Reports Generated"
          value="—"
          icon={<TrendingUp className="h-4 w-4" />}
          trend="Run analyses from Case Intelligence"
        />
        <StatCard
          label="Contradictions Found"
          value="—"
          icon={<AlertTriangle className="h-4 w-4" />}
          trend="Run analyses in Contradiction & Gap Hunter"
        />
      </div>

      {/* Error state */}
      {casesQuery.isError && (
        <div className="flex flex-col items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-6 py-8 text-center">
          <AlertTriangle className="h-5 w-5 text-red-600" aria-hidden="true" />
          <div>
            <p className="text-sm font-medium text-red-900">Could not load your cases</p>
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

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Recent / active cases */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                  {activeCasesList.length > 0 ? "Active Cases" : "Recently Updated Cases"}
                </CardTitle>
                <Button asChild variant="ghost" size="sm" className="text-xs text-muted-foreground">
                  <Link href="/cases">
                    View all <ArrowRight className="ml-1 h-3 w-3" />
                  </Link>
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {casesQuery.isLoading ? (
                <div className="divide-y divide-border">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <div key={i} className="flex items-start gap-3 px-6 py-4">
                      <Skeleton className="mt-1.5 h-2 w-2 rounded-full" />
                      <div className="flex-1 space-y-1.5">
                        <Skeleton className="h-3.5 w-2/3" />
                        <Skeleton className="h-2.5 w-1/3" />
                      </div>
                      <Skeleton className="h-5 w-16 rounded-full" />
                    </div>
                  ))}
                </div>
              ) : shownCases.length === 0 ? (
                <EmptyState
                  icon={<FolderOpen className="h-5 w-5" />}
                  title="No cases yet"
                  description="Create your first case workspace to get started."
                  action={
                    <Button variant="teal" size="sm" asChild>
                      <Link href="/cases">
                        <Plus className="h-3.5 w-3.5" />
                        New Case
                      </Link>
                    </Button>
                  }
                />
              ) : (
                <div className="divide-y divide-border">
                  {shownCases.map((c) => (
                    <Link
                      key={c.id}
                      href={`/cases/${c.id}`}
                      className="flex items-start gap-3 px-6 py-4 transition-colors hover:bg-secondary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
                    >
                      <PriorityDot priority={c.priority} className="mt-1.5 shrink-0" />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-foreground">{c.title}</p>
                        <p className="mt-0.5 text-xs text-muted-foreground">
                          {[c.case_number, c.court].filter(Boolean).join(" · ") || "—"}
                        </p>
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-1.5">
                        <CaseStatusBadge status={c.status} />
                        <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
                          <Clock className="h-3 w-3" />
                          {formatRelativeTime(c.updated_at)}
                        </span>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Activity feed — honest empty state until activity tracking lands */}
        <div>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                Recent Activity
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="px-5 pb-5">
                <EmptyState
                  title="No activity yet"
                  description="Uploads and analyses are visible in their case workspaces. A cross-case activity feed is not yet persisted."
                />
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
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          {[
            { href: "/intelligence", label: "Case Intelligence", desc: "Run source-linked analysis", stage: "Live" },
            { href: "/research", label: "Legal Research", desc: "Hybrid lexical & semantic search", stage: "Live" },
            { href: "/contradictions", label: "Contradiction & Gap", desc: "Detect conflicts, missing evidence", stage: "Live" },
            { href: "/precedents", label: "Precedent Explorer", desc: "Search legal authorities", stage: "Live" },
            { href: "/advocate", label: "Advocate Mode", desc: "Build opposing arguments", stage: "Stage 10" },
            { href: "/judge", label: "Judge / Clerk", desc: "Audit reasoning and coverage", stage: "Stage 10" },
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
              <Badge
                variant={mod.stage === "Live" ? "success" : "outline"}
                className="mt-1 w-fit text-[10px]"
              >
                {mod.stage}
              </Badge>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
