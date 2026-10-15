"use client";

import { useQuery } from "@tanstack/react-query";
import { Info } from "lucide-react";
import { ErrorState } from "@/components/shared/loading-error";
import { SettingsCard } from "@/components/settings/settings-card";
import { useWorkspace } from "@/hooks/use-workspace";
import { billingApi, campaignsApi, workspacesApi } from "@/lib/api/endpoints";
import { cn } from "@/lib/utils";

export const METRIC_LABELS: Record<string, { label: string; unit?: string }> = {
  monthly_sends: { label: "Emails sent this month" },
  monthly_leads: { label: "Leads added this month" },
  monthly_llm_tokens: { label: "AI tokens this month" },
  daily_enrichments: { label: "Company enrichments today" },
  daily_hunter_lookups: { label: "Email lookups today" },
  seats: { label: "Team seats" },
  max_campaigns: { label: "Campaigns" },
};

function metricLabel(metric: string) {
  return METRIC_LABELS[metric]?.label ?? metric.replaceAll("_", " ");
}

function resetText(period: string) {
  if (period === "day") return "Resets at midnight UTC";
  if (period === "month") return "Resets on the 1st of each month";
  return "";
}

function UsageBar({
  label,
  used,
  limit,
  note,
}: {
  label: string;
  used: number;
  limit: number;
  note?: string;
}) {
  const unlimited = limit <= 0;
  const percent = unlimited ? 0 : Math.min(100, Math.round((used / limit) * 100));
  const tone =
    percent >= 100 ? "bg-[var(--error)]" : percent >= 80 ? "bg-[var(--tertiary-fixed-dim)]" : "bg-[var(--primary)]";
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-3 text-[13px]">
        <span className="font-medium text-[var(--on-surface)]">{label}</span>
        <span className="whitespace-nowrap tabular-nums text-[var(--on-surface-variant)]">
          <span className="font-semibold text-[var(--on-surface)]">{used.toLocaleString()}</span>
          {unlimited ? " · no limit" : ` of ${limit.toLocaleString()}`}
        </span>
      </div>
      {!unlimited ? (
        <div
          role="progressbar"
          aria-label={label}
          aria-valuemin={0}
          aria-valuemax={limit}
          aria-valuenow={Math.min(used, limit)}
          aria-valuetext={`${used.toLocaleString()} of ${limit.toLocaleString()} (${percent}%)`}
          className="h-2 overflow-hidden rounded-full bg-[var(--surface-container-high)]"
        >
          <div className={cn("h-full rounded-full transition-[width]", tone)} style={{ width: `${percent}%` }} />
        </div>
      ) : null}
      <p className="text-[11px] text-[var(--outline)]">
        {percent >= 100
          ? `Limit reached. ${note ?? ""}`
          : percent >= 80
            ? `Almost at the limit. ${note ?? ""}`
            : note}
      </p>
    </div>
  );
}

export function UsageOverview() {
  const billing = useQuery({ queryKey: ["billing"], queryFn: billingApi.summary });
  const { hasRole } = useWorkspace();
  const isAdmin = hasRole("admin");
  const members = useQuery({ queryKey: ["members"], queryFn: workspacesApi.members });
  // Pending invitations hold a seat too, but only admins can see them.
  const invitations = useQuery({
    queryKey: ["invitations"],
    queryFn: workspacesApi.invitations,
    enabled: isAdmin,
  });
  const campaigns = useQuery({
    queryKey: ["campaigns", { limit: 1 }],
    queryFn: () => campaignsApi.list({ limit: 1 }),
  });

  if (billing.error) {
    return <ErrorState error={billing.error} onRetry={() => void billing.refetch()} />;
  }

  const data = billing.data;
  return (
    <div className="space-y-6">
      <SettingsCard
        id="plan"
        title="Plan"
        description="Limits protect your sending reputation and keep costs predictable."
      >
        {!data ? (
          <div className="h-12 animate-pulse rounded-md bg-[var(--surface-container-high)]" role="status" aria-label="Loading plan" />
        ) : (
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-[12px] uppercase tracking-wide text-[var(--on-surface-variant)]">Current plan</p>
              <p className="text-[22px] font-bold capitalize text-[var(--on-surface)]">{data.plan}</p>
            </div>
            <p className="flex max-w-md items-start gap-2 rounded-md bg-[var(--surface-container-low)] px-3 py-2 text-[12px] text-[var(--on-surface-variant)]">
              <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
              Upgrades aren&apos;t available yet. If you need higher limits, contact support.
            </p>
          </div>
        )}
      </SettingsCard>

      <SettingsCard id="usage" title="Usage" description="What this workspace has used in the current period.">
        {!data ? (
          <div className="space-y-4" role="status" aria-label="Loading usage">
            {[0, 1, 2, 3].map((key) => (
              <div key={key} className="h-10 animate-pulse rounded-md bg-[var(--surface-container-high)]" />
            ))}
          </div>
        ) : (
          <div className="grid gap-x-8 gap-y-5 md:grid-cols-2">
            {data.usage.map((item) => (
              <UsageBar
                key={item.metric}
                label={metricLabel(item.metric)}
                used={item.used}
                limit={item.limit}
                note={resetText(item.period)}
              />
            ))}
            {data.limits.seats != null ? (
              <UsageBar
                label={metricLabel("seats")}
                used={(members.data?.length ?? 0) + (invitations.data?.length ?? 0)}
                limit={data.limits.seats}
                note={
                  isAdmin
                    ? "Members plus pending invitations. Revoke unused invitations to free a seat."
                    : "Members of this workspace. Pending invitations also use a seat."
                }
              />
            ) : null}
            {data.limits.max_campaigns != null ? (
              <UsageBar
                label={metricLabel("max_campaigns")}
                used={campaigns.data?.total ?? 0}
                limit={data.limits.max_campaigns}
                note="All campaigns in this workspace."
              />
            ) : null}
          </div>
        )}
      </SettingsCard>
    </div>
  );
}
