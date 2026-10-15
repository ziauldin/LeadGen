"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AuthAlert, AuthField, AuthShell, AuthSubmit } from "@/components/auth/auth-shell";
import { getAuthErrorMessage, useAuth } from "@/hooks/use-auth";
import { loginSchema, type LoginFormValues } from "@/lib/validations/forms";

function LoginForm() {
  const { login } = useAuth();
  const params = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({ resolver: zodResolver(loginSchema) });

  async function onSubmit(values: LoginFormValues) {
    setError(null);
    try {
      await login(values.email, values.password, params.get("next"));
    } catch (err) {
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
      {error && <AuthAlert kind="error">{error}</AuthAlert>}
      <AuthSubmit loading={isSubmitting}>{isSubmitting ? "Signing in…" : "Sign in"}</AuthSubmit>
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
