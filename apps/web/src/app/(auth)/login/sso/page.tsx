"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AuthAlert, AuthField, AuthShell, AuthSubmit } from "@/components/auth/auth-shell";
import { ssoApi } from "@/lib/api/endpoints";
import { getErrorMessage } from "@/lib/api/client";

function SsoForm() {
  const next = useSearchParams().get("next");
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const found = await ssoApi.discover(email.trim());
      const url = new URL(found.url);
      if (next) url.searchParams.set("next", next);
      window.location.assign(url.pathname + url.search);
    } catch (err) {
      setError(getErrorMessage(err));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-5" noValidate>
      <AuthField
        label="Work email"
        type="email"
        name="email"
        autoComplete="email"
        placeholder="you@company.com"
        value={email}
        onChange={(event) => setEmail(event.target.value)}
      />
      {error && <AuthAlert kind="error">{error}</AuthAlert>}
      <AuthSubmit loading={busy || !email.includes("@")}>
        {busy ? "Finding your company…" : "Continue"}
      </AuthSubmit>
    </form>
  );
}

export default function SsoLoginPage() {
  return (
    <AuthShell
      title="Sign in with SSO"
      subtitle="We'll send you to your company's sign-in page."
      footer={
        <Link href="/login" className="font-semibold text-[var(--primary)] hover:underline">
          Back to sign in
        </Link>
      }
    >
      <Suspense>
        <SsoForm />
      </Suspense>
    </AuthShell>
  );
}
