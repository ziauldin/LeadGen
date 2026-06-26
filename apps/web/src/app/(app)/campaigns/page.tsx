"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PageHeader } from "@/components/layout/page-header";
import { campaignsApi } from "@/lib/api/endpoints";
import { cn } from "@/lib/utils";

export default function CampaignsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => campaignsApi.list(),
  });

  return (
    <div>
      <PageHeader
        title="Campaigns"
        description="Outreach sequences with send gates."
        actions={
          <Link href="/campaigns/new" className={cn(buttonVariants())}>
            New campaign
          </Link>
        }
      />
      {isLoading ? <p className="text-sm text-muted-foreground">Loading…</p> : null}
      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Daily limit</TableHead>
              <TableHead>Window</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data?.items.map((campaign) => (
              <TableRow key={campaign.id}>
                <TableCell>
                  <Link href={`/campaigns/${campaign.id}`} className="font-medium hover:underline">
                    {campaign.name}
                  </Link>
                </TableCell>
                <TableCell>
                  <Badge variant="secondary">{campaign.status}</Badge>
                </TableCell>
                <TableCell>{campaign.daily_send_limit}</TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {campaign.sending_window_start ?? "—"} – {campaign.sending_window_end ?? "—"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
