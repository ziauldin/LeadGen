"use client";

import { Eye } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { getImpersonation } from "@/lib/api/client";

/** Always visible while a platform admin is viewing the app as a customer. */
export function ImpersonationBanner() {
  const { user, logout } = useAuth();
  const impersonation = user?.impersonation as { admin_email?: string; read_only?: boolean } | null | undefined;
  if (!impersonation) return null;
  const session = getImpersonation();
  const ends = session ? new Date(session.expiresAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : null;

  return (
    <div
      role="status"
      className="mb-4 flex flex-col gap-2 rounded-lg border border-[var(--error)] bg-[var(--error-container)] px-4 py-3 text-[13px] text-[var(--on-error-container)] sm:flex-row sm:items-center sm:justify-between"
    >
      <p className="flex items-start gap-2">
        <Eye className="mt-0.5 size-4 shrink-0" aria-hidden />
        <span>
          <span className="font-semibold">
            Viewing {session?.workspaceName ?? "this workspace"} as {user?.name} ({user?.email})
          </span>
          {" · "}
          {impersonation.read_only ? "Read-only" : "Changes allowed"}
          {ends ? ` · Ends at ${ends}` : ""}
          {impersonation.admin_email ? ` · Signed in as ${impersonation.admin_email}` : ""}
        </span>
      </p>
      <Button size="sm" variant="outline" className="bg-white" onClick={() => void logout()}>
        End session
      </Button>
    </div>
  );
}
