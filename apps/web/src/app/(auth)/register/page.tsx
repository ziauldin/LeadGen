"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AuthAlert, AuthField, AuthShell, AuthSubmit } from "@/components/auth/auth-shell";
import { Captcha, captchaConfigured } from "@/components/auth/captcha";
import { getAuthErrorMessage, useAuth } from "@/hooks/use-auth";
import { registerSchema, type RegisterFormValues } from "@/lib/validations/forms";

function RegisterForm() {
  const { register: signUp } = useAuth();
  const params = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const [captchaReset, setCaptchaReset] = useState(0);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormValues>({ resolver: zodResolver(registerSchema) });

  async function onSubmit(values: RegisterFormValues) {
    setError(null);
    try {
      await signUp(values.name, values.email, values.password, params.get("next"), captchaToken);
    } catch (err) {
      setCaptchaReset((value) => value + 1);
      setError(getAuthErrorMessage(err));
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-5" noValidate>
      <AuthField
        label="Your name"
        autoComplete="name"
        error={errors.name?.message}
        {...register("name")}
      />
      <AuthField
        label="Work email"
        type="email"
        autoComplete="email"
        placeholder="you@company.com"
        error={errors.email?.message}
        {...register("email")}
      />
      <AuthField
        label="Password"
        type="password"
        autoComplete="new-password"
        error={errors.password?.message}
        {...register("password")}
      />
      <Captcha onToken={setCaptchaToken} resetKey={captchaReset} />
      {error && <AuthAlert kind="error">{error}</AuthAlert>}
      <AuthSubmit loading={isSubmitting || (captchaConfigured && !captchaToken)}>
        {isSubmitting ? "Creating account…" : "Create account"}
      </AuthSubmit>
      <p className="text-[12px] text-[var(--on-surface-variant)]">
        We&apos;ll email you a link to confirm your address before you can send outreach.
      </p>
    </form>
  );
}

export default function RegisterPage() {
  return (
    <AuthShell
      title="Create your workspace"
      subtitle="Start with a free plan. No card needed."
      footer={
        <>
          Already have an account?{" "}
          <Link href="/login" className="font-semibold text-[var(--primary)] hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <Suspense>
        <RegisterForm />
      </Suspense>
    </AuthShell>
  );
}
