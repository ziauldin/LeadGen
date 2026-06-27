"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { PageHeader } from "@/components/layout/page-header";
import { KpiCard } from "@/components/shared/kpi-card";
import { dashboardApi } from "@/lib/api/endpoints";
import {
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  Globe,
  Mail,
  Send,
  TrendingUp,
  Users,
} from "lucide-react";

const STATUS_COLORS: Record<string, string> = {
  new: "#c7c4d8",
  enriched: "#ffb95f",
  qualified: "#c3c0ff",
  ready_for_outreach: "#4edea3",
  contacted: "#4f46e5",
  replied: "#10b981",
  meeting_booked: "#006c49",
  client: "#002113",
  disqualified: "#ffdad6",
  opted_out: "#ba1a1a",
};

export default function DashboardPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: dashboardApi.summary,
  });

  const chartData = useMemo(() => {
    if (!data?.lead_status_counts) return [];
    return Object.entries(data.lead_status_counts).map(([status, count]) => ({
      status: status.replace(/_/g, " "),
      count: count as number,
      fill: STATUS_COLORS[status] ?? "#c7c4d8",
    }));
  }, [data?.lead_status_counts]);

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Real-time overview of your lead pipeline, campaigns, and outreach compliance."
        actions={
          <div
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-[13px] font-medium"
            style={{
              background: "var(--secondary-container)",
              color: "var(--on-secondary-container)",
            }}
          >
            <CheckCircle2 className="w-4 h-4" />
            All systems compliant
          </div>
        }
      />

      {isLoading ? (
        <div className="grid gap-4 grid-cols-2 md:grid-cols-4 mb-6">
          {Array.from({ length: 8 }).map((_, i) => (
            <div
              key={i}
              className="bg-white border rounded-lg p-4 h-24 animate-pulse"
              style={{ borderColor: "var(--outline-variant)" }}
            />
          ))}
        </div>
      ) : error ? (
        <div
          className="flex items-center gap-2 p-4 rounded-lg border mb-6 text-[14px]"
          style={{
            background: "var(--error-container)",
            borderColor: "var(--error)",
            color: "var(--on-error-container)",
          }}
        >
          <AlertTriangle className="w-4 h-4 shrink-0" />
          Failed to load dashboard data. Check that the backend is running.
        </div>
      ) : data ? (
        <>
          {/* KPI Grid */}
          <div className="grid gap-4 grid-cols-2 md:grid-cols-4 mb-6">
            <KpiCard
              label="Total Leads"
              value={data.total_leads}
              trend={
                <div className="flex items-center gap-1">
                  <TrendingUp className="w-3 h-3" style={{ color: "var(--secondary)" }} />
                  <span className="text-[11px]" style={{ color: "var(--secondary)" }}>
                    Pipeline active
                  </span>
                </div>
              }
            />
            <KpiCard
              label="Qualified"
              value={data.qualified_leads}
              dot="blue"
              highlight
            />
            <KpiCard
              label="Contacted"
              value={data.contacted_leads}
            />
            <KpiCard
              label="Replied"
              value={data.replied_leads}
              dot="green"
            />
            <KpiCard
              label="Active Campaigns"
              value={data.active_campaigns}
              dot="blue"
            />
            <KpiCard
              label="Positive Replies"
              value={data.positive_replies}
              dot="green"
              highlight
            />
            <KpiCard
              label="Pending Classification"
              value={data.pending_replies}
              dot={data.pending_replies > 0 ? "amber" : "none"}
            />
            <KpiCard
              label="Suppressed Contacts"
              value={(data as unknown as Record<string, number>).suppressed_contacts ?? 0}
            />
          </div>

          {/* Charts grid */}
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 mb-6">
            {/* Lead status pipeline — 3 cols */}
            <div
              className="lg:col-span-3 bg-white border rounded-lg p-5 shadow-sm"
              style={{ borderColor: "var(--outline-variant)" }}
            >
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3
                    className="text-[16px] font-semibold"
                    style={{ color: "var(--on-surface)" }}
                  >
                    Lead Pipeline by Status
                  </h3>
                  <p className="text-[13px] mt-0.5" style={{ color: "var(--on-surface-variant)" }}>
                    Distribution across all workflow stages
                  </p>
                </div>
                <Users className="w-5 h-5" style={{ color: "var(--on-surface-variant)" }} />
              </div>
              {chartData.length > 0 ? (
                <div style={{ height: 240 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData} layout="vertical" margin={{ left: 16 }}>
                      <CartesianGrid
                        strokeDasharray="3 3"
                        horizontal={false}
                        stroke="var(--outline-variant)"
                      />
                      <XAxis
                        type="number"
                        allowDecimals={false}
                        tick={{ fontSize: 11, fill: "var(--on-surface-variant)" }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <YAxis
                        type="category"
                        dataKey="status"
                        tick={{ fontSize: 11, fill: "var(--on-surface-variant)" }}
                        axisLine={false}
                        tickLine={false}
                        width={110}
                      />
                      <Tooltip
                        contentStyle={{
                          fontSize: 12,
                          borderRadius: 8,
                          border: "1px solid var(--outline-variant)",
                        }}
                      />
                      <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                        {chartData.map((entry, index) => (
                          <Cell key={index} fill={entry.fill} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div
                  className="h-60 flex flex-col items-center justify-center gap-2 rounded"
                  style={{ background: "var(--surface-container-low)" }}
                >
                  <Users className="w-8 h-8" style={{ color: "var(--outline)" }} />
                  <p className="text-[13px]" style={{ color: "var(--on-surface-variant)" }}>
                    No leads yet. Import a CSV or run a search to get started.
                  </p>
                </div>
              )}
            </div>

            {/* Right stats — 2 cols */}
            <div className="lg:col-span-2 flex flex-col gap-4">
              {/* Reply Classification */}
              <div
                className="bg-white border rounded-lg p-5 shadow-sm flex-1"
                style={{ borderColor: "var(--outline-variant)" }}
              >
                <div className="flex items-center justify-between mb-3">
                  <h3
                    className="text-[15px] font-semibold"
                    style={{ color: "var(--on-surface)" }}
                  >
                    Reply Classification
                  </h3>
                  <Mail className="w-4 h-4" style={{ color: "var(--on-surface-variant)" }} />
                </div>
                <div className="space-y-2">
                  {[
                    {
                      label: "Positive",
                      count: data.positive_replies,
                      color: "var(--secondary)",
                    },
                    {
                      label: "Pending",
                      count: data.pending_replies,
                      color: "var(--primary)",
                    },
                    {
                      label: "Total Replies",
                      count: data.replied_leads,
                      color: "var(--outline)",
                    },
                  ].map((item) => (
                    <div key={item.label} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span
                          className="w-2.5 h-2.5 rounded-full"
                          style={{ background: item.color }}
                        />
                        <span
                          className="text-[13px]"
                          style={{ color: "var(--on-surface-variant)" }}
                        >
                          {item.label}
                        </span>
                      </div>
                      <span
                        className="text-[14px] font-semibold"
                        style={{ color: "var(--on-surface)" }}
                      >
                        {item.count.toLocaleString()}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Active Campaigns */}
              <div
                className="bg-white border rounded-lg p-5 shadow-sm flex-1"
                style={{ borderColor: "var(--outline-variant)" }}
              >
                <div className="flex items-center justify-between mb-3">
                  <h3
                    className="text-[15px] font-semibold"
                    style={{ color: "var(--on-surface)" }}
                  >
                    Campaigns
                  </h3>
                  <Send className="w-4 h-4" style={{ color: "var(--on-surface-variant)" }} />
                </div>
                <div className="space-y-2">
                  {[
                    {
                      label: "Active",
                      count: data.active_campaigns,
                      color: "var(--primary)",
                    },
                    {
                      label: "Leads contacted",
                      count: data.contacted_leads,
                      color: "var(--secondary)",
                    },
                  ].map((item) => (
                    <div key={item.label} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span
                          className="w-2.5 h-2.5 rounded-full"
                          style={{ background: item.color }}
                        />
                        <span
                          className="text-[13px]"
                          style={{ color: "var(--on-surface-variant)" }}
                        >
                          {item.label}
                        </span>
                      </div>
                      <span
                        className="text-[14px] font-semibold"
                        style={{ color: "var(--on-surface)" }}
                      >
                        {item.count.toLocaleString()}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Compliance Note */}
          <div
            className="flex items-start gap-4 p-4 rounded-lg border"
            style={{
              background: "var(--surface-container-low)",
              borderColor: "var(--outline-variant)",
            }}
          >
            <Globe className="w-5 h-5 shrink-0 mt-0.5" style={{ color: "var(--primary)" }} />
            <div>
              <p
                className="text-[13px] font-semibold mb-0.5"
                style={{ color: "var(--on-surface)" }}
              >
                Compliance Mandate Active
              </p>
              <p className="text-[13px]" style={{ color: "var(--on-surface-variant)" }}>
                All outreach requires manual approval, source URL, compliance notes, and suppression
                checks. One-click mass sending is disabled by design. See{" "}
                <a
                  href="/settings"
                  className="font-medium underline"
                  style={{ color: "var(--primary)" }}
                >
                  Settings → Compliance
                </a>{" "}
                for the full policy.
              </p>
            </div>
            <a
              href="/settings"
              className="ml-auto shrink-0 flex items-center gap-1 text-[12px] font-semibold"
              style={{ color: "var(--primary)" }}
            >
              View policy
              <ArrowUpRight className="w-3.5 h-3.5" />
            </a>
          </div>
        </>
      ) : null}
    </div>
  );
}
