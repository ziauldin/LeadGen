import type { LeadStatus } from "@/lib/api/types";

export const LEAD_STATUS_LABELS: Record<LeadStatus, string> = {
  new: "New",
  enriched: "Enriched",
  qualified: "Qualified",
  ready_for_outreach: "Ready for outreach",
  contacted: "Contacted",
  replied: "Replied",
  meeting_booked: "Meeting booked",
  client: "Client",
  disqualified: "Disqualified",
  opted_out: "Opted out",
};

export const ALL_LEAD_STATUSES = Object.keys(LEAD_STATUS_LABELS) as LeadStatus[];

/**
 * Statuses a person can set by hand. `opted_out` only comes from an unsubscribe or a
 * suppression, so the API refuses it and we never offer it.
 */
export const SETTABLE_LEAD_STATUSES = ALL_LEAD_STATUSES.filter(
  (status) => status !== "opted_out",
);

export function leadStatusLabel(status: string): string {
  return LEAD_STATUS_LABELS[status as LeadStatus] ?? status.replace(/_/g, " ");
}

/** "3 days ago" style text for table cells; the exact date goes in a title. */
export function formatRelativeDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  const diff = Date.now() - date.getTime();
  if (Number.isNaN(diff)) return "—";
  const minutes = Math.round(diff / 60_000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days} day${days === 1 ? "" : "s"} ago`;
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString();
}
