import { Upload, Search, Filter, FileText } from "lucide-react";
import { DEMO_DOCUMENTS, DEMO_CASES } from "@/lib/demo-data";
import { PageHeader } from "@/components/shared/page-header";
import { DemoNotice } from "@/components/shared/demo-notice";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

export const metadata = { title: "Documents" };

const statusVariant = (s: string) => {
  if (s === "processed") return "success" as const;
  if (s === "processing") return "warning" as const;
  if (s === "error") return "destructive" as const;
  return "outline" as const;
};

export default function DocumentsPage() {
  const docsWithCase = DEMO_DOCUMENTS.map((d) => ({
    ...d,
    caseName: DEMO_CASES.find((c) => c.id === d.caseId)?.title ?? "—",
  }));

  return (
    <div className="flex flex-col gap-6 p-6 pb-10">
      <DemoNotice />

      <PageHeader
        title="Document Library"
        description={`${DEMO_DOCUMENTS.length} documents across all cases`}
        actions={
          <Button size="sm" variant="teal">
            <Upload className="h-3.5 w-3.5" />
            Upload
          </Button>
        }
      />

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <Input placeholder="Search documents…" className="pl-8 h-8 text-sm" aria-label="Search documents" />
        </div>
        <Button variant="outline" size="sm" className="w-fit">
          <Filter className="h-3.5 w-3.5" />
          Filter
        </Button>
      </div>

      {/* Upload zone */}
      <div
        className="flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed border-border bg-secondary/30 py-10 text-center transition-colors hover:border-teal-400 hover:bg-teal-50/30"
        role="region"
        aria-label="Document upload area"
      >
        <Upload className="h-8 w-8 text-muted-foreground/50" aria-hidden="true" />
        <div>
          <p className="text-sm font-medium text-foreground">Drop documents here or click to browse</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            PDF, DOCX, DOC · Max 50 MB per file · OCR supported for scanned PDFs
          </p>
        </div>
        <Button variant="outline" size="sm" disabled>
          Browse Files — Stage 4
        </Button>
      </div>

      {/* Documents list */}
      <div className="overflow-hidden rounded-lg border border-border bg-card">
        <div className="grid grid-cols-12 gap-3 border-b border-border bg-secondary/50 px-5 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          <div className="col-span-5">Name</div>
          <div className="col-span-3 hidden sm:block">Case</div>
          <div className="col-span-2">Type</div>
          <div className="col-span-1 text-center hidden sm:block">Pages</div>
          <div className="col-span-2 sm:col-span-1 text-right">Status</div>
        </div>
        <div className="divide-y divide-border">
          {docsWithCase.map((doc) => (
            <div
              key={doc.id}
              className="grid grid-cols-12 gap-3 px-5 py-3.5 transition-colors hover:bg-secondary/30"
            >
              <div className="col-span-5 flex items-center gap-2.5 min-w-0">
                <FileText className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-foreground">{doc.name}</p>
                  <p className="text-xs text-muted-foreground">{doc.size}</p>
                </div>
              </div>
              <div className="col-span-3 hidden sm:flex items-center">
                <p className="truncate text-xs text-muted-foreground">{doc.caseName}</p>
              </div>
              <div className="col-span-2 flex items-center">
                <Badge variant="secondary" className="capitalize text-[10px]">
                  {doc.type}
                </Badge>
              </div>
              <div className="col-span-1 hidden sm:flex items-center justify-center">
                <span className="text-xs text-muted-foreground">{doc.pages}</span>
              </div>
              <div className="col-span-2 sm:col-span-1 flex items-center justify-end">
                <Badge variant={statusVariant(doc.status)} className="capitalize text-[10px]">
                  {doc.status}
                </Badge>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

