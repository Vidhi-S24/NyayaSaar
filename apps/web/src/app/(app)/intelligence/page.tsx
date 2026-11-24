import { IntelligenceClient } from "./intelligence-client";

export const metadata = { title: "Case Intelligence" };

export default async function IntelligencePage({
  searchParams,
}: {
  searchParams: Promise<{ caseId?: string; docIds?: string; focus?: string }>;
}) {
  const params = await searchParams;
  const initialDocIds = params.docIds
    ? params.docIds
        .split(",")
        .map((id) => id.trim())
        .filter(Boolean)
    : undefined;
  return (
    <IntelligenceClient
      initialCaseId={params.caseId}
      initialDocIds={initialDocIds}
      initialFocus={params.focus}
    />
  );
}
