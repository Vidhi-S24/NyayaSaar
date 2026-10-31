import { AlertTriangle } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { DemoNotice } from "@/components/shared/demo-notice";
import { ComingSoonState } from "@/components/shared/case-ui";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

export const metadata = { title: "Contradiction & Gap Hunter" };

export default function ContradictionsPage() {
  return (
    <div className="flex flex-col gap-6 p-6 pb-10">
      <DemoNotice message="Contradiction & Gap Hunter requires the Gemini/LangGraph backend (Stage 5). Interface is ready; AI analysis is not yet connected." />

      <PageHeader
        title="Contradiction & Gap Hunter"
        description="Build timelines, compare documents, detect conflicting statements and dates, identify missing evidence."
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { title: "Timeline Builder", desc: "Auto-extract and order events from documents." },
          { title: "Conflict Detection", desc: "Flag contradictory facts and inconsistent dates." },
          { title: "Evidence Gaps", desc: "Identify claims unsupported by uploaded evidence." },
          { title: "Assertion Audit", desc: "List assertions without documentary backing." },
        ].map((f, i) => (
          <Card key={i}>
            <CardHeader>
              <AlertTriangle className="h-4 w-4 text-amber-500" aria-hidden="true" />
              <CardTitle className="text-sm">{f.title}</CardTitle>
              <CardDescription className="text-xs">{f.desc}</CardDescription>
            </CardHeader>
          </Card>
        ))}
      </div>

      <Card>
        <CardContent className="p-0">
          <ComingSoonState feature="Contradiction & Gap Hunter — AI Analysis" />
        </CardContent>
      </Card>
    </div>
  );
}

