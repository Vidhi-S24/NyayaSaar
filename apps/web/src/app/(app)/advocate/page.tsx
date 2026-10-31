import { Scale } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { DemoNotice } from "@/components/shared/demo-notice";
import { ComingSoonState } from "@/components/shared/case-ui";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

export const metadata = { title: "Advocate Mode" };

export default function AdvocatePage() {
  return (
    <div className="flex flex-col gap-6 p-6 pb-10">
      <DemoNotice message="Advocate Mode requires the Gemini/LangGraph backend (Stage 5). This module develops arguments from uploaded case materials only — it does not provide legal advice." />

      <PageHeader
        title="Advocate Mode"
        description="Develop opposing arguments, identify supporting and opposing authorities, expose evidentiary gaps."
      />

      <div className="grid gap-4 sm:grid-cols-2">
        {[
          { title: "Argument Development", desc: "Build case arguments grounded in uploaded documents. Flags unsupported assertions." },
          { title: "Counter-Argument Analysis", desc: "Anticipate opposing positions and identify vulnerabilities." },
          { title: "Authority Mapping", desc: "Match arguments to supporting and opposing legal authorities from corpus." },
          { title: "Evidentiary Gap Report", desc: "Identify claims lacking evidentiary support in uploaded materials." },
        ].map((f, i) => (
          <Card key={i}>
            <CardHeader>
              <Scale className="h-4 w-4 text-ink-700" aria-hidden="true" />
              <CardTitle className="text-sm">{f.title}</CardTitle>
              <CardDescription className="text-xs">{f.desc}</CardDescription>
            </CardHeader>
          </Card>
        ))}
      </div>

      <div className="rounded-lg border border-border bg-secondary/50 p-4 text-xs text-muted-foreground">
        <strong>Research tool only.</strong> Advocate Mode assists with legal research and argument preparation. It does not constitute legal advice, does not replace counsel, and must not be used to file documents autonomously.
      </div>

      <Card>
        <CardContent className="p-0">
          <ComingSoonState feature="Advocate Mode — Argument Analysis" />
        </CardContent>
      </Card>
    </div>
  );
}

