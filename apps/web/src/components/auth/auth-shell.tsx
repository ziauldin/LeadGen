import type { InputHTMLAttributes, ReactNode } from "react";
import { forwardRef } from "react";
import { Database, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";

/** Two-panel layout shared by sign-in, sign-up and the account recovery pages. */
export function AuthShell({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--background)] p-4 md:p-8">
      <div className="flex min-h-[560px] w-full max-w-[1040px] flex-col overflow-hidden rounded-xl border border-[var(--outline-variant)] bg-[var(--surface-container-lowest)] shadow-[0_10px_15px_-3px_rgba(0,0,0,0.1)] md:flex-row">
        <div className="flex w-full flex-col justify-between gap-8 border-b border-[var(--outline-variant)] bg-[var(--surface-container-low)] p-8 md:w-[45%] md:border-b-0 md:border-r md:p-12">
          <div className="flex items-center gap-2">
            <div className="flex size-8 items-center justify-center rounded bg-[var(--primary)] text-white">
              <Database className="size-4" aria-hidden />
            </div>
            <span className="text-[20px] font-extrabold tracking-tight text-[var(--on-surface)]">
              LeadsGen
            </span>
          </div>
          <div className="hidden md:block">
            <p className="mb-6 text-[32px] font-bold leading-[40px] tracking-[-0.02em] text-[var(--on-surface)]">
              Compliance-first
              <br />
              <span className="text-[var(--primary)]">B2B outreach.</span>
            </p>
            <p className="mb-8 max-w-sm text-[15px] leading-[24px] text-[var(--on-surface-variant)]">
              Find the right people, write to them with care, and keep every email under human
              review.
            </p>
            <div className="flex w-fit items-center gap-3 rounded-lg border border-[var(--outline-variant)] bg-white/80 p-3">
              <ShieldCheck className="size-4 text-[var(--primary)]" aria-hidden />
              <p className="text-[12px] text-[var(--on-surface-variant)]">
                One-click unsubscribe and suppression on every email
              </p>
            </div>
          </div>
        </div>

        <div className="flex w-full flex-col justify-center p-8 md:w-[55%] md:p-12 lg:p-16">
          <div className="mx-auto w-full max-w-[400px]">
            <h1 className="mb-2 text-[24px] font-semibold leading-[32px] tracking-[-0.015em] text-[var(--on-surface)]">
              {title}
            </h1>
            {subtitle ? (
              <div className="mb-8 text-[14px] text-[var(--on-surface-variant)]">{subtitle}</div>
            ) : (
              <div className="mb-8" />
            )}
            {children}
            {footer ? (
              <div className="mt-8 text-center text-[13px] text-[var(--on-surface-variant)]">
                {footer}
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}

type FieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  error?: string;
  hint?: ReactNode;
};

export const AuthField = forwardRef<HTMLInputElement, FieldProps>(function AuthField(
  { label, error, hint, id, className, ...props },
  ref,
) {
  const fieldId = id ?? props.name;
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between">
        <label htmlFor={fieldId} className="block text-[13px] font-medium text-[var(--on-surface)]">
          {label}
        </label>
        {hint}
      </div>
      <input
        ref={ref}
        id={fieldId}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${fieldId}-error` : undefined}
        className={cn(
          "w-full rounded border border-[var(--outline-variant)] bg-white px-3 py-2.5 text-[14px] text-[var(--on-surface)] outline-none transition-colors",
          "focus:border-[var(--primary)] focus:ring-2 focus:ring-[var(--primary)]/20 aria-invalid:border-[var(--error)]",
          className,
        )}
        {...props}
      />
      {error ? (
        <p id={`${fieldId}-error`} className="mt-1 text-[12px] text-[var(--error)]">
          {error}
        </p>
      ) : null}
    </div>
  );
});

export function AuthSubmit({ children, loading }: { children: ReactNode; loading?: boolean }) {
  return (
    <button
      type="submit"
      disabled={loading}
      className="mt-2 w-full rounded bg-[var(--primary)] py-3 text-[13px] font-medium text-white shadow-sm transition-opacity hover:opacity-90 disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[var(--primary)]"
    >
      {children}
    </button>
  );
}

export function AuthAlert({ kind, children }: { kind: "error" | "success"; children: ReactNode }) {
  return (
    <div
      role={kind === "error" ? "alert" : "status"}
      className={cn(
        "rounded border px-3 py-2 text-[13px]",
        kind === "error"
          ? "border-[var(--error)]/30 bg-[var(--error)]/5 text-[var(--error)]"
          : "border-emerald-300 bg-emerald-50 text-emerald-800",
      )}
    >
      {children}
    </div>
  );
}
