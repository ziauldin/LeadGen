"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AlertTriangle, ArrowRight } from "lucide-react";
import { KpiCard } from "@/components/shared/kpi-card";
import { ErrorState } from "@/components/shared/loading-error";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { SequenceStatusBadge } from "@/components/campaigns/campaign-status-badge";
import { RATE_THRESHOLDS, formatRate, rateLevel, type RateLevel } from "@/components/campaigns/format";
import { campaignsApi } from "@/lib/api/endpoints";
import type { CampaignMetrics } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const levelDot: Record<RateLevel, "green" | "amber" | "red"> = {
  ok: "green",
  warn: "amber",
  danger: "red",
};

function RateNote({ level, text }: { level: RateLevel; text: string }) {
  return (
    <p
      className={cn(
        "flex items-center gap-1 text-[12px]",
        level === "danger" && "font-medium text-[var(--error)]",
        level === "warn" && "font-medium text-[var(--tertiary)]",
        level === "ok" && "text-[var(--on-surface-variant)]",
      )}
    >
      {level !== "ok" ? <AlertTriangle className="size-3" aria-hidden /> : null}
      {text}
    </p>
  );
}

function Muted({ children }: { children: React.ReactNode }) {
  return <p className="text-[12px] text-[var(--on-surface-variant)]">{children}</p>;
}

export function useCampaignMetrics(campaignId: number) {
  return useQuery({
    queryKey: ["campaign", campaignId, "metrics"],
    queryFn: () => campaignsApi.metrics(campaignId),
  });
}

export function CampaignOverview({ campaignId }: { campaignId: number }) {
  const metrics = useCampaignMetrics(campaignId);

  if (metrics.error) return <ErrorState error={metrics.error} onRetry={() => metrics.refetch()} />;
  if (!metrics.data) {
    return (
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4" role="status" aria-label="Loading metrics">
        {Array.from({ length: 8 }).map((_, index) => (
          <div key={index} className="h-24 animate-pulse rounded-lg bg-[var(--surface-container-high)]" />
        ))}
      </div>
    );
  }
  return <OverviewContent metrics={metrics.data} campaignId={campaignId} />;
}

