import { ContradictionsClient } from "./contradictions-client";

export const metadata = { title: "Contradiction & Gap Hunter" };

export default async function ContradictionsPage({
  searchParams,
}: {
  searchParams: Promise<{ caseId?: string }>;
}) {
  const params = await searchParams;
  return <ContradictionsClient initialCaseId={params.caseId} />;
}
