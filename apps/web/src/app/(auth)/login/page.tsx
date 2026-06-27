"use client";

import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Database, Lock, Mail, Play, ShieldCheck } from "lucide-react";
import { useAuth, getAuthErrorMessage } from "@/hooks/use-auth";
import { loginSchema, type LoginFormValues } from "@/lib/validations/forms";

export default function LoginPage() {
  const { login } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setValue,
    formState: { isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
  });

  function fillDemo() {
    setValue("email", "demo@wellpredict.io");
    setValue("password", "demo1234");
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4 md:p-8" style={{ background: "var(--background)" }}>
      <div
        className="flex flex-col md:flex-row w-full max-w-[1040px] min-h-[600px] rounded-xl overflow-hidden border"
        style={{
          background: "var(--surface-container-lowest)",
          borderColor: "var(--outline-variant)",
          boxShadow: "0px 10px 15px -3px rgba(0,0,0,0.1)",
        }}
      >
        {/* Left panel — brand */}
        <div
          className="relative w-full md:w-[45%] p-8 md:p-12 flex flex-col justify-between border-b md:border-b-0 md:border-r overflow-hidden"
          style={{
            background: "var(--surface-container-low)",
            borderColor: "var(--outline-variant)",
          }}
        >
          {/* Brand */}
          <div className="relative z-10 flex items-center gap-2">
            <div
              className="w-8 h-8 rounded flex items-center justify-center text-white"
              style={{ background: "var(--primary)" }}
            >
              <Database className="w-4 h-4" />
            </div>
            <span
              className="text-[20px] font-extrabold tracking-tight"
              style={{ color: "var(--on-surface)" }}
            >
              LeadsGen
            </span>
          </div>

          {/* Hero copy */}
          <div className="relative z-10 mt-auto">
            <h1
              className="text-[36px] font-bold leading-[44px] tracking-[-0.02em] mb-6"
              style={{ color: "var(--on-surface)" }}
            >
              Compliance-first
              <br />
              <span style={{ color: "var(--primary)" }}>B2B Lead Intelligence.</span>
            </h1>
            <p
              className="text-[16px] leading-[24px] mb-10 max-w-sm"
              style={{ color: "var(--on-surface-variant)" }}
            >
              Access surgical-grade professional data with absolute certainty. Built for
              high-stakes enterprise sales teams.
            </p>

            {/* Badge */}
            <div
              className="flex items-center gap-3 backdrop-blur-sm border p-3 rounded-lg w-fit"
              style={{
                background: "rgba(255,255,255,0.8)",
                borderColor: "var(--outline-variant)",
              }}
            >
              <div
                className="w-8 h-8 rounded flex items-center justify-center"
                style={{ background: "rgba(108,248,187,0.3)", color: "var(--on-secondary-container)" }}
              >
                <ShieldCheck className="w-4 h-4" />
              </div>
              <div>
                <p
                  className="text-[12px] font-semibold uppercase tracking-wider"
                  style={{ color: "var(--on-surface)" }}
                >
                  GDPR &amp; CCPA
                </p>
                <p className="text-[12px]" style={{ color: "var(--on-surface-variant)" }}>
                  Fully compliant infrastructure
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Right panel — form */}
        <div className="w-full md:w-[55%] p-8 md:p-12 lg:p-16 flex flex-col justify-center" style={{ background: "var(--surface-container-lowest)" }}>
          <div className="w-full max-w-[400px] mx-auto">
            <div className="mb-8">
              <h2
                className="text-[24px] font-semibold leading-[32px] tracking-[-0.015em] mb-2"
                style={{ color: "var(--on-surface)" }}
              >
                Welcome back
              </h2>
              <p className="text-[14px]" style={{ color: "var(--on-surface-variant)" }}>
                Sign in to your account to continue.
              </p>
            </div>

            <form
              onSubmit={handleSubmit(async (values) => {
                setError(null);
                try {
                  await login(values.email, values.password);
                } catch (err) {
                  setError(getAuthErrorMessage(err));
                }
              })}
              className="flex flex-col gap-5"
            >
              {/* Email */}
              <div>
                <label
                  htmlFor="email"
                  className="block text-[13px] font-medium mb-1.5"
                  style={{ color: "var(--on-surface)" }}
                >
                  Email address
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Mail className="w-4 h-4" style={{ color: "var(--outline)" }} />
                  </div>
                  <input
                    id="email"
                    type="email"
                    autoComplete="email"
                    placeholder="name@company.com"
                    {...register("email")}
                    className="w-full pl-10 pr-3 py-2.5 rounded text-[14px] outline-none transition-colors"
                    style={{
                      background: "var(--surface-container-lowest)",
                      border: "1px solid var(--outline-variant)",
                      color: "var(--on-surface)",
                    }}
                    onFocus={(e) => {
                      e.target.style.borderColor = "var(--primary)";
                      e.target.style.boxShadow = "0 0 0 1px var(--primary)";
                    }}
                    onBlur={(e) => {
                      e.target.style.borderColor = "var(--outline-variant)";
                      e.target.style.boxShadow = "none";
                    }}
                  />
                </div>
              </div>

              {/* Password */}
              <div>
                <div className="flex justify-between items-center mb-1.5">
                  <label
                    htmlFor="password"
                    className="text-[13px] font-medium"
                    style={{ color: "var(--on-surface)" }}
                  >
                    Password
                  </label>
                  <a
                    href="#"
                    className="text-[12px] font-semibold tracking-wide"
                    style={{ color: "var(--primary)" }}
                  >
                    Forgot password?
                  </a>
                </div>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Lock className="w-4 h-4" style={{ color: "var(--outline)" }} />
                  </div>
                  <input
                    id="password"
                    type="password"
                    autoComplete="current-password"
                    placeholder="••••••••"
                    {...register("password")}
                    className="w-full pl-10 pr-3 py-2.5 rounded text-[14px] outline-none transition-colors"
                    style={{
                      background: "var(--surface-container-lowest)",
                      border: "1px solid var(--outline-variant)",
                      color: "var(--on-surface)",
                    }}
                    onFocus={(e) => {
                      e.target.style.borderColor = "var(--primary)";
                      e.target.style.boxShadow = "0 0 0 1px var(--primary)";
                    }}
                    onBlur={(e) => {
                      e.target.style.borderColor = "var(--outline-variant)";
                      e.target.style.boxShadow = "none";
                    }}
                  />
                </div>
              </div>

              {error && (
                <p className="text-[13px]" style={{ color: "var(--error)" }}>
                  {error}
                </p>
              )}

              {/* Submit */}
              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full text-white text-[13px] font-medium py-3 rounded transition-opacity duration-150 shadow-sm mt-2 disabled:opacity-60 active:scale-[0.98]"
                style={{ background: "var(--primary)" }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surface-tint)")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "var(--primary)")}
              >
                {isSubmitting ? "Signing in…" : "Sign In"}
              </button>
            </form>

            {/* Divider */}
            <div className="mt-8 relative flex items-center justify-center">
              <div className="absolute inset-x-0 border-t" style={{ borderColor: "var(--outline-variant)" }} />
              <span
                className="relative z-10 px-4 text-[11px] uppercase tracking-wider"
                style={{ background: "var(--surface-container-lowest)", color: "var(--outline)" }}
              >
                or
              </span>
            </div>

            {/* Demo login */}
            <div className="mt-8">
              <button
                type="button"
                onClick={fillDemo}
                className="w-full flex items-center justify-center gap-2 py-3 rounded border text-[13px] font-medium transition-colors duration-150 active:scale-[0.98]"
                style={{
                  background: "var(--surface-container-lowest)",
                  borderColor: "var(--outline-variant)",
                  color: "var(--on-surface)",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surface-container-low)")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "var(--surface-container-lowest)")}
              >
                <Play className="w-4 h-4" style={{ color: "var(--primary)" }} />
                Fill demo credentials
              </button>

              <p className="text-center text-[12px] mt-4" style={{ color: "var(--on-surface-variant)" }}>
                Don&apos;t have an account?{" "}
                <Link
                  href="/register"
                  className="font-medium"
                  style={{ color: "var(--primary)" }}
                >
                  Register
                </Link>
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
