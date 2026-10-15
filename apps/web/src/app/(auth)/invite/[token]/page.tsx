"use client";

import Link from "next/link";
import { use, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AuthAlert, AuthShell } from "@/components/auth/auth-shell";
import { workspacesApi } from "@/lib/api/endpoints";
import { getErrorMessage, setWorkspaceId } from "@/lib/api/client";
import { useAuth } from "@/hooks/use-auth";

export default function InvitePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user, loading } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [accepting, setAccepting] = useState(false);
  const next = encodeURIComponent(`/invite/${token}`);

  const preview = useQuery({
    queryKey: ["invitation", token],
    queryFn: () => workspacesApi.previewInvitation(token),
    retry: false,
  });

  async function accept() {
    setAccepting(true);
    setError(null);
    try {
      const workspace = await workspacesApi.acceptInvitation(token);
      setWorkspaceId(workspace.id);
      queryClient.clear();
      router.push("/dashboard");
    } catch (err) {
      setError(getErrorMessage(err));
      setAccepting(false);
    }
  }

  return (
    <AuthShell title="Join a workspace">
      {preview.isLoading || loading ? (
        <p role="status">Checking your invitation…</p>
      ) : preview.error ? (
        <AuthAlert kind="error">
          This invitation is invalid, expired or was revoked. Ask for a new one.
        </AuthAlert>
      ) : preview.data ? (
        <div className="flex flex-col gap-5">
          <p className="text-[14px] text-[var(--on-surface)]">
            You&apos;ve been invited to join <strong>{preview.data.workspace_name}</strong> as{" "}
            {preview.data.role === "admin" ? "an admin" : `a ${preview.data.role}`}.
          </p>
          <p className="text-[13px] text-[var(--on-surface-variant)]">
            The invitation was sent to {preview.data.email}.
          </p>
          {error && <AuthAlert kind="error">{error}</AuthAlert>}
          {user ? (
            user.email.toLowerCase() === preview.data.email.toLowerCase() ? (
              <button
                type="button"
                onClick={() => void accept()}
                disabled={accepting}
                className="w-full rounded bg-[var(--primary)] py-3 text-[13px] font-medium text-white disabled:opacity-60"
              >
                {accepting ? "Joining…" : `Join ${preview.data.workspace_name}`}
              </button>
            ) : (
              <AuthAlert kind="error">
                You&apos;re signed in as {user.email}. Sign in as {preview.data.email} to accept.
              </AuthAlert>
            )
          ) : (
            <div className="flex flex-col gap-3">
              <Link
                href={`/register?next=${next}`}
                className="w-full rounded bg-[var(--primary)] py-3 text-center text-[13px] font-medium text-white"
              >
                Create an account
              </Link>
              <Link
                href={`/login?next=${next}`}
                className="text-center text-[13px] font-semibold text-[var(--primary)] hover:underline"
              >
                I already have an account
              </Link>
            </div>
          )}
        </div>
      ) : null}
    </AuthShell>
  );
}
