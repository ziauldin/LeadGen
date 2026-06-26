"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { OutreachChecklist } from "@/components/compliance/outreach-checklist";
import { PageHeader } from "@/components/layout/page-header";
import { LeadStatusBadge } from "@/components/leads/lead-status-badge";
import { ScoreBadge } from "@/components/leads/score-badge";
import { LoadingState } from "@/components/shared/loading-error";
import { leadsApi } from "@/lib/api/endpoints";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function LeadDetailPage() {
  const params = useParams();
  const id = Number(params.id);

  const { data: lead, isLoading } = useQuery({
    queryKey: ["leads", id],
    queryFn: () => leadsApi.get(id),
    enabled: Number.isFinite(id),
  });

  const { data: readiness } = useQuery({
    queryKey: ["leads", id, "outreach-readiness"],
    queryFn: () => leadsApi.outreachReadiness(id),
    enabled: Number.isFinite(id),
  });

  if (isLoading) return <LoadingState />;
  if (!lead) return <p className="text-sm text-destructive">Lead not found.</p>;

  const outreachReady = readiness?.ready ?? false;

  return (
    <div>
      <PageHeader
        title={lead.full_name}
        description={lead.job_title ?? undefined}
        actions={
          <Link
            href={`/email-studio?lead_id=${lead.id}`}
            className={cn(buttonVariants({ variant: outreachReady ? "default" : "outline" }))}
          >
            Email studio
          </Link>
        }
      />
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Overview</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Status</span>
              <LeadStatusBadge status={lead.status} />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Score</span>
              <ScoreBadge score={lead.score} />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Email</span>
              <span>{lead.primary_email ?? "—"}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Company</span>
              <span>{lead.company?.name ?? "—"}</span>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Compliance</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <p>{lead.compliance_source_note ?? "No compliance note recorded."}</p>
            {lead.source_url ? (
              <a
                href={lead.source_url}
                target="_blank"
                rel="noreferrer"
                className="text-primary hover:underline"
              >
                Source URL
              </a>
            ) : null}
          </CardContent>
        </Card>
        <div className="md:col-span-2">
          <OutreachChecklist lead={lead} issues={readiness?.issues ?? []} />
        </div>
      </div>
    </div>
  );
}