function OverviewContent({ metrics, campaignId }: { metrics: CampaignMetrics; campaignId: number }) {
  const bounceLevel = rateLevel(metrics.bounce_rate, "bounce");
  const complaintLevel = rateLevel(metrics.complaint_rate, "complaint");
  const funnel = [
    { label: "Enrolled", value: metrics.enrolled },
    { label: "Awaiting approval", value: metrics.awaiting_approval },
    { label: "Scheduled", value: metrics.scheduled },
    { label: "Sent", value: metrics.sent },
    { label: "Replied", value: metrics.replies },
    { label: "Positive", value: metrics.positive_replies },
  ];
  const enrollmentStatuses = Object.entries(metrics.enrollments_by_status).filter(([, count]) => count > 0);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiCard label="Enrolled leads" value={metrics.enrolled} />
        <Link
          href={`/approvals?campaign_id=${campaignId}`}
          className="group rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)]"
          aria-label={`${metrics.awaiting_approval} emails awaiting approval – review in Approvals`}
        >
          <KpiCard
            label="Awaiting approval"
            value={metrics.awaiting_approval}
            dot={metrics.awaiting_approval > 0 ? "amber" : "none"}
            highlight={metrics.awaiting_approval > 0}
            className="h-full transition-colors group-hover:border-[var(--primary)]"
            trend={
              <p className="inline-flex items-center gap-1 text-[12px] font-medium text-[var(--primary)]">
                Review in Approvals <ArrowRight className="size-3" aria-hidden />
              </p>
            }
          />
        </Link>
        <KpiCard
          label="Scheduled"
          value={metrics.scheduled}
          trend={<Muted>Approved, waiting for the window</Muted>}
        />
        <KpiCard label="Sent" value={metrics.sent} />
        <KpiCard
          label="Replies"
          value={metrics.replies}
          trend={<Muted>{formatRate(metrics.reply_rate)} reply rate</Muted>}
        />
        <KpiCard
          label="Positive rate"
          value={formatRate(metrics.positive_rate)}
          dot={metrics.positive_replies > 0 ? "green" : "none"}
          trend={
            <Muted>
              {metrics.positive_replies} positive {metrics.positive_replies === 1 ? "reply" : "replies"}
            </Muted>
          }
        />
        <KpiCard
          label="Bounce rate"
          value={formatRate(metrics.bounce_rate)}
          dot={metrics.sent > 0 ? levelDot[bounceLevel] : "none"}
          className={cn(bounceLevel === "danger" && "border-[var(--error)]! bg-[var(--error-container)]/30")}
          trend={
            <RateNote
              level={bounceLevel}
              text={
                bounceLevel === "danger"
                  ? `Above the ${formatRate(RATE_THRESHOLDS.bounce.danger)} safety limit`
                  : bounceLevel === "warn"
                    ? `${metrics.bounced} bounced – check list quality`
                    : `${metrics.bounced} bounced`
              }
            />
          }
        />
        <KpiCard
          label="Complaint rate"
          value={formatRate(metrics.complaint_rate)}
          dot={metrics.sent > 0 ? levelDot[complaintLevel] : "none"}
          className={cn(complaintLevel === "danger" && "border-[var(--error)]! bg-[var(--error-container)]/30")}
          trend={
            <RateNote
              level={complaintLevel}
              text={
                complaintLevel === "danger"
                  ? `Above the ${formatRate(RATE_THRESHOLDS.complaint.danger)} safety limit`
                  : `${metrics.complained} spam ${metrics.complained === 1 ? "complaint" : "complaints"}`
              }
            />
          }
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <section
          aria-labelledby="campaign-funnel-title"
          className="rounded-lg border border-[var(--outline-variant)] bg-white p-4 shadow-sm"
        >
          <h3 id="campaign-funnel-title" className="text-[14px] font-semibold text-[var(--on-surface)]">
            Pipeline
          </h3>
          <p className="mb-3 text-[12px] text-[var(--on-surface-variant)]">
            Where this campaign&apos;s emails and leads are right now.
          </p>
          <div className="h-[240px] w-full" role="img" aria-label={funnel.map((row) => `${row.label}: ${row.value}`).join(", ")}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={funnel} layout="vertical" margin={{ top: 0, right: 40, bottom: 0, left: 0 }} barCategoryGap={8}>
                <CartesianGrid horizontal={false} stroke="var(--outline-variant)" strokeOpacity={0.5} />
                <XAxis type="number" hide allowDecimals={false} />
                <YAxis
                  type="category"
                  dataKey="label"
                  width={118}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fontSize: 12, fill: "var(--on-surface-variant)" }}
                />
                <Tooltip
                  cursor={{ fill: "var(--surface-container-low)" }}
                  contentStyle={{
                    borderRadius: 8,
                    border: "1px solid var(--outline-variant)",
                    fontSize: 12,
                  }}
                  formatter={(value) => [Number(value).toLocaleString(), "Count"]}
                />
                <Bar dataKey="value" fill="var(--primary)" radius={[0, 4, 4, 0]} maxBarSize={22} isAnimationActive={false}>
                  <LabelList dataKey="value" position="right" style={{ fontSize: 12, fill: "var(--on-surface)" }} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          {enrollmentStatuses.length > 0 ? (
            <div className="mt-3 border-t border-[var(--outline-variant)] pt-3">
              <p className="mb-2 text-[12px] font-semibold text-[var(--on-surface-variant)]">Enrollments by status</p>
              <ul className="flex flex-wrap gap-2">
                {enrollmentStatuses.map(([status, count]) => (
                  <li key={status} className="inline-flex items-center gap-1.5 text-[12px]">
                    <SequenceStatusBadge status={status} />
                    <span className="font-semibold text-[var(--on-surface)]">{count}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </section>

        <section
          aria-labelledby="campaign-steps-title"
          className="rounded-lg border border-[var(--outline-variant)] bg-white shadow-sm"
        >
          <div className="p-4 pb-2">
            <h3 id="campaign-steps-title" className="text-[14px] font-semibold text-[var(--on-surface)]">
              By step
            </h3>
            <p className="text-[12px] text-[var(--on-surface-variant)]">How each email in the sequence is doing.</p>
          </div>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Step</TableHead>
                  <TableHead className="text-right">Sent</TableHead>
                  <TableHead className="text-right">Replies</TableHead>
                  <TableHead className="text-right">Reply rate</TableHead>
                  <TableHead className="text-right">Awaiting approval</TableHead>
                  <TableHead className="text-right">Bounced</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {metrics.steps.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="py-6 text-center text-[13px] text-[var(--on-surface-variant)]">
                      No steps yet.
                    </TableCell>
                  </TableRow>
                ) : (
                  metrics.steps.map((step) => (
                    <TableRow key={step.step_number}>
                      <TableCell className="font-medium">Step {step.step_number}</TableCell>
                      <TableCell className="text-right tabular-nums">{step.sent}</TableCell>
                      <TableCell className="text-right tabular-nums">{step.replies}</TableCell>
                      <TableCell className="text-right tabular-nums">{formatRate(step.reply_rate)}</TableCell>
                      <TableCell className="text-right tabular-nums">
                        {step.awaiting_approval > 0 ? (
                          <Link
                            href={`/approvals?campaign_id=${campaignId}`}
                            className="font-semibold text-[var(--primary)] hover:underline"
                          >
                            {step.awaiting_approval}
                          </Link>
                        ) : (
                          0
                        )}
                      </TableCell>
                      <TableCell
                        className={cn(
                          "text-right tabular-nums",
                          step.sent > 0 && step.bounced / step.sent > RATE_THRESHOLDS.bounce.danger && "font-semibold text-[var(--error)]",
                        )}
                      >
                        {step.bounced}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </section>
      </div>
    </div>
  );
}
