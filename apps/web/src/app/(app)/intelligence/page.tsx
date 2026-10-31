import { Brain, Upload } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { DemoNotice } from "@/components/shared/demo-notice";
import { ComingSoonState } from "@/components/shared/case-ui";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

export const metadata = { title: "Case Intelligence" };

export default function IntelligencePage() {
  return (
    <div className="flex flex-col gap-6 p-6 pb-10">
      <DemoNotice message="Case Intelligence requires the Gemini/LangGraph backend (Stage 5). Navigation and interface are fully functional; AI analysis is not yet connected." />

      <PageHeader
        title="Case Intelligence"
        description="Upload documents, extract facts and legal issues, find relevant authorities, generate source-linked analysis."
        actions={
          <Button size="sm" variant="teal" disabled>
            <Upload className="h-3.5 w-3.5" />
            Upload Document
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-3">
        {[
          { title: "Fact Extraction", desc: "Extract material facts from uploaded documents with source page references." },
          { title: "Issue Identification", desc: "Identify legal issues, applicable statutes, and question frames." },
          { title: "Authority Research", desc: "Find relevant legal authorities from your configured corpus." },
        ].map((step, i) => (
          <Card key={i}>
            <CardHeader className="pb-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-ink-800 text-xs font-semibold text-white">
                {i + 1}
              </span>
              <CardTitle className="text-sm">{step.title}</CardTitle>
              <CardDescription className="text-xs">{step.desc}</CardDescription>
            </CardHeader>
          </Card>
        ))}
      </div>

      <Card>
        <CardContent className="p-0">
          <ComingSoonState feature="Case Intelligence — AI Analysis" />
        </CardContent>
      </Card>
    </div>
  );
}

