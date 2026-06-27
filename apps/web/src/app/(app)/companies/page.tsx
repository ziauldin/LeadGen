"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Building2,
  CheckCircle2,
  ChevronRight,
  ExternalLink,
  Globe,
  MoreVertical,
  RefreshCw,
  Search,
  XCircle,
} from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { companiesApi } from "@/lib/api/endpoints";
import { useState } from "react";

const ENRICHMENT_CONFIG: Record<
  string,
  { label: string; icon: typeof CheckCircle2; color: string }
> = {
  pending: {
    label: "Pending",
    icon: RefreshCw,
    color: "var(--on-surface-variant)",
  },
  enriched: {
    label: "Enriched",
    icon: CheckCircle2,
    color: "var(--secondary)",
  },
  failed: {
    label: "Failed",
    icon: XCircle,
    color: "var(--error)",
  },
  skipped: {
    label: "Skipped",
    icon: XCircle,
    color: "var(--outline)",
  },
};

function EnrichmentBadge({ status }: { status: string }) {
  const config = ENRICHMENT_CONFIG[status] ?? ENRICHMENT_CONFIG.pending;
  const Icon = config.icon;
  return (
    <span
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[12px] font-semibold"
      style={{
        background: "var(--surface-container)",
        color: config.color,
      }}
    >
      <Icon className="w-3 h-3" />
      {config.label}
    </span>
  );
}

export default function CompaniesPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["companies"],
    queryFn: companiesApi.list,
  });

  const enrichMutation = useMutation({
    mutationFn: (id: number) => companiesApi.enrich(id, true),
    onSuccess: (company) => {
      queryClient.invalidateQueries({ queryKey: ["companies"] });
      toast.success(`Enriching ${company.name}…`);
    },
    onError: () => toast.error("Enrichment failed"),
  });

  const companies = data?.items ?? [];
  const filtered = search
    ? companies.filter(
        (c) =>
          c.name.toLowerCase().includes(search.toLowerCase()) ||
          c.domain?.toLowerCase().includes(search.toLowerCase()),
      )
    : companies;

  return (
    <div>
      <PageHeader
        title="Companies"
        description="Enriched company records linked to leads in your pipeline."
      />

      {/* Filter bar */}
      <div
        className="bg-white border rounded-lg shadow-sm p-4 flex items-center gap-4 mb-4"
        style={{ borderColor: "var(--outline-variant)" }}
      >
        <div className="relative flex-1 max-w-xs">
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4"
            style={{ color: "var(--on-surface-variant)" }}
          />
          <input
            type="text"
            placeholder="Search companies…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-1.5 border rounded text-[13px] outline-none"
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
        <p className="text-[13px] ml-auto" style={{ color: "var(--on-surface-variant)" }}>
          {filtered.length.toLocaleString()} companies
        </p>
      </div>

      {/* Table */}
      <div
        className="bg-white border rounded-lg shadow-sm overflow-hidden"
        style={{ borderColor: "var(--outline-variant)" }}
      >
        {isLoading ? (
          <div className="p-10 text-center">
            <div
              className="inline-block w-5 h-5 border-2 rounded-full animate-spin mb-3"
              style={{ borderColor: "var(--primary-container)", borderTopColor: "var(--primary)" }}
            />
            <p className="text-[13px]" style={{ color: "var(--on-surface-variant)" }}>
              Loading companies…
            </p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-16 text-center">
            <Building2 className="w-10 h-10 mx-auto mb-3" style={{ color: "var(--outline)" }} />
            <p className="text-[16px] font-semibold mb-1" style={{ color: "var(--on-surface)" }}>
              No companies found
            </p>
            <p className="text-[13px]" style={{ color: "var(--on-surface-variant)" }}>
              Companies are created automatically when you import or enrich leads.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse whitespace-nowrap">
              <thead>
                <tr className="border-b" style={{ background: "var(--surface)", borderColor: "var(--outline-variant)" }}>
                  <th className="py-3 px-5 text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--on-surface-variant)" }}>
                    Company
                  </th>
                  <th className="py-3 px-5 text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--on-surface-variant)" }}>
                    Domain
                  </th>
                  <th className="py-3 px-5 text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--on-surface-variant)" }}>
                    Industry
                  </th>
                  <th className="py-3 px-5 text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--on-surface-variant)" }}>
                    Enrichment
                  </th>
                  <th className="py-3 px-5 text-[11px] font-semibold uppercase tracking-wider text-right" style={{ color: "var(--on-surface-variant)" }}>
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((company) => (
                  <tr
                    key={company.id}
                    className="border-b group transition-colors"
                    style={{ borderColor: "var(--outline-variant)" }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surface-container-low)")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                  >
                    <td className="py-4 px-5">
                      <div className="flex items-center gap-3">
                        <div
                          className="w-8 h-8 rounded flex items-center justify-center shrink-0"
                          style={{ background: "var(--primary-fixed)" }}
                        >
                          <Building2 className="w-4 h-4" style={{ color: "var(--primary)" }} />
                        </div>
                        <Link
                          href={`/companies/${company.id}`}
                          className="text-[13px] font-semibold hover:underline"
                          style={{ color: "var(--on-surface)" }}
                        >
                          {company.name}
                        </Link>
                      </div>
                    </td>
                    <td className="py-4 px-5">
                      {company.website ? (
                        <a
                          href={company.website}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1.5 text-[13px]"
                          style={{ color: "var(--primary)" }}
                        >
                          <Globe className="w-3.5 h-3.5" />
                          {company.domain ?? company.website}
                          <ExternalLink className="w-3 h-3 opacity-60" />
                        </a>
                      ) : (
                        <span className="text-[13px]" style={{ color: "var(--outline)" }}>—</span>
                      )}
                    </td>
                    <td className="py-4 px-5">
                      <span className="text-[13px]" style={{ color: "var(--on-surface-variant)" }}>
                        {company.industry ?? "—"}
                      </span>
                    </td>
                    <td className="py-4 px-5">
                      <EnrichmentBadge status={company.enrichment_status} />
                    </td>
                    <td className="py-4 px-5 text-right">
                      <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => enrichMutation.mutate(company.id)}
                          disabled={enrichMutation.isPending}
                          className="flex items-center gap-1.5 px-3 py-1 border rounded text-[12px] font-medium transition-colors"
                          style={{
                            borderColor: "var(--outline-variant)",
                            color: "var(--on-surface)",
                          }}
                          onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surface-container-low)")}
                          onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                        >
                          <RefreshCw className="w-3.5 h-3.5" />
                          Enrich
                        </button>
                        <Link
                          href={`/companies/${company.id}`}
                          className="p-1.5 rounded transition-colors"
                          style={{ color: "var(--on-surface-variant)" }}
                        >
                          <ChevronRight className="w-4 h-4" />
                        </Link>
                        <button
                          className="p-1.5 rounded transition-colors"
                          style={{ color: "var(--on-surface-variant)" }}
                        >
                          <MoreVertical className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
