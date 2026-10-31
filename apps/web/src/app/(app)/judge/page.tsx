import { Gavel } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { DemoNotice } from "@/components/shared/demo-notice";
import { ComingSoonState } from "@/components/shared/case-ui";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

export const metadata = { title: "Judge / Clerk Mode" };

export default function JudgePage() {
  return (
    <div className="flex flex-col gap-6 p-6 pb-10">
      <DemoNotice message="Judge/Clerk Mode requires the Gemini/LangGraph backend (Stage 5). This is an analytical audit tool — it does not simulate or replace judicial decision-making." />

      <PageHeader
        title="Judge / Clerk Mode"
        description="Audit issue coverage, reasoning consistency, source support, citations, and unresolved questions."
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {[
          { title: "Issue Coverage Audit", desc: "Check that all raised legal issues are addressed with reasoned analysis." },
          { title: "Reasoning Consistency", desc: "Flag internal inconsistencies in legal reasoning across documents." },
          { title: "Source Support Check", desc: "Verify that each assertion is grounded in cited authority or evidence." },
          { title: "Citation Integrity", desc: "Audit citations for format, completeness, and consistency." },
          { title: "Evidence References", desc: "Map factual claims to their evidentiary basis." },
          { title: "Unresolved Questions", desc: "List issues or arguments that lack a clear resolution." },
        ].map((f, i) => (
          <Card key={i}>
            <CardHeader>
              <Gavel className="h-4 w-4 text-ink-800" aria-hidden="true" />
              <CardTitle className="text-sm">{f.title}</CardTitle>
              <CardDescription className="text-xs">{f.desc}</CardDescription>
            </CardHeader>
          </Card>
        ))}
      </div>

      <Card>
        <CardContent className="p-0">
          <ComingSoonState feature="Judge / Clerk Mode — Analytical Audit" />
        </CardContent>
      </Card>
    </div>
  );
}

