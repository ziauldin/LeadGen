import type { ReactNode } from "react";
import { Lock } from "lucide-react";
import { cn } from "@/lib/utils";

/** A titled white card used by every settings page. */
export function SettingsCard({
  title,
  description,
  actions,
  children,
  className,
  id,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  id?: string;
}) {
  const headingId = id ? `${id}-heading` : undefined;
  return (
    <section
      id={id}
      aria-labelledby={headingId}
      className={cn(
        "rounded-lg border border-[var(--outline-variant)] bg-white p-4 shadow-sm sm:p-6",
        className,
      )}
    >
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h2 id={headingId} className="text-[16px] font-semibold text-[var(--on-surface)]">
            {title}
          </h2>
          {description ? (
            <div className="mt-1 text-[13px] leading-[20px] text-[var(--on-surface-variant)]">
              {description}
            </div>
          ) : null}
        </div>
        {actions ? <div className="flex shrink-0 flex-wrap gap-2">{actions}</div> : null}
      </div>
      {children}
    </section>
  );
}

/** Label, control, hint and error laid out consistently. */
export function Field({
  label,
  htmlFor,
  hint,
  error,
  required,
  children,
  className,
}: {
  label: string;
  htmlFor: string;
  hint?: ReactNode;
  error?: string;
  required?: boolean;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("space-y-1.5", className)}>
      <label htmlFor={htmlFor} className="block text-[13px] font-medium text-[var(--on-surface)]">
        {label}
        {required ? (
          <span className="text-[var(--error)]" aria-hidden>
            {" "}
            *
          </span>
        ) : null}
      </label>
      {children}
      {error ? (
        <p id={`${htmlFor}-error`} className="text-[12px] text-[var(--error)]" role="alert">
          {error}
        </p>
      ) : hint ? (
        <p id={`${htmlFor}-hint`} className="text-[12px] leading-[18px] text-[var(--on-surface-variant)]">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

export function AdminOnlyNotice({ what = "change these settings" }: { what?: string }) {
  return (
    <p className="mb-4 flex items-start gap-2 rounded-md bg-[var(--surface-container-low)] px-3 py-2 text-[12px] text-[var(--on-surface-variant)]">
      <Lock className="mt-0.5 size-3.5 shrink-0" aria-hidden />
      Only workspace admins and owners can {what}. Ask one of them if something needs updating.
    </p>
  );
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}
