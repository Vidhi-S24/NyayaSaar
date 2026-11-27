import { PrecedentsClient } from "./precedents-client";

export const metadata = { title: "Precedent Explorer" };

export default async function PrecedentsPage({
  searchParams,
}: {
  searchParams: Promise<{ caseId?: string }>;
}) {
  const params = await searchParams;
  return <PrecedentsClient initialCaseId={params.caseId} />;
}
