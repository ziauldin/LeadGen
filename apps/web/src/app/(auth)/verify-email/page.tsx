"use client";

import Link from "next/link";
import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AuthAlert, AuthShell } from "@/components/auth/auth-shell";
import { authApi } from "@/lib/api/endpoints";
import { getErrorMessage } from "@/lib/api/client";
import { useAuth } from "@/hooks/use-auth";

function Verify() {
  const token = useSearchParams().get("token");
  const { user, refreshUser } = useAuth();
  const [state, setState] = useState<"working" | "done" | "error">(token ? "working" : "error");
  const [message, setMessage] = useState<string>(
    token ? "" : "This verification link is incomplete.",
  );
  const started = useRef(false);

  useEffect(() => {
    if (!token || started.current) return;
    started.current = true;
    authApi
      .verifyEmail(token)
      .then(async () => {
        setState("done");
        if (user) await refreshUser();
      })
      .catch((err) => {
        setState("error");
        setMessage(getErrorMessage(err));
      });
  }, [token, user, refreshUser]);

  if (state === "working") return <p role="status">Confirming your email…</p>;
  if (state === "done") {
    return (
      <div className="flex flex-col gap-4">
        <AuthAlert kind="success">Thanks, your email address is confirmed.</AuthAlert>
        <Link
          href={user ? "/dashboard" : "/login"}
          className="text-center text-[13px] font-semibold text-[var(--primary)] hover:underline"
        >
          {user ? "Go to your dashboard" : "Sign in"}
        </Link>
      </div>
    );
  }
  return (
    <AuthAlert kind="error">
      {message} Links expire after 24 hours; you can send a new one from the banner after
      signing in.
    </AuthAlert>
  );
}

export default function VerifyEmailPage() {
  return (
    <AuthShell title="Confirm your email">
      <Suspense>
        <Verify />
      </Suspense>
    </AuthShell>
  );
}
