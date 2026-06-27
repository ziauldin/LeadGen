import type { LeadStatus } from "@/lib/api/types";
import { cn } from "@/lib/utils";

interface StatusBadgeProps {
  status: LeadStatus | string;
  className?: string;
}

const statusConfig: Record<
  string,
  { label: string; bg: string; text: string; dot: string }
> = {
  new: {
    label: "New",
    bg: "var(--surface-variant)",
    text: "var(--on-surface-variant)",
    dot: "var(--outline)",
  },
  enriched: {
    label: "Enriched",
    bg: "var(--tertiary-container)",
    text: "var(--on-tertiary-container)",
    dot: "var(--on-tertiary-container)",
  },
  qualified: {
    label: "Qualified",
    bg: "var(--primary-fixed)",
    text: "var(--on-primary-fixed)",
    dot: "var(--on-primary-fixed)",
  },
  ready_for_outreach: {
    label: "Ready",
    bg: "var(--secondary-fixed)",
    text: "var(--on-secondary-fixed)",
    dot: "var(--on-secondary-fixed)",
  },
  contacted: {
    label: "Contacted",
    bg: "var(--primary-container)",
    text: "var(--on-primary-container)",
    dot: "var(--on-primary-container)",
  },
  replied: {
    label: "Replied",
    bg: "var(--secondary-container)",
    text: "var(--on-secondary-container)",
    dot: "var(--on-secondary-container)",
  },
  meeting_booked: {
    label: "Meeting Booked",
    bg: "var(--secondary-container)",
    text: "var(--on-secondary-container)",
    dot: "var(--on-secondary-container)",
  },
  client: {
    label: "Client",
    bg: "var(--secondary-fixed)",
    text: "var(--on-secondary-fixed)",
    dot: "var(--on-secondary-fixed)",
  },
  disqualified: {
    label: "Disqualified",
    bg: "var(--error-container)",
    text: "var(--on-error-container)",
    dot: "var(--on-error-container)",
  },
  opted_out: {
    label: "Opted Out",
    bg: "var(--error-container)",
    text: "var(--on-error-container)",
    dot: "var(--on-error-container)",
  },
};

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = statusConfig[status] ?? {
    label: status,
    bg: "var(--surface-variant)",
    text: "var(--on-surface-variant)",
    dot: "var(--outline)",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[12px] font-semibold leading-[16px] tracking-[0.05em] whitespace-nowrap",
        className,
      )}
      style={{ background: config.bg, color: config.text }}
    >
      <span
        className="w-1.5 h-1.5 rounded-full shrink-0"
        style={{ background: config.dot }}
      />
      {config.label}
    </span>
  );
}
