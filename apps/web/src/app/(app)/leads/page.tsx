"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Download,
  ExternalLink,
  Filter,
  MoreVertical,
  Pencil,
  Search,
  Upload,
  UserPlus,
  XCircle,
} from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { StatusBadge } from "@/components/shared/status-badge";
import { ScoreBadge } from "@/components/shared/score-badge";
import { KpiCard } from "@/components/shared/kpi-card";
import { leadsApi } from "@/lib/api/endpoints";
import type { Lead } from "@/lib/api/types";

function getInitials(name: string) {
  return name
    .split(" ")
    .slice(0, 2)
    .map((p) => p[0])
    .join("")
    .toUpperCase();
}

function isOutreachReady(lead: Lead) {
  return (
    !!lead.primary_email &&
    lead.status !== "opted_out" &&
    lead.status !== "disqualified" &&
    !!lead.source_url &&
    !!lead.compliance_source_note
  );
}

const STATUS_FILTER_OPTIONS = [
  "All",
  "new",
  "enriched",
  "qualified",
  "ready_for_outreach",
  "contacted",
  "replied",
  "disqualified",
  "opted_out",
];

export default function LeadsPage() {
  const searchParams = useSearchParams();
  const nicheId = searchParams.get("niche_id");
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [importing, setImporting] = useState(false);
  const [statusFilter, setStatusFilter] = useState("All");
  const [search, setSearch] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["leads", nicheId, statusFilter],
    queryFn: () =>
      leadsApi.list(
        Object.assign(
          {},
          nicheId ? { niche_id: Number(nicheId) } : {},
          statusFilter !== "All" ? { status: statusFilter } : {},
        ),
      ),
  });

  const recalcMutation = useMutation({
    mutationFn: () => leadsApi.recalculateScores(nicheId ? Number(nicheId) : undefined),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      toast.success(`Updated scores for ${result.updated} leads`);
    },
  });

  async function handleImport(file: File) {
    setImporting(true);
    try {
      const result = await leadsApi.importCsv(file);
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      toast.success(`Imported ${result.created} leads (${result.skipped} skipped)`);
      if (result.errors.length > 0) {
        toast.warning(`${result.errors.length} rows had errors`);
      }
    } catch {
      toast.error("CSV import failed");
    } finally {
      setImporting(false);
    }
  }

  const leads = data?.items ?? [];
  const filtered = search
    ? leads.filter(
        (l) =>
          l.full_name.toLowerCase().includes(search.toLowerCase()) ||
          l.company?.name?.toLowerCase().includes(search.toLowerCase()),
      )
    : leads;

  const totalLeads = data?.total ?? 0;
  const enriched = leads.filter((l) => l.status !== "new").length;
  const qualified = leads.filter((l) => l.score >= 75).length;
  const outreachReady = leads.filter(isOutreachReady).length;

  return (
    <div>
      <PageHeader
        title="Leads"
        description="Manage and segment your raw and enriched contacts."
        actions={
          <>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void handleImport(file);
                e.target.value = "";
              }}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={importing}
              className="flex items-center gap-2 px-4 py-2 border rounded text-[13px] font-medium transition-colors active:scale-95 shadow-sm"
              style={{
                background: "var(--surface-container-lowest)",
                borderColor: "var(--outline-variant)",
                color: "var(--on-surface)",
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.background = "var(--surface-container-low)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = "var(--surface-container-lowest)")
              }
            >
              <Upload className="w-4 h-4" />
              {importing ? "Importing…" : "Import CSV"}
            </button>
            <button
              onClick={() => void leadsApi.exportCsv(nicheId ? Number(nicheId) : undefined)}
              className="flex items-center gap-2 px-4 py-2 border rounded text-[13px] font-medium transition-colors active:scale-95 shadow-sm"
              style={{
                background: "var(--surface-container-lowest)",
                borderColor: "var(--outline-variant)",
                color: "var(--on-surface)",
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.background = "var(--surface-container-low)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = "var(--surface-container-lowest)")
              }
            >
              <Download className="w-4 h-4" />
              Export CSV
            </button>
            <button
              onClick={() => recalcMutation.mutate()}
              disabled={recalcMutation.isPending}
              className="flex items-center gap-2 px-5 py-2 rounded text-[13px] font-medium transition-colors active:scale-95 shadow-sm text-white"
              style={{ background: "var(--primary)" }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.background = "var(--surface-tint)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = "var(--primary)")
              }
            >
              <UserPlus className="w-4 h-4" />
              Recalculate Scores
            </button>
          </>
        }
      />

      {/* Stats Bento */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <KpiCard
          label="Total Leads"
          value={totalLeads}
          trend={
            <div className="flex items-center gap-1 mt-1">
              <span className="text-[11px]" style={{ color: "var(--on-surface-variant)" }}>
                In pipeline
              </span>
            </div>
          }
        />
        <div
          className="bg-white border rounded-lg p-4 shadow-sm"
          style={{ borderColor: "var(--outline-variant)" }}
        >
          <p className="text-[13px] font-medium" style={{ color: "var(--on-surface-variant)" }}>
            Enriched
          </p>
          <p
            className="text-[20px] font-semibold leading-[28px] mt-2"
            style={{ color: "var(--on-surface)" }}
          >
            {enriched.toLocaleString()}
          </p>
          {totalLeads > 0 && (
            <>
              <div
                className="w-full h-1.5 rounded-full overflow-hidden mt-2"
                style={{ background: "var(--surface-container-high)" }}
              >
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${Math.round((enriched / totalLeads) * 100)}%`,
                    background: "var(--primary)",
                  }}
                />
              </div>
              <p
                className="text-[11px] text-right mt-1"
                style={{ color: "var(--on-surface-variant)" }}
              >
                {Math.round((enriched / totalLeads) * 100)}% match rate
              </p>
            </>
          )}
        </div>
        <KpiCard
          label="Qualified"
          value={qualified}
          trend={
            <p className="text-[11px] mt-1" style={{ color: "var(--on-surface-variant)" }}>
              Score ≥ 75
            </p>
          }
        />
        <KpiCard
          label="Outreach Ready"
          value={outreachReady}
          dot="green"
          trend={
            <div className="flex items-center gap-1 mt-1">
              <CheckCircle2 className="w-3 h-3" style={{ color: "var(--secondary)" }} />
              <span className="text-[11px]" style={{ color: "var(--on-surface-variant)" }}>
                Emails verified
              </span>
            </div>
          }
        />
      </div>

      {/* Filter Bar */}
      <div
        className="bg-white border rounded-lg shadow-sm p-4 flex flex-wrap items-center gap-4 mb-4"
        style={{ borderColor: "var(--outline-variant)" }}
      >
        <div
          className="flex items-center gap-2 pr-4 border-r"
          style={{ borderColor: "var(--outline-variant)", color: "var(--on-surface-variant)" }}
        >
          <Filter className="w-4 h-4" />
          <span className="text-[13px]">Filters</span>
        </div>

        {/* Status dropdown */}
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="flex items-center gap-2 px-3 py-1.5 border rounded text-[13px] cursor-pointer outline-none"
          style={{
            borderColor: "var(--outline-variant)",
            color: "var(--on-surface)",
            background: "var(--surface)",
          }}
        >
          {STATUS_FILTER_OPTIONS.map((s) => (
            <option key={s} value={s}>
              Status: {s === "All" ? "All" : s.replace(/_/g, " ")}
            </option>
          ))}
        </select>

        {/* Search */}
        <div className="relative ml-auto">
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4"
            style={{ color: "var(--on-surface-variant)" }}
          />
          <input
            type="text"
            placeholder="Search leads…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 pr-4 py-1.5 border rounded text-[13px] outline-none w-64"
            style={{
              borderColor: "var(--outline-variant)",
              background: "var(--surface)",
              color: "var(--on-surface)",
            }}
            onFocus={(e) => {
              e.target.style.borderColor = "var(--primary)";
              e.target.style.boxShadow = "0 0 0 1px var(--primary)";
            }}
            onBlur={(e) => {
              e.target.style.borderColor = "var(--outline-variant)";
              e.target.style.boxShadow = "none";
            }}
          />
        </div>
      </div>

      {/* Table */}
      <div
        className="bg-white border rounded-lg shadow-sm overflow-hidden"
        style={{ borderColor: "var(--outline-variant)" }}
      >
        {isLoading ? (
          <div className="p-8 text-center">
            <div
              className="inline-block w-5 h-5 border-2 rounded-full animate-spin"
              style={{
                borderColor: "var(--primary-container)",
                borderTopColor: "var(--primary)",
              }}
            />
            <p className="text-[13px] mt-3" style={{ color: "var(--on-surface-variant)" }}>
              Loading leads…
            </p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-16 text-center">
            <UserPlus className="w-10 h-10 mx-auto mb-3" style={{ color: "var(--outline)" }} />
            <p
              className="text-[16px] font-semibold mb-1"
              style={{ color: "var(--on-surface)" }}
            >
              No leads found
            </p>
            <p className="text-[13px]" style={{ color: "var(--on-surface-variant)" }}>
              Import a CSV or run a search to populate your pipeline.
            </p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse whitespace-nowrap">
                <thead>
                  <tr
                    className="border-b"
                    style={{
                      background: "var(--surface)",
                      borderColor: "var(--outline-variant)",
                    }}
                  >
                    <th className="py-3 px-4 w-10">
                      <input type="checkbox" className="rounded" />
                    </th>
                    <th
                      className="py-3 px-4 text-[11px] font-semibold uppercase tracking-wider"
                      style={{ color: "var(--on-surface-variant)" }}
                    >
                      Lead
                    </th>
                    <th
                      className="py-3 px-4 text-[11px] font-semibold uppercase tracking-wider"
                      style={{ color: "var(--on-surface-variant)" }}
                    >
                      Company &amp; Niche
                    </th>
                    <th
                      className="py-3 px-4 text-[11px] font-semibold uppercase tracking-wider"
                      style={{ color: "var(--on-surface-variant)" }}
                    >
                      Score
                    </th>
                    <th
                      className="py-3 px-4 text-[11px] font-semibold uppercase tracking-wider"
                      style={{ color: "var(--on-surface-variant)" }}
                    >
                      Status
                    </th>
                    <th
                      className="py-3 px-4 text-[11px] font-semibold uppercase tracking-wider text-center"
                      style={{ color: "var(--on-surface-variant)" }}
                    >
                      Ready
                    </th>
                    <th
                      className="py-3 px-4 text-[11px] font-semibold uppercase tracking-wider text-right"
                      style={{ color: "var(--on-surface-variant)" }}
                    >
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((lead) => {
                    const ready = isOutreachReady(lead);
                    return (
                      <tr
                        key={lead.id}
                        className="border-b group transition-colors"
                        style={{ borderColor: "var(--outline-variant)" }}
                        onMouseEnter={(e) =>
                          (e.currentTarget.style.background = "var(--surface-container-low)")
                        }
                        onMouseLeave={(e) =>
                          (e.currentTarget.style.background = "transparent")
                        }
                      >
                        {/* Checkbox */}
                        <td className="py-4 px-4">
                          <input type="checkbox" className="rounded" />
                        </td>
                        {/* Lead name + role */}
                        <td className="py-4 px-4">
                          <div className="flex items-center gap-3">
                            <div
                              className="w-9 h-9 rounded-full flex items-center justify-center text-[11px] font-bold text-white shrink-0"
                              style={{ background: "var(--primary)" }}
                            >
                              {getInitials(lead.full_name)}
                            </div>
                            <div>
                              <Link
                                href={`/leads/${lead.id}`}
                                className="text-[13px] font-semibold transition-colors hover:underline"
                                style={{ color: "var(--on-surface)" }}
                              >
                                {lead.full_name}
                              </Link>
                              <div
                                className="text-[12px]"
                                style={{ color: "var(--on-surface-variant)" }}
                              >
                                {lead.job_title ?? "—"}
                              </div>
                            </div>
                          </div>
                        </td>
                        {/* Company + industry */}
                        <td className="py-4 px-4">
                          <div
                            className="text-[13px] font-medium"
                            style={{ color: "var(--on-surface)" }}
                          >
                            {lead.company?.name ?? "—"}
                          </div>
                          <div
                            className="text-[12px]"
                            style={{ color: "var(--on-surface-variant)" }}
                          >
                            {lead.primary_email ?? "No email"}
                          </div>
                        </td>
                        {/* Score */}
                        <td className="py-4 px-4">
                          <ScoreBadge score={lead.score} />
                        </td>
                        {/* Status */}
                        <td className="py-4 px-4">
                          <StatusBadge status={lead.status} />
                        </td>
                        {/* Readiness */}
                        <td className="py-4 px-4 text-center">
                          {ready ? (
                            <CheckCircle2
                              className="w-5 h-5 mx-auto"
                              style={{ color: "var(--secondary)" }}
                            />
                          ) : (
                            <XCircle
                              className="w-5 h-5 mx-auto"
                              style={{ color: "var(--error)" }}
                            />
                          )}
                        </td>
                        {/* Actions */}
                        <td className="py-4 px-4 text-right">
                          <div className="flex items-center justify-end gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                            {lead.source_url && (
                              <a
                                href={lead.source_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="p-1.5 rounded transition-colors"
                                title="Source URL"
                                style={{ color: "var(--on-surface-variant)" }}
                                onMouseEnter={(e) =>
                                  (e.currentTarget.style.color = "var(--primary)")
                                }
                                onMouseLeave={(e) =>
                                  (e.currentTarget.style.color = "var(--on-surface-variant)")
                                }
                              >
                                <ExternalLink className="w-4 h-4" />
                              </a>
                            )}
                            <Link
                              href={`/leads/${lead.id}`}
                              className="p-1.5 rounded transition-colors"
                              title="Edit"
                              style={{ color: "var(--on-surface-variant)" }}
                              onMouseEnter={(e) =>
                                (e.currentTarget.style.color = "var(--primary)")
                              }
                              onMouseLeave={(e) =>
                                (e.currentTarget.style.color = "var(--on-surface-variant)")
                              }
                            >
                              <Pencil className="w-4 h-4" />
                            </Link>
                            <button
                              className="p-1.5 rounded transition-colors"
                              title="More"
                              style={{ color: "var(--on-surface-variant)" }}
                              onMouseEnter={(e) =>
                                (e.currentTarget.style.color = "var(--error)")
                              }
                              onMouseLeave={(e) =>
                                (e.currentTarget.style.color = "var(--on-surface-variant)")
                              }
                            >
                              <MoreVertical className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {/* Pagination */}
            <div
              className="border-t px-5 py-3 flex items-center justify-between"
              style={{
                borderColor: "var(--outline-variant)",
                background: "var(--surface)",
              }}
            >
              <p className="text-[13px]" style={{ color: "var(--on-surface-variant)" }}>
                Showing{" "}
                <span className="font-medium" style={{ color: "var(--on-surface)" }}>
                  {filtered.length}
                </span>{" "}
                of{" "}
                <span className="font-medium" style={{ color: "var(--on-surface)" }}>
                  {totalLeads.toLocaleString()}
                </span>{" "}
                results
              </p>
              <div className="flex items-center gap-2">
                <button
                  disabled
                  className="flex items-center gap-1 px-3 py-1 border rounded text-[12px] font-medium disabled:opacity-50"
                  style={{
                    borderColor: "var(--outline-variant)",
                    color: "var(--on-surface-variant)",
                  }}
                >
                  <ChevronLeft className="w-4 h-4" />
                  Previous
                </button>
                <button
                  className="flex items-center gap-1 px-3 py-1 border rounded text-[12px] font-medium"
                  style={{
                    borderColor: "var(--outline-variant)",
                    color: "var(--on-surface)",
                  }}
                >
                  Next
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
