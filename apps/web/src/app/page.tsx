import Link from "next/link";
import { ArrowRight, Scale, Brain, AlertTriangle, BookOpen, Gavel, Shield } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

/**
 * Landing page / home — NyayaSaar Stage 2 premium UI.
 * Clearly labelled as a research tool; no AI results displayed on this screen.
 */

const modules = [
  { icon: Brain, title: "Case Intelligence", desc: "Upload documents, extract facts and legal issues, find relevant authorities, generate source-linked analysis." },
  { icon: AlertTriangle, title: "Contradiction & Gap Hunter", desc: "Build timelines, detect conflicting statements, identify missing evidence, flag unsupported assertions." },
  { icon: BookOpen, title: "Precedent Explorer", desc: "Search legal authorities, explore citation relationships, analyse conflicting reasoning." },
  { icon: Scale, title: "Advocate Mode", desc: "Develop opposing arguments, identify supporting and opposing authorities, expose evidentiary gaps." },
  { icon: Gavel, title: "Judge / Clerk Mode", desc: "Audit issue coverage, reasoning consistency, source support, and unresolved questions." },
];

export default function HomePage() {
  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-10 flex h-14 items-center border-b border-border bg-background/95 px-6 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="flex items-center gap-2.5">
          <span className="inline-block h-5 w-0.5 rounded-full bg-teal-600" aria-hidden="true" />
          <span className="font-serif text-lg font-semibold tracking-tight text-foreground">NyayaSaar</span>
        </div>
        <nav className="ml-auto flex items-center gap-2" aria-label="Top navigation">
          <Button asChild variant="ghost" size="sm"><Link href="/dashboard">Sign In</Link></Button>
          <Button asChild size="sm" variant="teal">
            <Link href="/dashboard">Enter Workspace <ArrowRight className="h-3.5 w-3.5" /></Link>
          </Button>
        </nav>
      </header>

      <main>
        <section className="px-6 py-20 text-center lg:py-28">
          <div className="mx-auto max-w-3xl">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-border bg-secondary px-3 py-1 text-xs text-muted-foreground">
              <span className="h-1.5 w-1.5 rounded-full bg-teal-500" aria-hidden="true" />
              Research tool · Not legal advice
            </div>
            <h1 className="font-serif text-4xl font-semibold leading-tight tracking-tight text-foreground lg:text-5xl">
              Legal case intelligence,{" "}
              <span className="text-teal-600">source-linked</span> and{" "}
              <span className="text-teal-600">verifiable</span>
            </h1>
            <p className="mx-auto mt-5 max-w-xl text-base text-muted-foreground">
              NyayaSaar is a multi-agent legal research platform. Upload case documents, detect contradictions, explore precedents, and generate analysis — all grounded in your materials, never fabricated.
            </p>
            <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
              <Button asChild size="lg" variant="teal">
                <Link href="/dashboard">Open Workspace <ArrowRight className="h-4 w-4" /></Link>
              </Button>
              <Button asChild size="lg" variant="outline">
                <Link href="/cases">View Demo Cases</Link>
              </Button>
            </div>
          </div>
        </section>

        <Separator className="mx-6 lg:mx-16" />

        <section className="px-6 py-16" aria-labelledby="modules-heading">
          <div className="mx-auto max-w-5xl">
            <h2 id="modules-heading" className="mb-2 text-center font-serif text-2xl font-semibold text-foreground">Five intelligence modules</h2>
            <p className="mb-10 text-center text-sm text-muted-foreground">Each module operates on your uploaded documents. No external data is fabricated.</p>
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {modules.map((mod) => {
                const Icon = mod.icon;
                return (
                  <div key={mod.title} className="flex flex-col gap-3 rounded-lg border border-border bg-card p-6">
                    <div className="flex h-9 w-9 items-center justify-center rounded-md bg-ink-800 text-white">
                      <Icon className="h-4 w-4" aria-hidden="true" />
                    </div>
                    <h3 className="font-medium text-foreground">{mod.title}</h3>
                    <p className="text-sm text-muted-foreground leading-relaxed">{mod.desc}</p>
                  </div>
                );
              })}
              <div className="flex flex-col gap-3 rounded-lg border border-teal-200 bg-teal-50 p-6">
                <div className="flex h-9 w-9 items-center justify-center rounded-md bg-teal-600 text-white">
                  <Shield className="h-4 w-4" aria-hidden="true" />
                </div>
                <h3 className="font-medium text-teal-900">Built on verifiable AI</h3>
                <p className="text-sm text-teal-800 leading-relaxed">Gemini + LangGraph + pgvector. Source IDs and page references preserved. No fabricated citations, no hallucinated holdings.</p>
              </div>
            </div>
          </div>
        </section>

        <Separator className="mx-6 lg:mx-16" />

        <section className="px-6 py-12 text-center">
          <p className="mx-auto max-w-2xl text-xs text-muted-foreground leading-relaxed">
            <strong>Important:</strong> NyayaSaar is a legal research assistance tool. It does not constitute legal advice, does not replace qualified counsel, and all outputs must be independently verified by a qualified legal professional before use in any proceedings. The platform never fabricates legal authorities, citations, statutes, or holdings.
          </p>
        </section>
      </main>

      <footer className="border-t border-border px-6 py-5">
        <div className="flex flex-col items-center gap-2 text-xs text-muted-foreground sm:flex-row sm:justify-between">
          <span className="font-serif font-medium text-foreground/60">NyayaSaar</span>
          <span>Research tool only · Professional verification required</span>
        </div>
      </footer>
    </div>
  );
}


