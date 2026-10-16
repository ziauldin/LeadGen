"use client";

import { AnalyticsView } from "@/components/analytics/analytics-view";
import { PageHeader } from "@/components/layout/page-header";
import { useFlags } from "@/hooks/use-flags";

export default function AnalyticsPage() {
  const flags = useFlags();
  return (
    <div>
      <PageHeader title="Analytics" description="How your outreach performs, by day, campaign, step, A/B version, mailbox and template." />
      {flags.analytics_v2 === false ? (
        <p className="rounded-lg border border-[var(--outline-variant)] bg-white p-4 text-[13px] text-[var(--on-surface-variant)]">
          Analytics isn&apos;t turned on for this workspace yet.
        </p>
      ) : flags.analytics_v2 ? (
        <AnalyticsView />
      ) : null}
    </div>
  );
}
