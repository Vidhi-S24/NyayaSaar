import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, FileText, AlertTriangle, Brain, Scale, Gavel, BookOpen } from "lucide-react";
import { DEMO_CASES, DEMO_DOCUMENTS } from "@/lib/demo-data";
import { DemoNotice } from "@/components/shared/demo-notice";
import { CaseStatusBadge, PriorityDot } from "@/components/shared/case-ui";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

interface CasePageProps {
  params: Promise<{ id: string }>;
}

export async function generateStaticParams() {
  return DEMO_CASES.map((c) => ({ id: c.id }));
}

export async function generateMetadata({ params }: CasePageProps) {
  const { id } = await params;
  const c = DEMO_CASES.find((c) => c.id === id);
  return { title: c ? c.title : "Case Not Found" };
}

export default async function CasePage({ params }: CasePageProps) {
  const { id } = await params;
  const c = DEMO_CASES.find((c) => c.id === id);
  if (!c) notFound();

  const docs = DEMO_DOCUMENTS.filter((d) => d.caseId === c.id);

  const modules = [
    { href: "/intelligence", label: "Case Intelligence", icon: Brain, desc: "Extract facts & issues" },
    { href: "/contradictions", label: "Contradiction & Gap", icon: AlertTriangle, desc: "Detect conflicts" },
    { href: "/precedents", label: "Precedent Explorer", icon: BookOpen, desc: "Find authorities" },
    { href: "/advocate", label: "Advocate Mode", icon: Scale, desc: "Build arguments" },
    { href: "/judge", label: "Judge / Clerk", icon: Gavel, desc: "Audit analysis" },
  ];

  return (
    <div className="flex flex-col gap-6 p-6 pb-10">
      <DemoNotice />

      {/* Back + title */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
        <Button asChild variant="ghost" size="sm" className="-ml-2 w-fit">
          <Link href="/cases">
            <ArrowLeft className="h-3.5 w-3.5" />
            Cases
          </Link>
        </Button>
      </div>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-2.5">
          <PriorityDot priority={c.priority} className="mt-2" />
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-foreground">{c.title}</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {c.caseNumber} · {c.court}
            </p>
          </div>
        </div>
        <CaseStatusBadge status={c.status} />
      </div>

      {/* Tags */}
      <div className="flex flex-wrap gap-1.5">
        {c.tags.map((tag) => (
          <Badge key={tag} variant="secondary">{tag}</Badge>
        ))}
      </div>

      {/* Summary */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Summary
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-foreground/80 leading-relaxed">{c.summary}</p>
        </CardContent>
      </Card>

      {/* Intelligence modules */}
      <div>
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Run Analysis — Stage 5
        </p>
        <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-5">
          {modules.map((mod) => {
            const Icon = mod.icon;
            return (
              <Link
                key={mod.href}
                href={mod.href}
                className="group flex flex-col gap-1 rounded-lg border border-border bg-card p-4 transition-colors hover:border-teal-300 hover:bg-teal-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <Icon className="h-4 w-4 text-muted-foreground group-hover:text-teal-700" aria-hidden="true" />
                <span className="text-sm font-medium text-foreground">{mod.label}</span>
                <span className="text-xs text-muted-foreground">{mod.desc}</span>
              </Link>
            );
          })}
        </div>
      </div>

      <Separator />

      {/* Tabs */}
      <Tabs defaultValue="issues">
        <TabsList>
          <TabsTrigger value="issues">Legal Issues ({c.issues.length})</TabsTrigger>
          <TabsTrigger value="documents">Documents ({docs.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="issues">
          <div className="mt-4 divide-y divide-border rounded-lg border border-border bg-card">
            {c.issues.map((issue, i) => (
              <div key={i} className="flex items-start gap-3 px-5 py-3.5">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-secondary text-[10px] font-semibold text-muted-foreground">
                  {i + 1}
                </span>
                <p className="text-sm text-foreground">{issue}</p>
              </div>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="documents">
          {docs.length === 0 ? (
            <div className="mt-4 flex flex-col items-center gap-2 py-10 text-center">
              <FileText className="h-8 w-8 text-muted-foreground/40" aria-hidden="true" />
              <p className="text-sm text-muted-foreground">No documents uploaded yet.</p>
            </div>
          ) : (
            <div className="mt-4 divide-y divide-border rounded-lg border border-border bg-card">
              {docs.map((doc) => (
                <div key={doc.id} className="flex items-center gap-3 px-5 py-3.5">
                  <FileText className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-foreground">{doc.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {doc.pages} pages · {doc.size} · {doc.uploadedAt}
                    </p>
                  </div>
                  <Badge
                    variant={
                      doc.status === "processed"
                        ? "success"
                        : doc.status === "processing"
                        ? "warning"
                        : doc.status === "error"
                        ? "destructive"
                        : "outline"
                    }
                    className="shrink-0"
                  >
                    {doc.status}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

