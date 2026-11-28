import { AdvocateClient } from "./advocate-client";

export const metadata = { title: "Advocate Mode" };

export default async function AdvocatePage({
  searchParams,
}: {
  searchParams: Promise<{ caseId?: string }>;
}) {
  const params = await searchParams;
  return <AdvocateClient initialCaseId={params.caseId} />;
}
