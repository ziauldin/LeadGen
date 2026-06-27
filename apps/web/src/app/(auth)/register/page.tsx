"use client";

import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Database, Key, Lock, Mail, Shield, User } from "lucide-react";
import { useAuth, getAuthErrorMessage } from "@/hooks/use-auth";
import { registerSchema, type RegisterFormValues } from "@/lib/validations/forms";

export default function RegisterPage() {
  const { register: registerUser } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
  });

  const password = watch("password") ?? "";

  function getStrengthWidth() {
    if (password.length === 0) return "0%";
    if (password.length < 8) return "25%";
    if (password.length < 12) return "50%";
    if (/[!@#$%^&*()]/.test(password)) return "100%";
    return "75%";
  }
  const strengthWidth = getStrengthWidth();
  const strengthColor =
    strengthWidth === "100%"
      ? "var(--secondary)"
      : strengthWidth === "75%"
        ? "var(--primary)"
        : strengthWidth === "50%"
          ? "#f59e0b"
          : "var(--error)";

  function inputClass() {
    return "w-full pl-10 pr-3 py-2.5 rounded text-[14px] outline-none transition-all";
  }

  function inputStyle(): React.CSSProperties {
    return {
      background: "var(--surface-container-lowest)",
      border: "1px solid var(--outline-variant)",
      color: "var(--on-surface)",
    };
  }

  return (
    <div
      className="min-h-screen flex"
      style={{ background: "var(--surface-container-lowest)" }}
    >
      {/* Left panel — dark brand side */}
      <div
        className="hidden lg:flex lg:w-5/12 relative flex-col justify-between p-12 overflow-hidden"
        style={{ background: "var(--inverse-surface)" }}
      >
        {/* Gradient bg */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              "radial-gradient(ellipse at 60% 40%, rgba(79,70,229,0.3) 0%, transparent 70%)",
          }}
        />

        {/* Brand */}
        <div className="relative z-10 flex items-center gap-2">
          <div
            className="w-8 h-8 rounded flex items-center justify-center"
            style={{ background: "var(--primary)" }}
          >
            <Database className="w-4 h-4 text-white" />
          </div>
          <span
            className="text-[20px] font-bold"
            style={{ color: "var(--inverse-on-surface)" }}
          >
            LeadsGen Pro
          </span>
        </div>

        {/* Bottom content */}
        <div className="relative z-10 max-w-md">
          {/* Compliance badges */}
          <div className="flex gap-3 mb-8">
            {[
              { icon: Shield, label: "SOC 2 Type II" },
              { icon: Lock, label: "End-to-End Encrypted" },
            ].map(({ icon: Icon, label }) => (
              <div
                key={label}
                className="flex items-center gap-2 px-3 py-1.5 rounded border backdrop-blur-sm"
                style={{
                  background: "rgba(255,255,255,0.08)",
                  borderColor: "rgba(255,255,255,0.2)",
                }}
              >
                <Icon
                  className="w-3.5 h-3.5"
                  style={{ color: "var(--primary-fixed-dim)" }}
                />
                <span
                  className="text-[11px] font-semibold uppercase tracking-wider"
                  style={{ color: "var(--primary-fixed-dim)" }}
                >
                  {label}
                </span>
              </div>
            ))}
          </div>

          <h1
            className="text-[36px] font-bold leading-[44px] tracking-[-0.02em] mb-4"
            style={{ color: "#ffffff" }}
          >
            Secure. Precise.
            <br />
            Actionable.
          </h1>
          <p className="text-[16px] leading-[24px]" style={{ color: "var(--outline-variant)" }}>
            Join industry leaders who trust LeadsGen Pro for surgical data acquisition. Your
            compliance and data security are engineered into the foundation.
          </p>
        </div>
      </div>

      {/* Right panel — form */}
      <div className="w-full lg:w-7/12 flex items-center justify-center p-6 sm:p-12 lg:p-24">
        <div className="w-full max-w-[440px]">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-2 mb-10">
            <div
              className="w-8 h-8 rounded flex items-center justify-center"
              style={{ background: "var(--primary)" }}
            >
              <Database className="w-4 h-4 text-white" />
            </div>
            <span
              className="text-[20px] font-bold"
              style={{ color: "var(--on-surface)" }}
            >
              LeadsGen Pro
            </span>
          </div>

          <div className="mb-8">
            <h2
              className="text-[24px] font-semibold leading-[32px] tracking-[-0.015em] mb-2"
              style={{ color: "var(--on-surface)" }}
            >
              Create your account
            </h2>
            <p className="text-[14px]" style={{ color: "var(--on-surface-variant)" }}>
              Start building your high-intent pipeline today.
            </p>
          </div>

          <form
            onSubmit={handleSubmit(async (values) => {
              setError(null);
              try {
                await registerUser(values.name, values.email, values.password);
              } catch (err) {
                setError(getAuthErrorMessage(err));
              }
            })}
            className="flex flex-col gap-5"
          >
            {/* Full Name */}
            <div>
              <label
                htmlFor="name"
                className="block text-[13px] font-medium mb-1.5"
                style={{ color: "var(--on-surface)" }}
              >
                Full Name
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <User className="w-4 h-4" style={{ color: "var(--outline)" }} />
                </div>
                <input
                  id="name"
                  type="text"
                  autoComplete="name"
                  placeholder="Jane Doe"
                  {...register("name")}
                  className={inputClass()}
                  style={inputStyle()}
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
              {errors.name && (
                <p className="text-[12px] mt-1" style={{ color: "var(--error)" }}>
                  {errors.name.message}
                </p>
              )}
            </div>

            {/* Work Email */}
            <div>
              <label
                htmlFor="email"
                className="block text-[13px] font-medium mb-1.5"
                style={{ color: "var(--on-surface)" }}
              >
                Work Email
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Mail className="w-4 h-4" style={{ color: "var(--outline)" }} />
                </div>
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  placeholder="jane@company.com"
                  {...register("email")}
                  className={inputClass()}
                  style={inputStyle()}
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
              {errors.email && (
                <p className="text-[12px] mt-1" style={{ color: "var(--error)" }}>
                  {errors.email.message}
                </p>
              )}
            </div>

            {/* Password */}
            <div>
              <label
                htmlFor="password"
                className="block text-[13px] font-medium mb-1.5"
                style={{ color: "var(--on-surface)" }}
              >
                Password
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Key className="w-4 h-4" style={{ color: "var(--outline)" }} />
                </div>
                <input
                  id="password"
                  type="password"
                  autoComplete="new-password"
                  placeholder="••••••••"
                  {...register("password")}
                  className={inputClass()}
                  style={inputStyle()}
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
              {/* Strength indicator */}
              {password.length > 0 && (
                <div className="mt-2">
                  <div
                    className="h-1 w-full rounded-full overflow-hidden"
                    style={{ background: "var(--surface-container-high)" }}
                  >
                    <div
                      className="h-full rounded-full transition-all duration-300"
                      style={{ width: strengthWidth, background: strengthColor }}
                    />
                  </div>
                </div>
              )}
              {errors.password && (
                <p className="text-[12px] mt-1" style={{ color: "var(--error)" }}>
                  {errors.password.message}
                </p>
              )}
            </div>

            {error && (
              <p className="text-[13px]" style={{ color: "var(--error)" }}>
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full text-white text-[13px] font-medium py-3 rounded transition-opacity shadow-sm mt-2 disabled:opacity-60 active:scale-[0.98]"
              style={{ background: "var(--primary)" }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.background = "var(--surface-tint)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = "var(--primary)")
              }
            >
              {isSubmitting ? "Creating account…" : "Create Account"}
            </button>
          </form>

          <p
            className="text-center text-[13px] mt-8"
            style={{ color: "var(--on-surface-variant)" }}
          >
            Already have an account?{" "}
            <Link href="/login" className="font-medium" style={{ color: "var(--primary)" }}>
              Log in to LeadsGen
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
