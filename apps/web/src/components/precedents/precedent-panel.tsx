"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  BookOpen,
  Download,
  FileText,
  GitFork,
  Loader2,
  Play,
  RefreshCw,
  Scale,
  Search,
  ShieldAlert,
} from "lucide-react";
import type {
  CitationLink,
  CitationRelationship,
  Document,
  PrecedentAuthority,
  PrecedentCitationPair,
  PrecedentConflict,
  PrecedentResult,
  RetrievalResultItem,
  WorkflowRun,
} from "@nyayasaar/shared";
import {
  downloadCaseReport,
  isWorkflowActive,
  listCitationsForRun,
  listPrecedentAnalyses,
  retryCaseAnalysis,
  saveBlob,
  startPrecedentSearch,
  workflowStatusLabel,
} from "@/lib/api/analysis";
import { listDocuments } from "@/lib/api/documents";
import { getRetrievalStatus, searchLegalRetrieval } from "@/lib/api/retrieval";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";

const RELATIONSHIP_LABELS: Record<CitationRelationship, string> = {
  cites: "Cites",
  cited_by: "Cited by",
  related_issue: "Related issue",
  potentially_conflicting: "Potentially conflicting",
};

function supportBadge(support: string) {
  if (support === "supported") {
    return <Badge variant="success">Verified source</Badge>;
  }
  if (support === "partially_supported") {
    return <Badge variant="warning">Source cited</Badge>;
  }
  return <Badge variant="outline">Unverified / Fixture</Badge>;
}

