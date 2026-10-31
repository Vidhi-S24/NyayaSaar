import Link from "next/link";
import { Plus, Filter, Search } from "lucide-react";
import { DEMO_CASES } from "@/lib/demo-data";
import { PageHeader } from "@/components/shared/page-header";
import { DemoNotice } from "@/components/shared/demo-notice";
import { CaseStatusBadge, PriorityDot } from "@/components/shared/case-ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { FileText, Clock } from "lucide-react";

export const metadata = { title: "Cases" };

export default function CasesPage() {
  return (
    <div className="flex flex-col gap-6 p-6 pb-10">
      <DemoNotice />

      <PageHeader
        title="Cases"
        description={`${DEMO_CASES.length} cases in workspace`}
        actions={
          <Button size="sm" variant="teal">
            <Plus className="h-3.5 w-3.5" />
            New Case
          </Button>
        }
      />

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <Input placeholder="Search cases…" className="pl-8 h-8 text-sm" aria-label="Search cases" />
        </div>
        <Button variant="outline" size="sm" className="w-fit">
          <Filter className="h-3.5 w-3.5" />
          Filter
        </Button>
      </div>

      {/* Cases list */}
      <div className="overflow-hidden rounded-lg border border-border bg-card">
        {/* Table header */}
        <div className="grid grid-cols-12 gap-3 border-b border-border bg-secondary/50 px-5 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          <div className="col-span-5">Case</div>
          <div className="col-span-2 hidden sm:block">Court</div>
          <div className="col-span-2">Status</div>
          <div className="col-span-1 text-center">Docs</div>
          <div className="col-span-2 text-right">Last Activity</div>
        </div>

        <div className="divide-y divide-border">
          {DEMO_CASES.map((c) => (
            <Link
              key={c.id}
              href={`/cases/${c.id}`}
              className="grid grid-cols-12 gap-3 px-5 py-4 transition-colors hover:bg-secondary/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
            >
              <div className="col-span-5 flex min-w-0 items-start gap-2.5">
                <PriorityDot priority={c.priority} className="mt-1.5 shrink-0" />
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-foreground">{c.title}</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">{c.caseNumber}</p>
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
                <span className="text-xs text-muted-foreground leading-snug">{c.court}</span>
              </div>

              <div className="col-span-2 flex items-start">
                <CaseStatusBadge status={c.status} />
              </div>

              <div className="col-span-1 flex items-start justify-center">
                <span className="flex items-center gap-1 text-xs text-muted-foreground">
                  <FileText className="h-3 w-3" aria-hidden="true" />
                  {c.documentsCount}
                </span>
              </div>

              <div className="col-span-2 flex items-start justify-end">
                <span className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Clock className="h-3 w-3" aria-hidden="true" />
                  {c.lastActivity}
                </span>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

