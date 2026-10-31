import { History, FileDown } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { DemoNotice } from "@/components/shared/demo-notice";
import { DEMO_ACTIVITY } from "@/lib/demo-data";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export const metadata = { title: "Research History" };

const typeLabels: Record<string, { label: string; variant: "success" | "warning" | "secondary" | "outline" }> = {
  analysis_complete: { label: "Analysis", variant: "success" },
  contradiction_found: { label: "Contradiction", variant: "warning" },
  document_uploaded: { label: "Document", variant: "secondary" },
  report_saved: { label: "Report", variant: "secondary" },
  case_created: { label: "Case", variant: "outline" },
};

export default function HistoryPage() {
  return (
    <div className="flex flex-col gap-6 p-6 pb-10">
      <DemoNotice />

      <PageHeader
        title="Research History"
        description="Reports, analyses, and saved research sessions"
        actions={
          <Button variant="outline" size="sm" disabled>
            <FileDown className="h-3.5 w-3.5" />
            Export — Stage 5
          </Button>
        }
      />

      <div className="overflow-hidden rounded-lg border border-border bg-card">
        <div className="divide-y divide-border">
          {DEMO_ACTIVITY.map((act) => {
            const meta = typeLabels[act.type] ?? { label: act.type, variant: "outline" as const };
            return (
              <div key={act.id} className="flex items-center gap-4 px-5 py-4">
                <Badge variant={meta.variant} className="shrink-0 text-[10px]">
                  {meta.label}
                </Badge>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-foreground">{act.description}</p>
                  <p className="text-xs text-muted-foreground">{act.caseTitle}</p>
                </div>
                <span className="shrink-0 text-xs text-muted-foreground">{act.timestamp}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

