"use client";

import { User, Key, Bell, Shield, CheckCircle2, AlertTriangle, Loader2 } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/shared/page-header";
import { DemoNotice } from "@/components/shared/demo-notice";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { useAuth } from "@/lib/auth/auth-context";
import { getAIStatus } from "@/lib/api/analysis";
import { ApiClientError } from "@/lib/api-client";

export default function SettingsPage() {
  const { user, signOut } = useAuth();

  const aiQuery = useQuery({
    queryKey: ["ai-status"],
    queryFn: getAIStatus,
    select: (envelope) => envelope.data,
    staleTime: 60_000,
  });
  const ai = aiQuery.data;

  return (
    <div className="flex flex-col gap-6 p-6 pb-10">
      <DemoNotice message="Profile editing is not yet persisted. Authentication, cases, documents, Case Intelligence, Legal Research, Contradiction & Gap Hunter, and Precedent Explorer are live." />

      <PageHeader
        title="Settings"
        description="Workspace, account, and integration configuration"
      />

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Sidebar */}
        <nav aria-label="Settings sections" className="hidden lg:block">
          <ul className="flex flex-col gap-1">
            {[
              { icon: User, label: "Profile" },
              { icon: Key, label: "API & Integrations", note: "Live" },
              { icon: Bell, label: "Notifications", note: "Future stage" },
              { icon: Shield, label: "Security & Privacy", note: "Future stage" },
            ].map(({ icon: Icon, label, note }) => (
              <li key={label}>
                <button
                  className="flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-sm text-left text-foreground/70 transition-colors hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  aria-current={label === "Profile" ? "page" : undefined}
                >
                  <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                  {label}
                  {note && (
                    <span className="ml-auto text-[10px] text-muted-foreground">{note}</span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </nav>

        {/* Content */}
        <div className="lg:col-span-2 flex flex-col gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Profile</CardTitle>
              <CardDescription className="text-xs">
                Your signed-in account. Name changes will be persisted in a later stage.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-foreground" htmlFor="name">
                  Display Name
                </label>
                <Input id="name" defaultValue={user?.full_name ?? ""} disabled className="max-w-sm" />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-foreground" htmlFor="email">
                  Email
                </label>
                <Input id="email" type="email" defaultValue={user?.email ?? ""} disabled className="max-w-sm" />
              </div>
              <div className="flex gap-2">
                <Button size="sm" disabled>Save Changes — later stage</Button>
                <Button size="sm" variant="outline" onClick={() => signOut()}>
                  Sign out
                </Button>
              </div>
            </CardContent>
          </Card>

          <Separator />

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">AI provider</CardTitle>
              <CardDescription className="text-xs">
                Read from the server&apos;s <code>apps/api/.env</code>. Keys never reach
                the browser, and changes require an API restart.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              {aiQuery.isLoading && (
                <p className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                  Checking provider status…
                </p>
              )}
              {aiQuery.isError && (
                <div
                  className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800"
                  role="alert"
                >
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                  <span>
                    {aiQuery.error instanceof ApiClientError
                      ? aiQuery.error.message
                      : "Could not read AI provider status."}
                  </span>
                </div>
              )}
              {ai && (
                <>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="outline">
                      {ai.provider} / {ai.model}
                    </Badge>
                    {ai.configured ? (
                      <Badge variant="success" className="gap-1">
                        <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
                        Configured
                      </Badge>
                    ) : (
                      <Badge variant="destructive">Not configured</Badge>
                    )}
                    {ai.is_mock && <Badge variant="warning">Fixture mode</Badge>}
                  </div>
                  <p className="text-xs text-muted-foreground">{ai.message}</p>
                  {ai.is_mock && (
                    <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                      Fixture mode means no AI model is called. To use a real provider,
                      set <code>AI_PROVIDER</code>, <code>AI_MODEL</code>, and{" "}
                      <code>AI_API_KEY</code> in <code>apps/api/.env</code>, then restart
                      the API.
                    </p>
                  )}
                </>
              )}
            </CardContent>
          </Card>

          <Separator />

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Disclaimer</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs leading-relaxed text-muted-foreground">
                NyayaSaar is a legal research assistance tool. It does not constitute legal advice,
                does not replace qualified counsel, and all outputs must be independently verified
                by a qualified legal professional before use in any proceedings.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

