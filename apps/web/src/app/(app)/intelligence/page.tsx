import { IntelligenceClient } from "./intelligence-client";

export const metadata = { title: "Case Intelligence" };

export default async function IntelligencePage({
  searchParams,
}: {
  searchParams: Promise<{ caseId?: string }>;
}) {
  const params = await searchParams;
  return <IntelligenceClient initialCaseId={params.caseId} />;
}
