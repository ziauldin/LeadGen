"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AuthShell } from "@/components/auth/auth-shell";
import { safeNext, useAuth } from "@/hooks/use-auth";

/** Landing page after a Google, Microsoft or SSO sign-in has set the session cookie. */
function Complete() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const next = useSearchParams().get("next");

  useEffect(() => {
    if (loading) return;
    router.replace(user ? safeNext(next) : "/login?error=Sign-in%20didn%27t%20finish.%20Please%20try%20again.");
  }, [loading, user, next, router]);

  return <p role="status">Signing you in…</p>;
}

export default function AuthCompletePage() {
  return (
    <AuthShell title="Signing you in">
      <Suspense>
        <Complete />
      </Suspense>
    </AuthShell>
  );
}