function CitationGraphView({
  authorities,
  pairs,
  persistedLinks,
  relationshipFilter,
}: {
  authorities: PrecedentAuthority[];
  pairs: PrecedentCitationPair[];
  persistedLinks: CitationLink[];
  relationshipFilter: string;
}) {
  const filteredPairs = useMemo(() => {
    if (relationshipFilter === "all") return pairs;
    return pairs.filter((p) => p.relationship_type === relationshipFilter);
  }, [pairs, relationshipFilter]);

  if (filteredPairs.length === 0 && persistedLinks.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-muted/20 p-6 text-center text-sm text-muted-foreground">
        <GitFork className="mx-auto mb-2 h-6 w-6 text-muted-foreground/70" />
        <p className="font-medium text-foreground">
          No citation graph edges available for this filter
        </p>
        <p className="mt-1 text-xs">
          Neo4j is optional — when graph data or subsequent-treatment metadata is
          unavailable, NyayaSaar uses the in-database citation index and never
          fabricates relationships.
        </p>
      </div>
    );
  }

  // Build unique nodes for a clean SVG citation map
  const nodeNames = Array.from(
    new Set(
      filteredPairs.flatMap((p) => [p.from_citation, p.to_citation]).slice(0, 12),
    ),
  );
  const authSet = new Set(authorities.map((a) => a.citation_text));

  return (
    <div className="space-y-4">
      {nodeNames.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-border bg-slate-50/70 p-4 dark:bg-slate-950/30">
          <div className="mb-2 flex items-center justify-between text-xs text-muted-foreground">
            <span>Citation relationship map ({filteredPairs.length} edge(s))</span>
            <span>Dashed border = unresolved / unverified target</span>
          </div>
          <svg
            viewBox={`0 0 760 ${Math.max(180, filteredPairs.length * 64 + 32)}`}
            className="w-full min-w-[540px]"
            role="img"
            aria-label="Citation relationship graph"
          >
            <defs>
              <marker
                id="arrow-cite"
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 1 L 10 5 L 0 9 z" fill="#0f766e" />
              </marker>
              <marker
                id="arrow-conflict"
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 1 L 10 5 L 0 9 z" fill="#b45309" />
              </marker>
            </defs>
            {filteredPairs.slice(0, 8).map((pair, idx) => {
              const y = 38 + idx * 62;
              const isConflict =
                pair.relationship_type === "potentially_conflicting";
              const stroke = isConflict ? "#b45309" : "#0f766e";
              const targetResolved = authSet.has(pair.to_citation);
              return (
                <g key={`${pair.from_citation}-${pair.to_citation}-${idx}`}>
                  <rect
                    x={16}
                    y={y - 20}
                    width={220}
                    height={40}
                    rx={6}
                    fill="#ffffff"
                    stroke="#0f172a"
                    strokeWidth={1.2}
                  />
                  <text
                    x={26}
                    y={y + 4}
                    fontSize={11}
                    fill="#0f172a"
                    fontFamily="system-ui, sans-serif"
                  >
                    {pair.from_citation.slice(0, 28)}
                    {pair.from_citation.length > 28 ? "…" : ""}
                  </text>

                  <line
                    x1={236}
                    y1={y}
                    x2={514}
                    y2={y}
                    stroke={stroke}
                    strokeWidth={1.6}
                    strokeDasharray={isConflict ? "5,4" : undefined}
                    markerEnd={
                      isConflict ? "url(#arrow-conflict)" : "url(#arrow-cite)"
                    }
                  />
                  <rect
                    x={318}
                    y={y - 12}
                    width={122}
                    height={22}
                    rx={4}
                    fill={isConflict ? "#fef3c7" : "#ccfbf1"}
                  />
                  <text
                    x={379}
                    y={y + 3}
                    textAnchor="middle"
                    fontSize={10}
                    fontWeight={600}
                    fill={isConflict ? "#92400e" : "#115e59"}
                    fontFamily="system-ui, sans-serif"
                  >
                    {RELATIONSHIP_LABELS[pair.relationship_type]}
                  </text>

                  <rect
                    x={520}
                    y={y - 20}
                    width={224}
                    height={40}
                    rx={6}
                    fill="#ffffff"
                    stroke={targetResolved ? "#0f766e" : "#94a3b8"}
                    strokeDasharray={targetResolved ? undefined : "4,3"}
                    strokeWidth={1.2}
                  />
                  <text
                    x={530}
                    y={y + 4}
                    fontSize={11}
                    fill="#0f172a"
                    fontFamily="system-ui, sans-serif"
                  >
                    {pair.to_citation.slice(0, 28)}
                    {pair.to_citation.length > 28 ? "…" : ""}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      )}

      {/* Structured edge list (citing / cited-by / unresolved) */}
      <div className="grid gap-3 md:grid-cols-2">
        {filteredPairs.map((pair, idx) => (
          <div
            key={`${pair.from_citation}-${pair.to_citation}-card-${idx}`}
            className="rounded-lg border border-border bg-card p-3.5 text-sm"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Badge
                variant={
                  pair.relationship_type === "potentially_conflicting"
                    ? "warning"
                    : "outline"
                }
              >
                {RELATIONSHIP_LABELS[pair.relationship_type]}
              </Badge>
              <span className="text-xs text-muted-foreground">
                Confidence: {pair.confidence}
              </span>
            </div>
            <p className="mt-2 font-medium text-foreground">
              {pair.from_citation}{" "}
              <span className="text-muted-foreground">→</span>{" "}
              {pair.to_citation}
            </p>
            {pair.supporting_passage && (
              <p className="mt-1.5 text-xs text-muted-foreground">
                Supporting passage: “{pair.supporting_passage}”
              </p>
            )}
          </div>
        ))}
      </div>

      {persistedLinks.length > 0 && (
        <div className="rounded-lg border border-border bg-muted/20 p-3">
          <p className="text-xs font-semibold text-foreground">
            Persisted Citation Index ({persistedLinks.length} link(s))
          </p>
          <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
            {persistedLinks.map((link) => (
              <li key={link.id} className="flex flex-wrap items-center gap-2">
                <span className="font-mono">{link.to_citation_text}</span>
                <Badge variant={link.is_resolved ? "success" : "outline"}>
                  {link.is_resolved ? "Resolved in corpus" : "Unresolved"}
                </Badge>
                <span>({link.relationship_type})</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export function PrecedentPanel({ caseId }: { caseId?: string }) {
  const queryClient = useQueryClient();

  // Direct corpus search state
  const [searchQuery, setSearchQuery] = useState("");
  const [jurisdictionFilter, setJurisdictionFilter] = useState("");
  const [courtFilter, setCourtFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [relationshipFilter, setRelationshipFilter] = useState<string>("all");
  const [selectedAuthority, setSelectedAuthority] =
    useState<PrecedentAuthority | null>(null);

  // Case workflow state
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [focus, setFocus] = useState("");
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const retrievalStatusQuery = useQuery({
    queryKey: ["retrieval", "status"],
    queryFn: () => getRetrievalStatus(),
    select: (env) => env.data,
  });

  const searchMutation = useMutation({
    mutationFn: () =>
      searchLegalRetrieval({
        query: searchQuery.trim() || "limitation acknowledgment contract",
        filters: {
          source_type: "legal_authority",
          jurisdiction: jurisdictionFilter.trim() || null,
          court: courtFilter.trim() || null,
          date_from: dateFrom.trim() || null,
          date_to: dateTo.trim() || null,
        },
        limit: 12,
      }),
  });

  const docsQuery = useQuery({
    queryKey: ["documents", caseId],
    queryFn: () => listDocuments(caseId!),
    enabled: Boolean(caseId),
    select: (env) => env.data?.items ?? [],
  });

  const runsQuery = useQuery({
    queryKey: ["analysis", "precedent", caseId],
    queryFn: () => listPrecedentAnalyses(caseId!, 15),
    enabled: Boolean(caseId),
    select: (env) => env.data?.items ?? [],
    refetchInterval: (query) => {
      const items = query.state.data?.data?.items ?? [];
      return items.some((r) => isWorkflowActive(r.status)) ? 1500 : false;
    },
  });

  const runs = useMemo(() => runsQuery.data ?? [], [runsQuery.data]);
  const activeRun: WorkflowRun | undefined = useMemo(() => {
    if (activeRunId) {
      return runs.find((r) => r.id === activeRunId) ?? runs[0];
    }
    return runs[0];
  }, [runs, activeRunId]);

  useEffect(() => {
    if (runs.length > 0 && !activeRunId) {
      setActiveRunId(runs[0].id);
    }
  }, [runs, activeRunId]);

  const citationsQuery = useQuery({
    queryKey: ["analysis", "citations", caseId, activeRun?.id],
    queryFn: () => listCitationsForRun(caseId!, activeRun!.id),
    enabled: Boolean(caseId && activeRun?.id && activeRun.status === "completed"),
    select: (env) => env.data?.items ?? [],
  });

  const startMutation = useMutation({
    mutationFn: () =>
      startPrecedentSearch(caseId!, {
        document_ids: selectedDocIds.length > 0 ? selectedDocIds : undefined,
        focus: focus.trim() || undefined,
      }),
    onSuccess: (env) => {
      if (env.data) setActiveRunId(env.data.id);
      queryClient.invalidateQueries({
        queryKey: ["analysis", "precedent", caseId],
      });
    },
  });

  const retryMutation = useMutation({
    mutationFn: (workflowId: string) => retryCaseAnalysis(caseId!, workflowId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["analysis", "precedent", caseId],
      });
    },
  });

  const precedentResult = useMemo<PrecedentResult | null>(() => {
    if (!activeRun || activeRun.status !== "completed" || !activeRun.result) {
      return null;
    }
    const res = activeRun.result as unknown as PrecedentResult;
    return res;
  }, [activeRun]);

  const filteredAuthorities = useMemo(() => {
    const auths = precedentResult?.authorities ?? [];
    return auths.filter((a) => {
      if (
        jurisdictionFilter.trim() &&
        !a.jurisdiction
          .toLowerCase()
          .includes(jurisdictionFilter.trim().toLowerCase())
      ) {
        return false;
      }
      if (
        courtFilter.trim() &&
        !a.court.toLowerCase().includes(courtFilter.trim().toLowerCase())
      ) {
        return false;
      }
      return true;
    });
  }, [precedentResult, jurisdictionFilter, courtFilter]);

  async function handleDownload(format: "html" | "markdown") {
    if (!caseId || !activeRun) return;
    setExportError(null);
    try {
      const { blob, filename } = await downloadCaseReport(
        caseId,
        activeRun.id,
        format,
      );
      saveBlob(blob, filename);
    } catch (err) {
      setExportError(
        err instanceof Error ? err.message : "Could not download report.",
      );
    }
  }

  const corpusConfigured = retrievalStatusQuery.data?.corpus_configured ?? false;
  const searchItems: RetrievalResultItem[] =
    searchMutation.data?.data?.items ?? [];

  return (
    <div className="space-y-6">
      {/* Corpus & Reliability Banner */}
      <div
        className={`rounded-lg border p-4 text-sm ${
          corpusConfigured
            ? "border-teal-200 bg-teal-50/70 text-teal-950"
            : "border-amber-200 bg-amber-50/80 text-amber-950"
        }`}
      >
        <div className="flex flex-wrap items-start gap-3">
          <Scale className="mt-0.5 h-4 w-4 shrink-0" />
          <div className="space-y-1">
            <p className="font-semibold">
              {corpusConfigured
                ? `Legal corpus connected (${retrievalStatusQuery.data?.corpus_provider})`
                : "No external legal corpus configured — development fixture mode"}
            </p>
            <p className="text-xs opacity-90">
              NyayaSaar never fabricates citations, holdings, or subsequent
              judicial treatment. Unresolved citations are stored as unresolved,
              and model-generated conflict notes require independent legal
              review.
            </p>
          </div>
        </div>
      </div>

      {/* Direct Legal Corpus Search & Filter Bar */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Search className="h-4 w-4 text-teal-700" />
            Search Legal Records
          </CardTitle>
          <CardDescription>
            Query ingested statutes, judgments, or development fixtures with
            jurisdiction, court, and date filters.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <form
            className="grid gap-3 md:grid-cols-7"
            onSubmit={(e) => {
              e.preventDefault();
              searchMutation.mutate();
            }}
          >
            <Input
              className="md:col-span-2"
              placeholder="Search legal issue, citation, or doctrine..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              aria-label="Search legal records"
            />
            <Input
              placeholder="Jurisdiction (e.g. India)"
              value={jurisdictionFilter}
              onChange={(e) => setJurisdictionFilter(e.target.value)}
              aria-label="Filter by jurisdiction"
            />
            <Input
              placeholder="Court"
              value={courtFilter}
              onChange={(e) => setCourtFilter(e.target.value)}
              aria-label="Filter by court"
            />
            <Input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              aria-label="Date from"
            />
            <Input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              aria-label="Date to"
            />
            <Button
              type="submit"
              variant="teal"
              disabled={searchMutation.isPending}
            >
              {searchMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Search className="h-4 w-4" />
              )}
              Search
            </Button>
          </form>

          {searchMutation.isError && (
            <p className="text-xs text-destructive">
              Could not search legal records. Please try again.
            </p>
          )}

          {searchMutation.isSuccess && searchItems.length === 0 && (
            <div className="rounded-md border border-dashed p-4 text-center text-xs text-muted-foreground">
              No matching legal records found for this query and filter set.
            </div>
          )}

          {searchItems.length > 0 && (
            <div className="grid gap-3 md:grid-cols-2">
              {searchItems.map((item) => (
                <div
                  key={item.result_id}
                  className={`rounded-lg border p-3.5 text-sm ${
                    item.is_fixture
                      ? "border-amber-200 bg-amber-50/40"
                      : "border-border bg-card"
                  }`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-semibold text-foreground">
                      {item.citation || item.title}
                    </span>
                    <div className="flex items-center gap-1.5">
                      {item.is_fixture && (
                        <Badge variant="warning">FIXTURE — NOT REAL LAW</Badge>
                      )}
                      <Badge variant="outline">{item.source_provider}</Badge>
                    </div>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {item.court || "[Court unavailable]"} ·{" "}
                    {item.jurisdiction || "[Jurisdiction unavailable]"} ·{" "}
                    {item.decision_date || "[Date unavailable]"}
                  </p>
                  <p className="mt-2 line-clamp-3 text-xs text-foreground/90">
                    {item.text}
                  </p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Case-Linked Precedent Explorer & Conflict Detector */}
      {caseId && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <BookOpen className="h-4 w-4 text-teal-700" />
              Case-Linked Precedent &amp; Conflict Analysis
            </CardTitle>
            <CardDescription>
              Extract citations from case documents, match against retrieved
              legal records, map citation relationships, and inspect potential
              conflicts.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 md:grid-cols-3">
              <div className="md:col-span-2">
                <label
                  htmlFor="precedent-focus"
                  className="mb-1 block text-xs font-medium"
                >
                  Research focus (optional)
                </label>
                <Input
                  id="precedent-focus"
                  placeholder="e.g., limitation period, written acknowledgment, breach remedies..."
                  value={focus}
                  onChange={(e) => setFocus(e.target.value)}
                />
              </div>
              <div className="flex items-end">
                <Button
                  variant="teal"
                  className="w-full"
                  disabled={
                    startMutation.isPending ||
                    (activeRun ? isWorkflowActive(activeRun.status) : false)
                  }
                  onClick={() => startMutation.mutate()}
                >
                  {startMutation.isPending ||
                  (activeRun && isWorkflowActive(activeRun.status)) ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Play className="h-4 w-4" />
                  )}
                  Run Precedent Explorer
                </Button>
              </div>
            </div>

            {(docsQuery.data ?? []).length > 0 && (
              <div className="space-y-1.5">
                <span className="text-xs font-medium text-muted-foreground">
                  Limit to specific case documents (optional — default uses all
                  ready documents):
                </span>
                <div className="flex flex-wrap gap-2">
                  {(docsQuery.data ?? []).map((doc: Document) => {
                    const checked = selectedDocIds.includes(doc.id);
                    return (
                      <button
                        key={doc.id}
                        type="button"
                        onClick={() =>
                          setSelectedDocIds((prev) =>
                            checked
                              ? prev.filter((id) => id !== doc.id)
                              : [...prev, doc.id],
                          )
                        }
                        className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs transition-colors ${
                          checked
                            ? "border-teal-600 bg-teal-50 text-teal-900"
                            : "border-border bg-background text-muted-foreground hover:text-foreground"
                        }`}
                      >
                        <FileText className="h-3 w-3" />
                        {doc.original_name}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {startMutation.isError && (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
                Could not start Precedent Explorer:{" "}
                {startMutation.error instanceof Error
                  ? startMutation.error.message
                  : "Unknown error"}
              </div>
            )}

            {/* Run selector & progress */}
            {runs.length > 0 && activeRun && (
              <div className="space-y-3 rounded-lg border border-border bg-muted/20 p-3.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-semibold">Run:</span>
                    <select
                      aria-label="Select precedent run"
                      value={activeRun.id}
                      onChange={(e) => setActiveRunId(e.target.value)}
                      className="h-8 rounded-md border border-input bg-background px-2 text-xs"
                    >
                      {runs.map((r) => (
                        <option key={r.id} value={r.id}>
                          {new Date(r.created_at).toLocaleString()} —{" "}
                          {workflowStatusLabel(r.status)}
                          {r.is_mock ? " (Fixture)" : ""}
                        </option>
                      ))}
                    </select>
                    <Badge
                      variant={
                        activeRun.status === "completed"
                          ? "success"
                          : activeRun.status === "failed"
                            ? "destructive"
                            : "warning"
                      }
                    >
                      {workflowStatusLabel(activeRun.status)}
                    </Badge>
                  </div>

                  {activeRun.status === "completed" && (
                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleDownload("html")}
                      >
                        <Download className="h-3.5 w-3.5" />
                        HTML Report
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleDownload("markdown")}
                      >
                        <Download className="h-3.5 w-3.5" />
                        Markdown
                      </Button>
                    </div>
                  )}
                </div>

                {isWorkflowActive(activeRun.status) && (
                  <div className="space-y-1">
                    <Progress value={activeRun.progress} />
                    <p className="text-xs text-muted-foreground">
                      Step: {activeRun.current_step ?? "queued"} (
                      {activeRun.progress}%)
                    </p>
                  </div>
                )}

                {activeRun.status === "failed" && (
                  <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
                    <span>
                      {activeRun.error?.message || "Precedent run failed."}
                    </span>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={retryMutation.isPending}
                      onClick={() => retryMutation.mutate(activeRun.id)}
                    >
                      <RefreshCw className="h-3.5 w-3.5" />
                      Retry
                    </Button>
                  </div>
                )}

                {exportError && (
                  <p className="text-xs text-destructive">{exportError}</p>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Results Display */}
      {precedentResult && (
        <div className="space-y-6">
          {/* Summary */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Research Summary</CardTitle>
              <CardDescription>
                {precedentResult.corpus_configured
                  ? "Authorities grounded in configured legal corpus."
                  : "Development fixture / case-document mode — no external legal database connected."}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <p className="leading-relaxed text-foreground">
                {precedentResult.summary}
              </p>
              {precedentResult.insufficient_sources && (
                <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                  No usable extracted document text was found. Upload and
                  process documents first.
                </div>
              )}
            </CardContent>
          </Card>

          {/* Authorities */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                Identified Authorities ({filteredAuthorities.length})
              </CardTitle>
              <CardDescription>
                Click any authority card to inspect full provenance and
                verification status. Subsequent judicial treatment is shown only
                when supplied by a reliable source.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {filteredAuthorities.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No authorities matched the current filters.
                </p>
              ) : (
                <div className="grid gap-3 md:grid-cols-2">
                  {filteredAuthorities.map((auth) => (
                    <button
                      key={auth.authority_id}
                      type="button"
                      onClick={() => setSelectedAuthority(auth)}
                      className={`w-full rounded-lg border p-4 text-left transition-colors hover:border-teal-600 ${
                        auth.is_fixture
                          ? "border-amber-200 bg-amber-50/40"
                          : "border-border bg-card"
                      }`}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-semibold text-sm text-foreground">
                          {auth.citation_text}
                        </span>
                        <div className="flex flex-wrap gap-1.5">
                          {auth.is_fixture && (
                            <Badge variant="warning">FIXTURE</Badge>
                          )}
                          {supportBadge(auth.support)}
                        </div>
                      </div>
                      <p className="mt-1 text-xs font-medium text-foreground/90">
                        {auth.title}
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {auth.court} · {auth.jurisdiction} ·{" "}
                        {auth.decision_date}
                      </p>
                      <p className="mt-2 line-clamp-2 text-xs text-muted-foreground">
                        {auth.holding_summary}
                      </p>
                      <div className="mt-2 flex items-center justify-between text-[11px] text-muted-foreground">
                        <span>Provider: {auth.source_provider}</span>
                        <span>Subsequent treatment: Unavailable</span>
                      </div>
                    </button>
                  ))}
                </div>
              )}

              {selectedAuthority && (
                <div className="rounded-lg border border-teal-200 bg-teal-50/30 p-4 text-sm">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h4 className="font-semibold">
                        {selectedAuthority.citation_text} —{" "}
                        {selectedAuthority.title}
                      </h4>
                      <p className="text-xs text-muted-foreground">
                        Source ID: {selectedAuthority.source_id} · Provider:{" "}
                        {selectedAuthority.source_provider}
                      </p>
                    </div>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setSelectedAuthority(null)}
                    >
                      Close
                    </Button>
                  </div>
                  <p className="mt-2 text-xs leading-relaxed">
                    <strong>Holding summary:</strong>{" "}
                    {selectedAuthority.holding_summary}
                  </p>
                  {selectedAuthority.relevance_note && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      <strong>Relevance note (model):</strong>{" "}
                      {selectedAuthority.relevance_note}
                    </p>
                  )}
                  <p className="mt-2 text-xs text-amber-800">
                    Subsequent judicial treatment metadata is not available
                    from the configured corpus. Do not treat this authority as
                    binding without independent verification.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Citation Graph & Relationships */}
          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <GitFork className="h-4 w-4 text-teal-700" />
                    Citation Relationships &amp; Graph
                  </CardTitle>
                  <CardDescription>
                    Explore citing, cited-by, related-issue, and potentially
                    conflicting links.
                  </CardDescription>
                </div>
                <select
                  aria-label="Filter relationship type"
                  value={relationshipFilter}
                  onChange={(e) => setRelationshipFilter(e.target.value)}
                  className="h-8 rounded-md border border-input bg-background px-2 text-xs"
                >
                  <option value="all">All relationships</option>
                  <option value="cites">Cites</option>
                  <option value="cited_by">Cited by</option>
                  <option value="related_issue">Related issue</option>
                  <option value="potentially_conflicting">
                    Potentially conflicting
                  </option>
                </select>
              </div>
            </CardHeader>
            <CardContent>
              <CitationGraphView
                authorities={precedentResult.authorities ?? []}
                pairs={precedentResult.citation_pairs ?? []}
                persistedLinks={citationsQuery.data ?? []}
                relationshipFilter={relationshipFilter}
              />
            </CardContent>
          </Card>

          {/* Potential Conflicts */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <AlertTriangle className="h-4 w-4 text-amber-600" />
                Potential Reasoning Conflicts (
                {(precedentResult.potential_conflicts ?? []).length})
              </CardTitle>
              <CardDescription>
                Side-by-side comparison of potentially conflicting passages.
                Model-generated notes are analytical hypotheses, never binding
                determinations.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {(precedentResult.potential_conflicts ?? []).length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No potential reasoning conflicts were identified in the
                  available passages.
                </p>
              ) : (
                (precedentResult.potential_conflicts ?? []).map(
                  (conflict: PrecedentConflict, idx: number) => (
                    <div
                      key={`${conflict.title}-${idx}`}
                      className="rounded-lg border border-border p-4 space-y-3"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <h4 className="font-semibold text-sm">
                          {conflict.title}
                        </h4>
                        {supportBadge(conflict.support)}
                      </div>
                      <div className="grid gap-3 md:grid-cols-2">
                        <div className="rounded-md border border-border bg-muted/20 p-3 text-xs">
                          <p className="font-semibold text-foreground">
                            Interpretation A
                          </p>
                          <p className="mt-1 text-foreground/90">
                            {conflict.interpretation_a}
                          </p>
                          {conflict.source_a_verified && (
                            <p className="mt-2 text-[11px] text-muted-foreground">
                              Source: {conflict.source_a_verified.document_name}
                              {conflict.source_a_verified.page_number
                                ? ` (p.${conflict.source_a_verified.page_number})`
                                : ""}
                            </p>
                          )}
                        </div>
                        <div className="rounded-md border border-border bg-muted/20 p-3 text-xs">
                          <p className="font-semibold text-foreground">
                            Interpretation B
                          </p>
                          <p className="mt-1 text-foreground/90">
                            {conflict.interpretation_b}
                          </p>
                          {conflict.source_b_verified && (
                            <p className="mt-2 text-[11px] text-muted-foreground">
                              Source: {conflict.source_b_verified.document_name}
                              {conflict.source_b_verified.page_number
                                ? ` (p.${conflict.source_b_verified.page_number})`
                                : ""}
                            </p>
                          )}
                        </div>
                      </div>
                      <div className="flex items-start gap-2 rounded-md bg-amber-50/70 p-2.5 text-xs text-amber-950">
                        <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                        <span>
                          <strong>Model analytical note:</strong>{" "}
                          {conflict.model_note}
                        </span>
                      </div>
                    </div>
                  ),
                )
              )}
            </CardContent>
          </Card>

          {/* Limitations */}
          {(precedentResult.limitations ?? []).length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">
                  Limitations &amp; Verification Notice
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="list-disc space-y-1 pl-5 text-xs text-muted-foreground">
                  {precedentResult.limitations.map((lim, i) => (
                    <li key={i}>{lim}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
