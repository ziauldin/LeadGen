"use client";

import type { ComponentProps, ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

/** Small, consistent form pieces for the campaign screens. */

export function FieldLabel({
  htmlFor,
  children,
  optional,
  className,
}: {
  htmlFor?: string;
  children: ReactNode;
  optional?: boolean;
  className?: string;
}) {
  return (
    <label
      htmlFor={htmlFor}
      className={cn("mb-1.5 block text-[13px] font-semibold text-[var(--on-surface)]", className)}
    >
      {children}
      {optional ? (
        <span className="ml-1 font-normal text-[var(--on-surface-variant)]">(optional)</span>
      ) : null}
    </label>
  );
}

export function FieldHint({ id, children }: { id?: string; children: ReactNode }) {
  return (
    <p id={id} className="mt-1 text-[12px] leading-[18px] text-[var(--on-surface-variant)]">
      {children}
    </p>
  );
}

export function FieldError({ id, message }: { id?: string; message?: string }) {
  if (!message) return null;
  return (
    <p id={id} role="alert" className="mt-1 text-[12px] font-medium text-[var(--error)]">
      {message}
    </p>
  );
}

export const nativeControlClass =
  "h-9 w-full min-w-0 rounded-lg border border-input bg-white px-2.5 text-[13px] text-[var(--on-surface)] outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:bg-[var(--surface-container-low)] disabled:opacity-70 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20";

/** A styled native <select>: accessible, keyboard friendly and works well on phones. */
export function NativeSelect({ className, children, ...props }: ComponentProps<"select">) {
  return (
    <div className="relative">
      <select {...props} className={cn(nativeControlClass, "appearance-none pr-8", className)}>
        {children}
      </select>
      <ChevronDown
        className="pointer-events-none absolute top-1/2 right-2.5 size-4 -translate-y-1/2 text-[var(--on-surface-variant)]"
        aria-hidden
      />
    </div>
  );
}

/** A checkbox styled as a switch; still a real checkbox for forms and screen readers. */
export function Switch({
  label,
  description,
  className,
  ...props
}: Omit<ComponentProps<"input">, "type"> & { label: ReactNode; description?: ReactNode }) {
  return (
    <label className={cn("flex cursor-pointer items-start gap-3", className)}>
      <span className="relative mt-0.5 inline-flex shrink-0">
        <input type="checkbox" role="switch" className="peer sr-only" {...props} />
        <span
          aria-hidden
          className="h-5 w-9 rounded-full bg-[var(--outline-variant)] transition-colors peer-checked:bg-[var(--primary)] peer-focus-visible:ring-3 peer-focus-visible:ring-ring/50 peer-disabled:opacity-50"
        />
        <span
          aria-hidden
          className="absolute top-0.5 left-0.5 size-4 rounded-full bg-white shadow-sm transition-transform peer-checked:translate-x-4"
        />
      </span>
      <span className="min-w-0">
        <span className="block text-[13px] font-semibold text-[var(--on-surface)]">{label}</span>
        {description ? (
          <span className="mt-0.5 block text-[12px] leading-[18px] text-[var(--on-surface-variant)]">
            {description}
          </span>
        ) : null}
      </span>
    </label>
  );
}

export function FormSection({
  title,
  description,
  children,
  id,
}: {
  title: string;
  description?: ReactNode;
  children: ReactNode;
  id?: string;
}) {
  return (
    <section
      aria-labelledby={id}
      className="rounded-lg border border-[var(--outline-variant)] bg-white shadow-sm"
    >
      <header className="border-b border-[var(--outline-variant)] px-4 py-4 sm:px-6">
        <h3 id={id} className="text-[16px] font-semibold text-[var(--on-surface)]">
          {title}
        </h3>
        {description ? (
          <p className="mt-1 text-[13px] text-[var(--on-surface-variant)]">{description}</p>
        ) : null}
      </header>
      <div className="px-4 py-5 sm:px-6">{children}</div>
    </section>
  );
}

/** Renders text with {{variables}} shown as small chips (for read-only previews). */
export function HighlightedTemplate({ text }: { text: string }) {
  const parts = text.split(/({{\s*[^{}]*?\s*}})/g);
  return (
    <>
      {parts.map((part, index) =>
        /^{{.*}}$/.test(part) ? (
          <span
            key={index}
            className="rounded bg-[var(--primary-fixed)] px-1 font-mono text-[12px] text-[var(--primary)]"
          >
            {part}
          </span>
        ) : (
          <span key={index}>{part}</span>
        ),
      )}
    </>
  );
}
