"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Download } from "lucide-react";
import { KpiCard } from "@/components/shared/kpi-card";
import { ErrorState, LoadingState } from "@/components/shared/loading-error";
import { Button } from "@/components/ui/button";
import { formatRate } from "@/components/campaigns/format";
import { useWorkspace } from "@/hooks/use-workspace";
import { analyticsApi } from "@/lib/api/endpoints";
import type { components } from "@/lib/api/schema";

type Row = components["schemas"]["BreakdownRow"];

const RANGES = [7, 30, 90] as const;
const BREAKDOWNS = [
  { key: "by_campaign", label: "Campaign" },
  { key: "by_step", label: "Step" },
  { key: "by_variant", label: "A/B version" },
  { key: "by_mailbox", label: "Mailbox" },
  { key: "by_template", label: "Template" },
] as const;
const SERIES = [
  { key: "sent", label: "Sent", color: "var(--primary)" },
  { key: "replies", label: "Replies", color: "var(--secondary)" },
  { key: "positive", label: "Interested", color: "#15803d" },
  { key: "bounced", label: "Bounced", color: "var(--error)" },
] as const;

/** Workspace analytics: totals, a daily chart and breakdowns by campaign, step, version, mailbox and template. */
export function AnalyticsView() {
  const { can } = useWorkspace();
  const [days, setDays] = useState<(typeof RANGES)[number]>(30);
  const [breakdown, setBreakdown] = useState<(typeof BREAKDOWNS)[number]["key"]>("by_campaign");
  const overview = useQuery({ queryKey: ["analytics", days], queryFn: () => analyticsApi.overview({ days }) });
  const exportCsv = useMutation({ mutationFn: () => analyticsApi.exportCsv(days) });

  if (overview.isPending) return <LoadingState message="Loading analytics…" />;
  if (overview.isError) return <ErrorState error={overview.error} onRetry={() => void overview.refetch()} />;
  const data = overview.data;
  const totals = data.totals;
  const rows: Row[] = data[breakdown];
  const chartLabel = `Daily totals over the last ${days} days: ${totals.sent} sent, ${totals.replies} replies, ${totals.positive} interested, ${totals.bounced} bounced`;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="group" aria-label="Date range" className="flex gap-1">
          {RANGES.map((range) => (
            <Button key={range} size="sm" variant={range === days ? "default" : "outline"} aria-pressed={range === days} onClick={() => setDays(range)}>
              Last {range} days
            </Button>
          ))}
        </div>
        {can("data.export") ? (
          <Button size="sm" variant="outline" onClick={() => exportCsv.mutate()} disabled={exportCsv.isPending}>
            <Download aria-hidden />
            Export CSV
          </Button>
        ) : null}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard label="Emails sent" value={totals.sent.toLocaleString()} />
        <KpiCard label="Reply rate" value={formatRate(totals.reply_rate)} />
        <KpiCard label="Interested rate" value={formatRate(totals.positive_rate)} />
        <KpiCard label="Bounce rate" value={formatRate(totals.bounce_rate)} />
      </div>

      <section aria-labelledby="analytics-series-title" className="rounded-lg border border-[var(--outline-variant)] bg-white p-4 shadow-sm">
        <h2 id="analytics-series-title" className="text-[14px] font-semibold text-[var(--on-surface)]">
          Day by day
        </h2>
        <p className="mb-3 text-[12px] text-[var(--on-surface-variant)]">Replies are counted on the day they arrive.</p>
        <div className="h-[260px] w-full" role="img" aria-label={chartLabel}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data.series} margin={{ top: 4, right: 12, bottom: 0, left: -16 }}>
              <CartesianGrid stroke="var(--outline-variant)" strokeOpacity={0.5} vertical={false} />
              <XAxis dataKey="date" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "var(--on-surface-variant)" }} tickFormatter={(value: string) => value.slice(5)} minTickGap={16} />
              <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "var(--on-surface-variant)" }} />
              <Tooltip contentStyle={{ borderRadius: 8, border: "1px solid var(--outline-variant)", fontSize: 12 }} />
              {SERIES.map((line) => (
                <Line key={line.key} type="monotone" dataKey={line.key} name={line.label} stroke={line.color} strokeWidth={2} dot={false} isAnimationActive={false} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
        <ul className="mt-2 flex flex-wrap gap-4 text-[12px] text-[var(--on-surface-variant)]" aria-hidden>
          {SERIES.map((line) => (
            <li key={line.key} className="flex items-center gap-1.5">
              <span className="inline-block size-2.5 rounded-full" style={{ background: line.color }} />
              {line.label}
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="analytics-breakdown-title" className="rounded-lg border border-[var(--outline-variant)] bg-white p-4 shadow-sm">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 id="analytics-breakdown-title" className="text-[14px] font-semibold text-[var(--on-surface)]">
            Breakdown
          </h2>
          <div role="group" aria-label="Break down by" className="flex flex-wrap gap-1">
            {BREAKDOWNS.map((item) => (
              <Button key={item.key} size="sm" variant={item.key === breakdown ? "default" : "outline"} aria-pressed={item.key === breakdown} onClick={() => setBreakdown(item.key)}>
                {item.label}
              </Button>
            ))}
          </div>
        </div>
        {rows.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[13px]">
              <thead className="text-[12px] text-[var(--on-surface-variant)]">
                <tr>
                  <th scope="col" className="py-2 pr-3 font-medium">{BREAKDOWNS.find((b) => b.key === breakdown)!.label}</th>
                  <th scope="col" className="py-2 pr-3 text-right font-medium">Sent</th>
                  <th scope="col" className="py-2 pr-3 text-right font-medium">Replies</th>
                  <th scope="col" className="py-2 pr-3 text-right font-medium">Reply rate</th>
                  <th scope="col" className="py-2 pr-3 text-right font-medium">Interested</th>
                  <th scope="col" className="py-2 text-right font-medium">Bounce rate</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={String(row.key)} className="border-t border-[var(--outline-variant)]">
                    <th scope="row" className="py-2 pr-3 font-medium text-[var(--on-surface)]">{row.label}</th>
                    <td className="py-2 pr-3 text-right tabular-nums">{row.sent.toLocaleString()}</td>
                    <td className="py-2 pr-3 text-right tabular-nums">{row.replies.toLocaleString()}</td>
                    <td className="py-2 pr-3 text-right tabular-nums">{formatRate(row.reply_rate)}</td>
                    <td className="py-2 pr-3 text-right tabular-nums">{row.positive.toLocaleString()}</td>
                    <td className="py-2 text-right tabular-nums">{formatRate(row.bounce_rate)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-[13px] text-[var(--on-surface-variant)]">No emails were sent in this period.</p>
        )}
      </section>
    </div>
  );
}
