"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, ArrowUpRight, ShieldCheck } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { KpiCard } from "@/components/shared/kpi-card";
import { ErrorState } from "@/components/shared/loading-error";
import { OnboardingChecklist } from "@/components/dashboard/onboarding-checklist";
import { LeadStatusChart } from "@/components/dashboard/lead-status-chart";
import { dashboardApi } from "@/lib/api/endpoints";
import type { DashboardSummary } from "@/lib/api/types";

type Kpi = {
  label: string;
  value: number;
  href?: string;
  hint?: string;
  dot?: "green" | "red" | "amber" | "blue" | "none";
  highlight?: boolean;
};

function KpiTile({ kpi }: { kpi: Kpi }) {
  const card = (
    <KpiCard
      label={kpi.label}
      value={kpi.value}
      dot={kpi.dot}
      highlight={kpi.highlight}
      className="h-full"
      trend={
        kpi.hint || kpi.href ? (
          <span className="inline-flex items-center gap-1 text-[11px] text-[var(--on-surface-variant)]">
            {kpi.hint}
            {kpi.href ? <ArrowRight className="size-3" aria-hidden /> : null}
          </span>
        ) : undefined
      }
    />
  );
  if (!kpi.href) return card;
  return (
    <Link
      href={kpi.href}
      className="block rounded-lg transition-shadow hover:shadow-md focus-visible:ring-2 focus-visible:ring-[var(--primary)] focus-visible:ring-offset-2 focus-visible:outline-none"
    >
      {card}
    </Link>
  );
}

function KpiGroup({ title, kpis }: { title: string; kpis: Kpi[] }) {
  return (
    <section aria-label={title}>
      <h3 className="mb-2 text-[12px] font-semibold tracking-wider text-[var(--on-surface-variant)] uppercase">
        {title}
      </h3>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {kpis.map((kpi) => (
          <KpiTile key={kpi.label} kpi={kpi} />
        ))}
      </div>
    </section>
  );
}

function groups(data: DashboardSummary): { title: string; kpis: Kpi[] }[] {
  return [
    {
      title: "Pipeline",
      kpis: [
        { label: "Total leads", value: data.total_leads, href: "/leads", hint: "View leads" },
        { label: "Qualified", value: data.qualified_leads, dot: "blue" },
        { label: "Contacted", value: data.contacted_leads },
        { label: "Replied", value: data.replied_leads, dot: "green" },
      ],
    },
    {
      title: "Outreach",
      kpis: [
        {
          label: "Waiting for approval",
          value: data.pending_approval,
          href: "/approvals",
          hint: data.pending_approval > 0 ? "Review drafts" : "All caught up",
          dot: data.pending_approval > 0 ? "amber" : "none",
          highlight: data.pending_approval > 0,
        },
        { label: "Approved, queued to send", value: data.approved_emails, dot: "blue" },
        { label: "Sent today", value: data.sent_today },
        {
          label: "Active campaigns",
          value: data.active_campaigns,
          href: "/campaigns",
          hint: "View campaigns",
        },
      ],
    },
    {
      title: "Replies and compliance",
      kpis: [
        {
          label: "Replies to review",
          value: data.pending_replies,
          href: "/replies",
          hint: data.pending_replies > 0 ? "Classify replies" : "Nothing waiting",
          dot: data.pending_replies > 0 ? "amber" : "none",
        },
        { label: "Positive replies", value: data.positive_replies, dot: "green", highlight: true },
        { label: "Opted out", value: data.opted_out_leads },
        { label: "Suppressed contacts", value: data.suppressed_contacts },
      ],
    },
  ];
}

export default function DashboardPage() {
  const summary = useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: dashboardApi.summary,
  });

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Your pipeline, what's waiting for you and how outreach is going."
      />

      <OnboardingChecklist />

      {summary.isLoading ? (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4" aria-busy="true" aria-label="Loading">
          {Array.from({ length: 8 }).map((_, i) => (
            <div
              key={i}
              className="h-24 animate-pulse rounded-lg border border-[var(--outline-variant)] bg-white"
            />
          ))}
        </div>
      ) : summary.error || !summary.data ? (
        <ErrorState error={summary.error} onRetry={() => summary.refetch()} />
      ) : (
        <div className="flex flex-col gap-6">
          {groups(summary.data).map((group) => (
            <KpiGroup key={group.title} title={group.title} kpis={group.kpis} />
          ))}

          <LeadStatusChart counts={summary.data.lead_status_counts} />

          <div className="flex flex-col gap-3 rounded-lg border border-[var(--outline-variant)] bg-[var(--surface-container-low)] p-4 sm:flex-row sm:items-start">
            <ShieldCheck className="size-5 shrink-0 text-[var(--primary)]" aria-hidden />
            <div className="flex-1">
              <p className="text-[13px] font-semibold text-[var(--on-surface)]">
                Every email is approved by a person
              </p>
              <p className="text-[13px] text-[var(--on-surface-variant)]">
                Drafts wait in Approvals until someone on your team approves them. Every email has
                a one-click unsubscribe, and suppressed or opted-out contacts are never emailed.
              </p>
            </div>
            <Link
              href="/settings"
              className="inline-flex shrink-0 items-center gap-1 text-[12px] font-semibold text-[var(--primary)] hover:underline"
            >
              Suppression settings
              <ArrowUpRight className="size-3.5" aria-hidden />
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
