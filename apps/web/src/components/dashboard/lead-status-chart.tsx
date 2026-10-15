"use client";

import { useMemo } from "react";
import Link from "next/link";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Users } from "lucide-react";
import { ALL_LEAD_STATUSES, leadStatusLabel } from "@/components/leads/lead-status";

/**
 * Leads per status, in pipeline order. One series, so one hue: the bar length carries the
 * value and the axis label carries the status. A visually hidden table backs the chart.
 */
export function LeadStatusChart({ counts }: { counts: Record<string, number> }) {
  const data = useMemo(() => {
    const known = ALL_LEAD_STATUSES.map((status) => ({
      status,
      label: leadStatusLabel(status),
      count: counts[status] ?? 0,
    }));
    const extra = Object.keys(counts)
      .filter((status) => !ALL_LEAD_STATUSES.includes(status as never))
      .map((status) => ({ status, label: leadStatusLabel(status), count: counts[status] }));
    return [...known, ...extra];
  }, [counts]);
  const total = data.reduce((sum, row) => sum + row.count, 0);

  return (
    <section
      aria-labelledby="lead-status-chart-title"
      className="rounded-lg border border-[var(--outline-variant)] bg-white p-5 shadow-sm"
    >
      <div className="mb-4 flex items-start justify-between gap-2">
        <div>
          <h3
            id="lead-status-chart-title"
            className="text-[16px] font-semibold text-[var(--on-surface)]"
          >
            Leads by status
          </h3>
          <p className="mt-0.5 text-[13px] text-[var(--on-surface-variant)]">
            Where everyone in your pipeline is right now
          </p>
        </div>
        <Users className="size-5 text-[var(--on-surface-variant)]" aria-hidden />
      </div>

      {total === 0 ? (
        <div className="flex h-60 flex-col items-center justify-center gap-2 rounded-md bg-[var(--surface-container-low)] p-4 text-center">
          <p className="text-[13px] text-[var(--on-surface-variant)]">
            No leads yet.{" "}
            <Link href="/search" className="font-medium text-[var(--primary)] underline">
              Find leads
            </Link>{" "}
            or{" "}
            <Link href="/leads" className="font-medium text-[var(--primary)] underline">
              import a CSV
            </Link>
            .
          </p>
        </div>
      ) : (
        <>
          <div className="h-[300px]" aria-hidden>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data} layout="vertical" margin={{ left: 0, right: 16 }} barCategoryGap={4}>
                <CartesianGrid horizontal={false} stroke="var(--outline-variant)" strokeOpacity={0.6} />
                <XAxis
                  type="number"
                  allowDecimals={false}
                  tick={{ fontSize: 11, fill: "var(--on-surface-variant)" }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  type="category"
                  dataKey="label"
                  tick={{ fontSize: 11, fill: "var(--on-surface-variant)" }}
                  axisLine={false}
                  tickLine={false}
                  width={118}
                />
                <Tooltip
                  cursor={{ fill: "var(--surface-container-low)" }}
                  formatter={(value) => [Number(value).toLocaleString(), "Leads"]}
                  contentStyle={{
                    fontSize: 12,
                    borderRadius: 8,
                    border: "1px solid var(--outline-variant)",
                    color: "var(--on-surface)",
                  }}
                />
                <Bar dataKey="count" fill="var(--primary)" radius={[0, 4, 4, 0]} maxBarSize={18} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <table className="sr-only">
            <caption>Leads by status</caption>
            <thead>
              <tr>
                <th scope="col">Status</th>
                <th scope="col">Leads</th>
              </tr>
            </thead>
            <tbody>
              {data.map((row) => (
                <tr key={row.status}>
                  <th scope="row">{row.label}</th>
                  <td>{row.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
}
