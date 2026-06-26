import type { ReactNode } from "react";

export function LoadingState({ message = "Loading…" }: { message?: string }) {
  return <p className="text-sm text-muted-foreground">{message}</p>;
}

export function ErrorState({
  message = "Something went wrong.",
  action,
}: {
  message?: string;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm">
      <p className="text-destructive">{message}</p>
      {action ? <div className="mt-3">{action}</div> : null}
    </div>
  );
}
