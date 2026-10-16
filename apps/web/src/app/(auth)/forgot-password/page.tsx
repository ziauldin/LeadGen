"use client";

import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { AuthAlert, AuthField, AuthShell, AuthSubmit } from "@/components/auth/auth-shell";
import { Captcha, captchaConfigured } from "@/components/auth/captcha";
import { authApi } from "@/lib/api/endpoints";
import { getErrorMessage } from "@/lib/api/client";

const schema = z.object({ email: z.string().email("Enter a valid email") });

export default function ForgotPasswordPage() {
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const [captchaReset, setCaptchaReset] = useState(0);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) });

  async function onSubmit({ email }: z.infer<typeof schema>) {
    setError(null);
    try {
      await authApi.forgotPassword(email, captchaToken);
      setSent(true);
    } catch (err) {
      setCaptchaReset((value) => value + 1);
      setError(getErrorMessage(err));
    }
  }

  return (
    <AuthShell
      title="Reset your password"
      subtitle="Enter your email and we'll send you a reset link."
      footer={
        <Link href="/login" className="font-semibold text-[var(--primary)] hover:underline">
          Back to sign in
        </Link>
      }
    >
      {sent ? (
        <AuthAlert kind="success">
          If an account exists for that address, a reset link is on its way. It expires in an
          hour.
        </AuthAlert>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-5" noValidate>
          <AuthField
            label="Email"
            type="email"
            autoComplete="email"
            error={errors.email?.message}
            {...register("email")}
          />
          <Captcha onToken={setCaptchaToken} resetKey={captchaReset} />
          {error && <AuthAlert kind="error">{error}</AuthAlert>}
          <AuthSubmit loading={isSubmitting || (captchaConfigured && !captchaToken)}>
            {isSubmitting ? "Sending…" : "Send reset link"}
          </AuthSubmit>
        </form>
      )}
    </AuthShell>
  );
}
