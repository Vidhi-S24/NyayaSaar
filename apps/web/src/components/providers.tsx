"use client";

/**
 * Providers — client-side providers for the whole app.
 *
 * - QueryClientProvider: TanStack Query for all server state (cases, health).
 * - AuthProvider: session state backed by the FastAPI JWT API.
 */

import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "@/lib/auth/auth-context";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 15_000,
            retry: (failureCount, error) => {
              // Never retry auth failures or client errors (4xx).
              const status =
                typeof error === "object" && error && "status" in error
                  ? (error as { status: number }).status
                  : undefined;
              if (status && status >= 400 && status < 500) return false;
              return failureCount < 2;
            },
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  );
}
