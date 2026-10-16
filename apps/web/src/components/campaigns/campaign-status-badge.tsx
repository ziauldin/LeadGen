import type { CampaignStatus } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type Tone = { label: string; bg: string; text: string; dot: string };

const NEUTRAL: Tone = {
  label: "",
  bg: "var(--surface-variant)",
  text: "var(--on-surface-variant)",
  dot: "var(--outline)",
};
const GOOD: Omit<Tone, "label"> = {
  bg: "var(--secondary-fixed)",
  text: "var(--on-secondary-fixed)",
  dot: "var(--secondary)",
};
const WARN: Omit<Tone, "label"> = {
  bg: "var(--tertiary-fixed)",
  text: "var(--on-tertiary-fixed)",
  dot: "var(--tertiary)",
};
const INFO: Omit<Tone, "label"> = {
  bg: "var(--primary-fixed)",
  text: "var(--on-primary-fixed)",
  dot: "var(--primary)",
};
const BAD: Omit<Tone, "label"> = {
  bg: "var(--error-container)",
  text: "var(--on-error-container)",
  dot: "var(--error)",
};

const CAMPAIGN: Record<CampaignStatus, Tone> = {
  draft: { ...NEUTRAL, label: "Draft" },
  active: { ...GOOD, label: "Active" },
  paused: { ...WARN, label: "Paused" },
  completed: { ...INFO, label: "Completed" },
};

/** Statuses of enrollments and campaign emails. */
const OTHER: Record<string, Tone> = {
  // enrollments
  active: { ...GOOD, label: "Active" },
  paused: { ...WARN, label: "Paused" },
  completed: { ...INFO, label: "Completed" },
  replied: { ...GOOD, label: "Replied" },
  bounced: { ...BAD, label: "Bounced" },
  opted_out: { ...BAD, label: "Opted out" },
  stopped: { ...NEUTRAL, label: "Stopped" },
  failed: { ...BAD, label: "Failed" },
  // emails
  draft: { ...WARN, label: "Draft" },
  pending_approval: { ...WARN, label: "Awaiting approval" },
  approved: { ...INFO, label: "Approved" },
  queued: { ...INFO, label: "Queued" },
  sending: { ...INFO, label: "Sending" },
  sent: { ...GOOD, label: "Sent" },
  complained: { ...BAD, label: "Complaint" },
  rejected: { ...NEUTRAL, label: "Rejected" },
  cancelled: { ...NEUTRAL, label: "Cancelled" },
};

function Pill({ tone, className }: { tone: Tone; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-[12px] leading-[16px] font-semibold",
        className,
      )}
      style={{ background: tone.bg, color: tone.text }}
    >
      <span className="size-1.5 shrink-0 rounded-full" style={{ background: tone.dot }} aria-hidden />
      {tone.label}
    </span>
  );
}

export function CampaignStatusBadge({
  status,
  className,
}: {
  status: CampaignStatus | string;
  className?: string;
}) {
  const tone = CAMPAIGN[status as CampaignStatus] ?? { ...NEUTRAL, label: status };
  return <Pill tone={tone} className={className} />;
}

export function SequenceStatusBadge({ status, className }: { status: string; className?: string }) {
  const tone = OTHER[status] ?? {
    ...NEUTRAL,
    label: status.charAt(0).toUpperCase() + status.slice(1).replace(/_/g, " "),
  };
  return <Pill tone={tone} className={className} />;
}
