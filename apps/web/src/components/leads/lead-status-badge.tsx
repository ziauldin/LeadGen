import type { LeadStatus } from "@/lib/api/types";
import { Badge } from "@/components/ui/badge";

const labels: Record<LeadStatus, string> = {
  new: "New",
  enriched: "Enriched",
  qualified: "Qualified",
  ready_for_outreach: "Ready",
  contacted: "Contacted",
  replied: "Replied",
  meeting_booked: "Meeting booked",
  client: "Client",
  disqualified: "Disqualified",
  opted_out: "Opted out",
};

export function LeadStatusBadge({ status }: { status: LeadStatus }) {
  return <Badge variant="secondary">{labels[status] ?? status}</Badge>;
}
