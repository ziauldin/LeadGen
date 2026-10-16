import type { ReplyClassification } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type Style = { label: string; description: string; bg: string; text: string; dot: string };

export const CLASSIFICATION_STYLES: Record<ReplyClassification, Style> = {
  positive: {
    label: "Positive",
    description: "Interested, wants to talk or asked for more information.",
    bg: "var(--secondary-fixed)",
    text: "var(--on-secondary-fixed)",
    dot: "var(--secondary)",
  },
  neutral: {
    label: "Neutral",
    description: "A question or a reply that doesn't say yes or no.",
    bg: "var(--surface-container-high)",
    text: "var(--on-surface)",
    dot: "var(--outline)",
  },
  objection: {
    label: "Objection",
    description: "Not now, too expensive, already has a solution.",
    bg: "var(--tertiary-fixed)",
    text: "var(--on-tertiary-fixed)",
    dot: "var(--tertiary)",
  },
  unsubscribe: {
    label: "Unsubscribe",
    description: "Asked not to be contacted again. They are suppressed automatically.",
    bg: "var(--error-container)",
    text: "var(--on-error-container)",
    dot: "var(--error)",
  },
  bounce: {
    label: "Bounce",
    description: "The email couldn't be delivered.",
    bg: "var(--error-container)",
    text: "var(--on-error-container)",
    dot: "var(--error)",
  },
  out_of_office: {
    label: "Out of office",
    description: "An automatic away message.",
    bg: "var(--surface-variant)",
    text: "var(--on-surface-variant)",
    dot: "var(--outline)",
  },
  auto_reply: {
    label: "Auto-reply",
    description: "Another automatic response, such as a ticket confirmation.",
    bg: "var(--surface-variant)",
    text: "var(--on-surface-variant)",
    dot: "var(--outline)",
  },
  wrong_person: {
    label: "Wrong person",
    description: "Not the right contact; may point you to someone else.",
    bg: "var(--primary-fixed)",
    text: "var(--on-primary-fixed)",
    dot: "var(--primary)",
  },
  unknown: {
    label: "Unclassified",
    description: "Not labelled yet. Pick a label so your reports stay accurate.",
    bg: "var(--surface-container)",
    text: "var(--on-surface-variant)",
    dot: "var(--outline-variant)",
  },
};

/** Every classification in a sensible order for menus. */
export const CLASSIFICATION_ORDER: ReplyClassification[] = [
  "positive",
  "neutral",
  "objection",
  "wrong_person",
  "unsubscribe",
  "out_of_office",
  "auto_reply",
  "bounce",
  "unknown",
];

export function classificationLabel(classification: string): string {
  return (
    CLASSIFICATION_STYLES[classification as ReplyClassification]?.label ??
    classification.replaceAll("_", " ")
  );
}

export function ReplyClassificationBadge({
  classification,
  className,
}: {
  classification: ReplyClassification;
  className?: string;
}) {
  const style = CLASSIFICATION_STYLES[classification] ?? CLASSIFICATION_STYLES.unknown;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-[12px] font-semibold leading-[18px]",
        className,
      )}
      style={{ background: style.bg, color: style.text }}
    >
      <span className="size-1.5 shrink-0 rounded-full" style={{ background: style.dot }} aria-hidden />
      {style.label}
    </span>
  );
}

/** Small "AI" marker shown when the label came from the language model, with its confidence. */
export function AiLabelMarker({
  classifiedBy,
  confidence,
}: {
  classifiedBy: string | null | undefined;
  confidence: number | null | undefined;
}) {
  if (classifiedBy !== "llm") return null;
  const percent = confidence != null ? Math.round(confidence * 100) : null;
  const title =
    percent != null
      ? `Labelled by AI with ${percent}% confidence. Check it and change it if it's wrong.`
      : "Labelled by AI. Check it and change it if it's wrong.";
  return (
    <span
      className="inline-flex items-center gap-1 rounded border border-[var(--primary)]/25 bg-[var(--primary-fixed)] px-1.5 text-[11px] font-semibold leading-[16px] text-[var(--on-primary-fixed)]"
      title={title}
    >
      AI
      {percent != null ? <span className="font-normal">{percent}%</span> : null}
      <span className="sr-only">{title}</span>
    </span>
  );
}
