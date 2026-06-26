"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/layout/page-header";
import { dashboardApi } from "@/lib/api/endpoints";

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-3xl font-semibold">{value}</p>
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: dashboardApi.summary,
  });

  const chartData = useMemo(() => {
    if (!data?.lead_status_counts) return [];
    return Object.entries(data.lead_status_counts).map(([status, count]) => ({
      status: status.replace(/_/g, " "),
      count,
    }));
  }, [data?.lead_status_counts]);

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Overview of leads, campaigns, and replies."
      />
      {isLoading ? <p className="text-sm text-muted-foreground">Loading…</p> : null}
      {error ? <p className="text-sm text-destructive">Failed to load dashboard.</p> : null}
      {data ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Total leads" value={data.total_leads} />
            <StatCard label="Qualified" value={data.qualified_leads} />
            <StatCard label="Contacted" value={data.contacted_leads} />
            <StatCard label="Replied" value={data.replied_leads} />
            <StatCard label="Active campaigns" value={data.active_campaigns} />
            <StatCard label="Positive replies" value={data.positive_replies} />
            <StatCard label="Pending classification" value={data.pending_replies} />
          </div>
          {chartData.length > 0 ? (
            <Card>
              <CardHeader>
                <CardTitle>Leads by status</CardTitle>
              </CardHeader>
              <CardContent className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="status" tick={{ fontSize: 12 }} />
                    <YAxis allowDecimals={false} />
                    <Tooltip />
                    <Bar dataKey="count" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
