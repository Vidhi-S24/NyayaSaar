import { Settings, User, Key, Bell, Shield } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { DemoNotice } from "@/components/shared/demo-notice";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";

export const metadata = { title: "Settings" };

export default function SettingsPage() {
  return (
    <div className="flex flex-col gap-6 p-6 pb-10">
      <DemoNotice message="Settings are not yet persisted. Authentication and user management will be added in Stage 3." />

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
              { icon: Key, label: "API & Integrations", note: "Stage 5" },
              { icon: Bell, label: "Notifications", note: "Stage 3" },
              { icon: Shield, label: "Security & Privacy", note: "Stage 3" },
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
                Authentication is added in Stage 3. Fields below are non-functional placeholders.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-foreground" htmlFor="name">
                  Display Name
                </label>
                <Input id="name" defaultValue="Vidhi Soni" disabled className="max-w-sm" />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-foreground" htmlFor="email">
                  Email
                </label>
                <Input id="email" type="email" defaultValue="demo@nyayasaar.in" disabled className="max-w-sm" />
              </div>
              <Button size="sm" disabled>Save Changes — Stage 3</Button>
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

