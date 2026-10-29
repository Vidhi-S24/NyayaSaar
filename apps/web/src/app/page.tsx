/**
 * Root page — minimal app shell for Stage 1.
 * Stage 2 will replace this with the full dashboard experience.
 */
export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-background px-6">
      <div className="max-w-lg text-center">
        {/* Wordmark */}
        <div className="mb-8 flex items-center justify-center gap-3">
          <span className="inline-block h-8 w-1 rounded-full bg-accent" aria-hidden="true" />
          <h1 className="font-serif text-4xl font-semibold tracking-tight text-foreground">
            NyayaSaar
          </h1>
        </div>

        <p className="mb-2 text-lg font-medium text-foreground/80">
          Legal Case Intelligence Platform
        </p>
        <p className="text-sm text-muted-foreground">
          Multi-agent analysis · Precedent reasoning · Source-linked findings
        </p>

        {/* Status badge */}
        <div className="mt-10 inline-flex items-center gap-2 rounded-full border border-border bg-card px-4 py-2 text-xs text-muted-foreground">
          <span className="h-2 w-2 rounded-full bg-teal-500 animate-pulse" aria-hidden="true" />
          Foundation ready — Stage 2 builds the full interface
        </div>

        {/* Disclaimer */}
        <p className="mt-10 text-xs text-muted-foreground/70">
          Research tool only. All outputs require professional legal verification.
        </p>
      </div>
    </main>
  );
}

