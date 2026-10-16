"use client";

import type { ReactNode } from "react";
import { AlertTriangle, RotateCw } from "lucide-react";
import { getErrorMessage } from "@/lib/api/client";

export function LoadingState({ message = "Loading…" }: { message?: string }) {
  return (
    <p className="py-6 text-sm text-muted-foreground" role="status">
      {message}
    </p>
  );
}

/** Shown wherever a query fails, with the real reason and a retry button. */
export function ErrorState({
  message,
  error,
  onRetry,
  action,
}: {
  message?: string;
  error?: unknown;
  onRetry?: () => void;
  action?: ReactNode;
}) {
  const text = message ?? (error ? getErrorMessage(error) : "Something went wrong.");
  return (
    <div
      role="alert"
      className="flex flex-col gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm sm:flex-row sm:items-center"
    >
      <AlertTriangle className="size-4 shrink-0 text-destructive" aria-hidden />
      <p className="flex-1 text-destructive">{text}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 self-start rounded-md border border-destructive/30 px-3 py-1 text-[13px] font-medium text-destructive hover:bg-destructive/10 sm:self-auto"
        >
          <RotateCw className="size-3.5" aria-hidden />
          Try again
        </button>
      ) : null}
      {action}
    </div>
  );
}
