"use client";

import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { useState } from "react";
import { toast } from "sonner";
import { AnalyticsBridge } from "@/components/analytics-provider";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/hooks/use-auth";
import { WorkspaceProvider } from "@/hooks/use-workspace";
import { ApiError, getErrorMessage } from "@/lib/api/client";

const Devtools =
  process.env.NODE_ENV === "development"
    ? dynamic(
        () =>
          import("@tanstack/react-query-devtools").then((mod) => mod.ReactQueryDevtools),
        { ssr: false },
      )
    : () => null;

declare module "@tanstack/react-query" {
  interface Register {
    mutationMeta: { silent?: boolean };
  }
}

export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        retry: (failureCount, error) =>
          !(error instanceof ApiError && error.status >= 400 && error.status < 500) &&
          failureCount < 2,
      },
    },
    // A workspace that requires two-factor sends members without it to set it up.
    queryCache: new QueryCache({
      onError: (error) => {
        if (
          error instanceof ApiError &&
          error.status === 403 &&
          (error.detail as { code?: string } | undefined)?.code === "mfa_required" &&
          typeof window !== "undefined" &&
          !window.location.pathname.startsWith("/settings/security")
        ) {
          window.location.assign("/settings/security?required=1");
        }
      },
    }),
    // Every failed mutation tells the user why, unless the caller handles it itself.
    mutationCache: new MutationCache({
      onError: (error, _variables, _context, mutation) => {
        if (mutation.meta?.silent || mutation.options.onError) return;
        toast.error(getErrorMessage(error));
      },
    }),
  });
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(makeQueryClient);

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <WorkspaceProvider>
          {children}
          <AnalyticsBridge />
        </WorkspaceProvider>
      </AuthProvider>
      <Toaster richColors closeButton position="top-right" />
      <Devtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}
