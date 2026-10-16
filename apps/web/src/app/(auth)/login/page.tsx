"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AuthAlert, AuthField, AuthShell, AuthSubmit } from "@/components/auth/auth-shell";
import { Captcha } from "@/components/auth/captcha";
import { getAuthErrorMessage, useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api/client";
import { socialSignInUrl, ssoApi } from "@/lib/api/endpoints";
import { loginSchema, type LoginFormValues } from "@/lib/validations/forms";

function needsCaptcha(error: unknown) {
  return (
    error instanceof ApiError &&
    (error.detail as { code?: string } | undefined)?.code === "captcha_required"
  );
}

function TwoFactorStep({ mfaToken, next }: { mfaToken: string; next: string | null }) {
  const { completeTwoFactor } = useAuth();
  const [code, setCode] = useState("");
  const [recovery, setRecovery] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await completeTwoFactor(mfaToken, code.trim(), next);
    } catch (err) {
      setError(getAuthErrorMessage(err));
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-5" noValidate>
      <p className="text-[14px] text-[var(--on-surface-variant)]">
        {recovery
          ? "Enter one of the recovery codes you saved when you turned on two-factor authentication."
          : "Enter the 6-digit code from your authenticator app."}
      </p>
      <AuthField
        label={recovery ? "Recovery code" : "Authentication code"}
        name="code"
        autoComplete="one-time-code"
        inputMode={recovery ? "text" : "numeric"}
        autoFocus
        placeholder={recovery ? "xxxx-xxxx-xxxx" : "123456"}
        value={code}
        onChange={(event) => setCode(event.target.value)}
      />
      {error && <AuthAlert kind="error">{error}</AuthAlert>}
      <AuthSubmit loading={submitting || code.trim().length < 6}>
        {submitting ? "Checking…" : "Verify and sign in"}
      </AuthSubmit>
      <button
        type="button"
        onClick={() => {
          setRecovery((value) => !value);
          setCode("");
          setError(null);
        }}
        className="text-[13px] font-semibold text-[var(--primary)] hover:underline"
      >
        {recovery ? "Use a code from my authenticator app" : "Use a recovery code instead"}
      </button>
    </form>
  );
}

function SignInOptions({ next }: { next: string | null }) {
  const providers = useQuery({ queryKey: ["auth-providers"], queryFn: ssoApi.providers, retry: false });
  const options = providers.data;
  if (!options || (!options.google && !options.microsoft && !options.sso)) return null;
  const linkClass =
    "flex w-full items-center justify-center gap-2 rounded border border-[var(--outline-variant)] bg-white py-2.5 text-[13px] font-medium text-[var(--on-surface)] hover:bg-[var(--surface-container-low)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)]";
  return (
    <div className="mt-6 space-y-3">
      <div className="relative flex items-center justify-center">
        <span className="absolute inset-x-0 border-t border-[var(--outline-variant)]" />
        <span className="relative bg-[var(--surface-container-lowest)] px-3 text-[11px] uppercase tracking-wider text-[var(--on-surface-variant)]">
          or
        </span>
      </div>
      {options.google && (
        <a href={socialSignInUrl("google", next)} className={linkClass}>
          Continue with Google
        </a>
      )}
      {options.microsoft && (
        <a href={socialSignInUrl("microsoft", next)} className={linkClass}>
          Continue with Microsoft
        </a>
      )}
      {options.sso && (
        <Link href={next ? `/login/sso?next=${encodeURIComponent(next)}` : "/login/sso"} className={linkClass}>
          Sign in with single sign-on (SSO)
        </Link>
      )}
    </div>
  );
}

function LoginForm() {
  const { login } = useAuth();
  const params = useSearchParams();
  const next = params.get("next");
  const [error, setError] = useState<string | null>(params.get("error"));
  const [mfaToken, setMfaToken] = useState<string | null>(params.get("mfa_token"));
  const [showCaptcha, setShowCaptcha] = useState(false);
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const [captchaReset, setCaptchaReset] = useState(0);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({ resolver: zodResolver(loginSchema) });

  if (mfaToken) return <TwoFactorStep mfaToken={mfaToken} next={next} />;

  async function onSubmit(values: LoginFormValues) {
    setError(null);
    try {
      const result = await login(values.email, values.password, next, captchaToken);
      if (result?.mfaToken) setMfaToken(result.mfaToken);
    } catch (err) {
      if (needsCaptcha(err)) setShowCaptcha(true);
      if (showCaptcha) setCaptchaReset((value) => value + 1);
      setError(getAuthErrorMessage(err));
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-5" noValidate>
      {params.get("reset") === "1" && (
        <AuthAlert kind="success">Your password was changed. Sign in with the new one.</AuthAlert>
      )}
      <AuthField
        label="Email"
        type="email"
        autoComplete="email"
        placeholder="you@company.com"
        error={errors.email?.message}
        {...register("email")}
      />
      <AuthField
        label="Password"
        type="password"
        autoComplete="current-password"
        error={errors.password?.message}
        hint={
          <Link
            href="/forgot-password"
            className="text-[12px] font-semibold text-[var(--primary)] hover:underline"
          >
            Forgot password?
          </Link>
        }
        {...register("password")}
      />
      {showCaptcha && <Captcha onToken={setCaptchaToken} resetKey={captchaReset} />}
      {error && <AuthAlert kind="error">{error}</AuthAlert>}
      <AuthSubmit loading={isSubmitting}>{isSubmitting ? "Signing in…" : "Sign in"}</AuthSubmit>
      <SignInOptions next={next} />
    </form>
  );
}

export default function LoginPage() {
  return (
    <AuthShell
      title="Welcome back"
      subtitle="Sign in to your account to continue."
      footer={
        <>
          New to LeadsGen?{" "}
          <Link href="/register" className="font-semibold text-[var(--primary)] hover:underline">
            Create an account
          </Link>
        </>
      }
    >
      <Suspense>
        <LoginForm />
      </Suspense>
    </AuthShell>
  );
}
