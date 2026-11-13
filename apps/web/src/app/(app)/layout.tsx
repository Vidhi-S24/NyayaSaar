"use client";

/**
 * Authenticated app layout — guards all workspace routes.
 *
 * While the session is being restored, a full-screen loading state is shown.
 * Unauthenticated visitors are redirected to /signin.
 */

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { useAuth } from "@/lib/auth/auth-context";

function AuthLoader() {
  return (
    <div
      className="flex h-screen items-center justify-center bg-background"
      role="status"
      aria-live="polite"
    >
      <div className="flex flex-col items-center gap-3">
        <div
          className="h-6 w-6 animate-spin rounded-full border-2 border-muted-foreground/30 border-t-ink-700"
          aria-hidden="true"
        />
        <p className="text-sm text-muted-foreground">Checking session…</p>
      </div>
    </div>
  );
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace("/signin");
    }
  }, [status, router]);

  if (status !== "authenticated") {
    return <AuthLoader />;
  }

  return <AppShell>{children}</AppShell>;
}
