"use client";

/**
 * Legal Research — Stage 7 Hybrid Legal Retrieval Workspace.
 *
 * Combines lexical search (BM25 / PostgreSQL FTS) and semantic embeddings
 * (hashing / pgvector) with Reciprocal Rank Fusion (RRF) and metadata filters.
 * When no external legal corpus is configured, clearly labels fixture records.
 */

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  Database,
  ExternalLink,
  FileText,
  Filter,
  Loader2,
  RefreshCw,
  Search,
  ShieldAlert,
} from "lucide-react";
import type {
  RetrievalResultItem,
  RetrievalSearchResponse,
  RetrievalSourceType,
} from "@nyayasaar/shared";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiClientError } from "@/lib/api-client";
import { listCases } from "@/lib/api/cases";
import {
  getRetrievalStatus,
  indexCaseForRetrieval,
  searchLegalRetrieval,
} from "@/lib/api/retrieval";

function InspectSourceDialog({
  item,
  onClose,
}: {
  item: RetrievalResultItem | null;
  onClose: () => void;
}) {
  return (
    <Dialog open={item !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="pr-8">
            {item?.title}
            {item?.is_fixture && (
              <Badge variant="warning" className="ml-2 align-middle">
                Sample Fixture
              </Badge>
            )}
          </DialogTitle>
          <DialogDescription>
            Retrieved text is untrusted source material for human review. Scores
            measure similarity only and do not indicate legal authority or
            binding status.
          </DialogDescription>
        </DialogHeader>

        {item && (
          <div className="flex flex-col gap-3 text-xs">
            <div className="flex flex-wrap gap-1.5">
              <Badge variant="secondary">
                {item.source_type === "case_document"
                  ? "Case Document"
                  : "Legal Authority"}
              </Badge>
              <Badge variant="outline">Provider: {item.source_provider}</Badge>
              {item.citation && (
                <Badge variant="outline">Citation: {item.citation}</Badge>
              )}
              {item.jurisdiction && (
                <Badge variant="outline">
                  Jurisdiction: {item.jurisdiction}
                </Badge>
              )}
              {item.court && (
                <Badge variant="outline">Court: {item.court}</Badge>
              )}
              {item.decision_date && (
                <Badge variant="outline">Date: {item.decision_date}</Badge>
              )}
              {item.page_number !== null && (
                <Badge variant="outline">Page {item.page_number}</Badge>
              )}
              {item.paragraph_number !== null && (
                <Badge variant="outline">Para {item.paragraph_number}</Badge>
              )}
            </div>

            {item.has_injection_signals && (
              <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-amber-900">
                <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
                <span>
                  This excerpt contains instruction-like phrasing. It is
                  displayed strictly as untrusted source text.
                </span>
              </div>
            )}

            <div className="max-h-80 overflow-y-auto whitespace-pre-wrap rounded-md border border-border bg-secondary/40 p-3 font-mono text-xs leading-relaxed text-foreground">
              {item.text}
            </div>

            <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-muted-foreground">
              <span>
                Source ID: <code>{item.source_id}</code> · Hybrid RRF:{" "}
                {item.hybrid_score.toFixed(4)} · Lexical:{" "}
                {item.lexical_score.toFixed(3)} · Semantic:{" "}
                {item.semantic_score.toFixed(3)}
              </span>
              {item.source_url && (
                <a
                  href={item.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 font-medium text-teal-700 underline hover:text-teal-900"
                >
                  Open source URL
                  <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export function ResearchClient() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [caseId, setCaseId] = useState("");
  const [sourceType, setSourceType] = useState<RetrievalSourceType>("all");
  const [jurisdiction, setJurisdiction] = useState("");
  const [court, setCourt] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [limit, setLimit] = useState(10);
  const [showFilters, setShowFilters] = useState(false);

  const [selectedIds, setSelectedIds] = useState<Record<string, boolean>>({});
  const [inspectItem, setInspectItem] = useState<RetrievalResultItem | null>(
    null,
  );
  const [searchResult, setSearchResult] =
    useState<RetrievalSearchResponse | null>(null);
  const [indexMessage, setIndexMessage] = useState<string | null>(null);

  const statusQuery = useQuery({
    queryKey: ["retrieval-status"],
    queryFn: getRetrievalStatus,
    select: (env) => env.data,
    staleTime: 60_000,
  });

  const casesQuery = useQuery({
    queryKey: ["cases", "research"],
    queryFn: () => listCases({ page_size: 100 }),
    select: (env) => env.data,
  });

  const cases = useMemo(
    () => casesQuery.data?.items ?? [],
    [casesQuery.data],
  );

  const searchMutation = useMutation({
    mutationFn: () =>
      searchLegalRetrieval({
        query: query.trim(),
        limit,
        filters: {
          case_id: caseId || null,
          source_type: sourceType,
          jurisdiction: jurisdiction.trim() || null,
          court: court.trim() || null,
          date_from: dateFrom || null,
          date_to: dateTo || null,
        },
      }),
    onSuccess: (env) => {
      if (env.data) {
        setSearchResult(env.data);
      }
      setSelectedIds({});
    },
  });

  const indexMutation = useMutation({
    mutationFn: (targetCaseId: string) => indexCaseForRetrieval(targetCaseId),
    onSuccess: (env) => {
      const d = env.data;
      if (!d) return;
      setIndexMessage(
        `Indexed ${d.indexed_chunks} of ${d.total_chunks} chunk(s) using ${d.embedding_provider} (${d.dimensions}d).`,
      );
    },
  });

  const selectedItems = useMemo(() => {
    if (!searchResult) return [];
    return searchResult.items.filter((it) => selectedIds[it.result_id]);
  }, [searchResult, selectedIds]);

  const selectedCaseDocIds = useMemo(() => {
    const ids = new Set<string>();
    for (const it of selectedItems) {
      if (it.source_type === "case_document" && it.document_id) {
        ids.add(it.document_id);
      }
    }
    return Array.from(ids);
  }, [selectedItems]);

  function handleSendToAnalysis() {
    const targetCaseId =
      caseId ||
      selectedItems.find((it) => it.case_id)?.case_id ||
      cases[0]?.id ||
      "";
    const params = new URLSearchParams();
    if (targetCaseId) params.set("caseId", targetCaseId);
    if (selectedCaseDocIds.length > 0) {
      params.set("docIds", selectedCaseDocIds.join(","));
    }
    const focusParts = [
      query.trim() ? `Research query: ${query.trim()}` : "",
      ...selectedItems
        .filter((it) => it.citation)
        .map((it) => `${it.title} (${it.citation})`),
    ].filter(Boolean);
    if (focusParts.length > 0) {
      params.set("focus", focusParts.join(" | ").slice(0, 900));
    }
    router.push(`/intelligence?${params.toString()}`);
  }

  const retrievalStatus = statusQuery.data;

  return (
    <div className="flex flex-col gap-6 p-6 pb-10">
      <PageHeader
        title="Legal Research"
        description="Hybrid lexical and semantic retrieval across your case documents and configured legal-source providers, with full source provenance."
      />

      {/* Provider & fixture honesty banner */}
      {statusQuery.isLoading ? (
        <Skeleton className="h-12 w-full" />
      ) : retrievalStatus ? (
        <div
          className={
            retrievalStatus.fixture_active
              ? "rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-900"
              : "rounded-md border border-teal-200 bg-teal-50 px-4 py-3 text-xs text-teal-900"
          }
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              {retrievalStatus.fixture_active ? (
                <>
                  <strong>No external legal corpus configured.</strong>{" "}
                  External authority results come from clearly labelled{" "}
                  <code>development_fixture</code> records — never real case
                  law. Case document search still queries your uploaded case
                  chunks.
                </>
              ) : (
                <>
                  <strong>
                    Legal corpus provider:{" "}
                    {retrievalStatus.corpus_provider}
                  </strong>{" "}
                  · Hybrid retrieval active.
                </>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-1.5">
              <Badge variant="outline">
                Vector: {retrievalStatus.vector_backend}
              </Badge>
              <Badge variant="outline">
                Embeddings: {retrievalStatus.embedding_provider} (
                {retrievalStatus.embedding_dimensions}d)
              </Badge>
            </div>
          </div>
        </div>
      ) : null}

      {/* Search & Filters */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">Search query &amp; filters</CardTitle>
          <CardDescription className="text-xs">
            Enter a legal issue, clause, or factual question. Retrieved text is
            treated as untrusted source content.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (query.trim()) searchMutation.mutate();
            }}
            className="flex flex-col gap-3 sm:flex-row"
          >
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g. limitation period acknowledgment of debt or termination notice"
                className="pl-9"
                maxLength={retrievalStatus?.max_query_chars ?? 500}
                aria-label="Legal research query"
              />
            </div>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowFilters((v) => !v)}
              >
                <Filter className="h-3.5 w-3.5" />
                Filters
              </Button>
              <Button
                type="submit"
                variant="teal"
                disabled={!query.trim() || searchMutation.isPending}
              >
                {searchMutation.isPending ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Searching
                  </>
                ) : (
                  <>
                    <Search className="h-3.5 w-3.5" />
                    Search
                  </>
                )}
              </Button>
            </div>
          </form>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <div className="flex min-w-0 flex-col gap-1">
              <label
                htmlFor="research-case"
                className="text-xs font-medium text-foreground"
              >
                Case scope (optional)
              </label>
              <div className="flex min-w-0 gap-1.5">
                <select
                  id="research-case"
                  value={caseId}
                  onChange={(e) => {
                    setCaseId(e.target.value);
                    setIndexMessage(null);
                  }}
                  className="h-9 min-w-0 w-full flex-1 truncate rounded-md border border-input bg-background px-2.5 text-xs text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <option value="">All configured legal sources only</option>
                  {cases.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.title}
                      {c.case_number ? ` · ${c.case_number}` : ""}
                    </option>
                  ))}
                </select>
                {caseId && (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    title="Re-index case document embeddings"
                    disabled={indexMutation.isPending}
                    onClick={() => indexMutation.mutate(caseId)}
                  >
                    {indexMutation.isPending ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <RefreshCw className="h-3.5 w-3.5" />
                    )}
                  </Button>
                )}
              </div>
              {indexMessage && (
                <p className="text-[11px] text-teal-700">{indexMessage}</p>
              )}
            </div>

            <div className="flex flex-col gap-1">
              <label
                htmlFor="research-source-type"
                className="text-xs font-medium text-foreground"
              >
                Source type
              </label>
              <select
                id="research-source-type"
                value={sourceType}
                onChange={(e) =>
                  setSourceType(e.target.value as RetrievalSourceType)
                }
                className="h-9 rounded-md border border-input bg-background px-2.5 text-xs text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <option value="all">All sources (Case + Authorities)</option>
                <option value="case_document">Case documents only</option>
                <option value="legal_authority">Legal authorities only</option>
              </select>
            </div>

            <div className="flex flex-col gap-1">
              <label
                htmlFor="research-limit"
                className="text-xs font-medium text-foreground"
              >
                Result limit
              </label>
              <select
                id="research-limit"
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
                className="h-9 rounded-md border border-input bg-background px-2.5 text-xs text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <option value={5}>Top 5</option>
                <option value={10}>Top 10</option>
                <option value={20}>Top 20</option>
                <option value={30}>Top 30</option>
              </select>
            </div>
          </div>

          {showFilters && (
            <div className="grid gap-3 border-t border-border pt-3 sm:grid-cols-2 lg:grid-cols-4">
              <div className="flex flex-col gap-1">
                <label
                  htmlFor="filter-jurisdiction"
                  className="text-xs font-medium text-foreground"
                >
                  Jurisdiction
                </label>
                <Input
                  id="filter-jurisdiction"
                  value={jurisdiction}
                  onChange={(e) => setJurisdiction(e.target.value)}
                  placeholder="e.g. India, Karnataka"
                  className="h-8 text-xs"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label
                  htmlFor="filter-court"
                  className="text-xs font-medium text-foreground"
                >
                  Court
                </label>
                <Input
                  id="filter-court"
                  value={court}
                  onChange={(e) => setCourt(e.target.value)}
                  placeholder="e.g. High Court, Civil Court"
                  className="h-8 text-xs"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label
                  htmlFor="filter-date-from"
                  className="text-xs font-medium text-foreground"
                >
                  Date from
                </label>
                <Input
                  id="filter-date-from"
                  type="date"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                  className="h-8 text-xs"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label
                  htmlFor="filter-date-to"
                  className="text-xs font-medium text-foreground"
                >
                  Date to
                </label>
                <Input
                  id="filter-date-to"
                  type="date"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                  className="h-8 text-xs"
                />
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Error state */}
      {searchMutation.isError && (
        <div
          className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
          role="alert"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div className="flex-1">
            <p className="font-medium">Search failed</p>
            <p className="mt-0.5 text-xs">
              {searchMutation.error instanceof ApiClientError
                ? searchMutation.error.message
                : "Check that the API server is running and try again."}
            </p>
          </div>
        </div>
      )}

      {/* Loading state */}
      {searchMutation.isPending && (
        <div className="flex flex-col gap-3">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      )}

      {/* Results */}
      {!searchMutation.isPending && searchResult && (
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-card px-4 py-3">
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <span className="font-medium text-foreground">
                {searchResult.items.length} result
                {searchResult.items.length === 1 ? "" : "s"}
              </span>
              <span>· Method: {searchResult.retrieval_method}</span>
              <span>· Candidates: {searchResult.total_candidates}</span>
              {searchResult.deduplicated_count > 0 && (
                <span>
                  · Deduplicated: {searchResult.deduplicated_count}
                </span>
              )}
            </div>

            {selectedItems.length > 0 && (
              <Button
                type="button"
                size="sm"
                variant="teal"
                onClick={handleSendToAnalysis}
              >
                Send {selectedItems.length} selected to Case Intelligence
                <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            )}
          </div>

          <p className="text-[11px] text-muted-foreground">
            {searchResult.score_disclaimer}
          </p>

          {searchResult.items.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center gap-2 py-12 text-center">
                <Database className="h-7 w-7 text-muted-foreground/40" />
                <p className="text-sm font-medium text-foreground">
                  No matching sources found
                </p>
                <p className="max-w-md text-xs text-muted-foreground">
                  Try broadening your query, clearing metadata filters, or
                  selecting a case with uploaded documents.
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="flex flex-col gap-3">
              {searchResult.items.map((item) => {
                const checked = Boolean(selectedIds[item.result_id]);
                return (
                  <Card
                    key={item.result_id}
                    className={
                      item.is_fixture ? "border-amber-200/80" : undefined
                    }
                  >
                    <CardContent className="flex flex-col gap-3 pt-5">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-start gap-2.5">
                          <input
                            type="checkbox"
                            id={`select-${item.result_id}`}
                            checked={checked}
                            onChange={() =>
                              setSelectedIds((prev) => ({
                                ...prev,
                                [item.result_id]: !prev[item.result_id],
                              }))
                            }
                            className="mt-1 h-4 w-4 rounded border-input accent-teal-600"
                            aria-label={`Select ${item.title}`}
                          />
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              {item.source_type === "case_document" ? (
                                <FileText className="h-4 w-4 text-teal-600" />
                              ) : (
                                <BookOpen className="h-4 w-4 text-ink-700" />
                              )}
                              <h3 className="text-sm font-semibold text-foreground">
                                {item.title}
                              </h3>
                              {item.is_fixture && (
                                <Badge variant="warning">Sample Fixture</Badge>
                              )}
                              {item.has_injection_signals && (
                                <Badge variant="destructive">
                                  Untrusted / instruction-like text
                                </Badge>
                              )}
                            </div>
                            <div className="mt-1 flex flex-wrap gap-1.5 text-[11px] text-muted-foreground">
                              {item.citation && <span>{item.citation}</span>}
                              {item.jurisdiction && (
                                <span>· {item.jurisdiction}</span>
                              )}
                              {item.court && <span>· {item.court}</span>}
                              {item.decision_date && (
                                <span>· {item.decision_date}</span>
                              )}
                              {item.page_number !== null && (
                                <span>· Page {item.page_number}</span>
                              )}
                              {item.paragraph_number !== null && (
                                <span>· Para {item.paragraph_number}</span>
                              )}
                              <span>· Provider: {item.source_provider}</span>
                            </div>
                          </div>
                        </div>

                        <div className="flex shrink-0 items-center gap-2">
                          <Badge variant="secondary" className="font-mono text-[10px]">
                            RRF {item.hybrid_score.toFixed(4)}
                          </Badge>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => setInspectItem(item)}
                          >
                            Inspect
                          </Button>
                        </div>
                      </div>

                      <p className="line-clamp-3 rounded-md bg-secondary/40 px-3 py-2 text-xs leading-relaxed text-foreground/90">
                        {item.text}
                      </p>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Initial empty state */}
      {!searchMutation.isPending && !searchResult && !searchMutation.isError && (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-12 text-center">
            <Search className="h-7 w-7 text-muted-foreground/40" />
            <p className="text-sm font-medium text-foreground">
              Search case documents and legal sources
            </p>
            <p className="max-w-md text-xs text-muted-foreground">
              Enter a query above to run hybrid lexical + semantic retrieval.
              Select a case to search within its uploaded documents, or search
              configured legal-source providers directly.
            </p>
          </CardContent>
        </Card>
      )}

      <InspectSourceDialog
        item={inspectItem}
        onClose={() => setInspectItem(null)}
      />
    </div>
  );
}
