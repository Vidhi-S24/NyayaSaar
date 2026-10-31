import { BookOpen } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { DemoNotice } from "@/components/shared/demo-notice";
import { ComingSoonState } from "@/components/shared/case-ui";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

export const metadata = { title: "Precedent Explorer" };

export default function PrecedentsPage() {
  return (
    <div className="flex flex-col gap-6 p-6 pb-10">
      <DemoNotice message="Precedent Explorer requires a configured legal corpus and the LangGraph backend (Stage 5–6). When no corpus is configured, the system will clearly say so. These are not real legal research results." />

      <PageHeader
        title="Precedent Explorer"
        description="Search legal authorities, explore citation relationships, analyse conflicting reasoning."
      />

      <div className="grid gap-4 sm:grid-cols-3">
        {[
          { title: "Authority Search", desc: "Search your configured legal corpus. Results clearly indicate source and confidence." },
          { title: "Citation Graph", desc: "Explore how authorities cite each other (requires Neo4j — optional service)." },
          { title: "Conflict Analysis", desc: "Identify potentially conflicting reasoning between authorities." },
        ].map((f, i) => (
          <Card key={i}>
            <CardHeader>
              <BookOpen className="h-4 w-4 text-teal-600" aria-hidden="true" />
              <CardTitle className="text-sm">{f.title}</CardTitle>
              <CardDescription className="text-xs">{f.desc}</CardDescription>
            </CardHeader>
          </Card>
        ))}
      </div>

      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
        <strong>No legal corpus configured.</strong> In production, connect an authorised legal database. The system will clearly indicate when no corpus is available and will never fabricate citations or holdings.
      </div>

      <Card>
        <CardContent className="p-0">
          <ComingSoonState feature="Precedent Explorer — Legal Research" />
        </CardContent>
      </Card>
    </div>
  );
}

