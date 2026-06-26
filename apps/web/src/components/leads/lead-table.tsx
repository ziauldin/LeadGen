import Link from "next/link";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { LeadStatusBadge } from "@/components/leads/lead-status-badge";
import { ScoreBadge } from "@/components/leads/score-badge";
import type { Lead } from "@/lib/api/types";

export function LeadTable({ leads }: { leads: Lead[] }) {
  if (leads.length === 0) {
    return <p className="text-sm text-muted-foreground">No leads found.</p>;
  }

  return (
    <div className="rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Company</TableHead>
            <TableHead>Email</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Score</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {leads.map((lead) => (
            <TableRow key={lead.id}>
              <TableCell>
                <Link href={`/leads/${lead.id}`} className="font-medium hover:underline">
                  {lead.full_name}
                </Link>
                {lead.job_title ? (
                  <p className="text-xs text-muted-foreground">{lead.job_title}</p>
                ) : null}
              </TableCell>
              <TableCell>{lead.company?.name ?? "—"}</TableCell>
              <TableCell className="text-sm">{lead.primary_email ?? "—"}</TableCell>
              <TableCell>
                <LeadStatusBadge status={lead.status} />
              </TableCell>
              <TableCell className="text-right">
                <ScoreBadge score={lead.score} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
