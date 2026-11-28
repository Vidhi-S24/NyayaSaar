import { JudgeClient } from "./judge-client";

export const metadata = { title: "Judge / Clerk Mode" };

export default async function JudgePage({
  searchParams,
}: {
  searchParams: Promise<{ caseId?: string }>;
}) {
  const params = await searchParams;
  return <JudgeClient initialCaseId={params.caseId} />;
}
