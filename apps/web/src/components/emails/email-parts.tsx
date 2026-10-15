import { AlertTriangle, FileText, ShieldAlert, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

const MODE_STYLES: Record<string, { label: string; className: string; Icon: typeof Sparkles }> = {
  ai: {
    label: "AI draft",
    className: "border-[var(--primary)]/20 bg-[var(--primary-fixed)] text-[var(--on-primary-fixed)]",
    Icon: Sparkles,
  },
  template_fallback: {
    label: "AI fallback",
    className: "border-amber-300 bg-amber-50 text-amber-900",
    Icon: AlertTriangle,
  },
  template: {
    label: "Template",
    className:
      "border-[var(--outline-variant)] bg-[var(--surface-container-low)] text-[var(--on-surface-variant)]",
    Icon: FileText,
  },
};

/** How a draft was written: from a template, by AI, or a template because AI fell back. */
export function GenerationBadge({
  mode,
  className,
}: {
  mode: string | null | undefined;
  className?: string;
}) {
  const style = MODE_STYLES[mode ?? "template"] ?? MODE_STYLES.template;
  const { Icon } = style;
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold leading-4 whitespace-nowrap",
        style.className,
        className,
      )}
    >
      <Icon className="size-3" aria-hidden />
      {style.label}
    </span>
  );
}

/** Blocking compliance problems. Nothing is rendered when the list is empty. */
export function ProblemList({
  problems,
  title = "Can't approve yet",
  className,
}: {
  problems: string[];
  title?: string;
  className?: string;
}) {
  if (!problems.length) return null;
  return (
    <div
      role="alert"
      className={cn(
        "flex gap-2.5 rounded-lg border border-[var(--error)]/30 bg-[var(--error-container)]/60 px-3 py-2.5 text-[13px] text-[var(--on-error-container)]",
        className,
      )}
    >
      <ShieldAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div className="min-w-0">
        <p className="font-semibold">{title}</p>
        <ul className="mt-1 list-disc space-y-0.5 pl-4">
          {problems.map((problem) => (
            <li key={problem}>{problem}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}

/** Amber callout explaining why an AI draft fell back to the template. */
export function GenerationNote({
  mode,
  note,
  className,
}: {
  mode: string | null | undefined;
  note: string | null | undefined;
  className?: string;
}) {
  if (!note) return null;
  const fallback = mode === "template_fallback";
  return (
    <div
      className={cn(
        "flex gap-2.5 rounded-lg border px-3 py-2.5 text-[13px]",
        fallback
          ? "border-amber-300 bg-amber-50 text-amber-900"
          : "border-[var(--outline-variant)] bg-[var(--surface-container-low)] text-[var(--on-surface-variant)]",
        className,
      )}
    >
      {fallback ? (
        <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
      ) : (
        <Sparkles className="mt-0.5 size-4 shrink-0" aria-hidden />
      )}
      <div className="min-w-0">
        {fallback ? <p className="font-semibold">Written from the template instead</p> : null}
        <p>{note}</p>
      </div>
    </div>
  );
}

/** The email body as the recipient will see it: plain text with line breaks kept. */
export function EmailBody({ body, className }: { body: string; className?: string }) {
  return (
    <div
      className={cn(
        "whitespace-pre-wrap break-words font-sans text-[14px] leading-[22px] text-[var(--on-surface)]",
        className,
      )}
    >
      {body}
    </div>
  );
}
