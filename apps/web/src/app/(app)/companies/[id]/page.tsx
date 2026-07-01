"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  Building2,
  ExternalLink,
  Mail,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Globe
} from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { LoadingState } from "@/components/shared/loading-error";
import { companiesApi } from "@/lib/api/endpoints";

const ENRICHMENT_CONFIG: Record<
  string,
  { label: string; icon: typeof CheckCircle2; color: string }
> = {
  pending: {
    label: "Pending",
    icon: RefreshCw,
    color: "var(--on-surface-variant)",
  },
  in_progress: {
    label: "In Progress",
    icon: RefreshCw,
    color: "var(--primary)",
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

export default function CompanyDetailPage() {
  const params = useParams();
  const id = Number(params.id);
  const router = useRouter();

  const { data: company, isLoading } = useQuery({
    queryKey: ["companies", id],
    queryFn: () => companiesApi.get(id),
    enabled: Number.isFinite(id),
  });

  if (isLoading) return <LoadingState />;
  if (!company) return <p className="text-sm text-destructive">Company not found.</p>;

  return (
    <div>
      <PageHeader
        title={company.name}
        description={company.industry ?? "No industry recorded"}
        actions={
          <>
            <button
              onClick={() => router.back()}
              className="flex items-center gap-2 px-4 py-2 border rounded text-[13px] font-medium transition-colors"
              style={{
                background: "var(--surface-container-lowest)",
                borderColor: "var(--outline-variant)",
                color: "var(--on-surface)",
              }}
            >
              Back to Companies
            </button>
          </>
        }
      />

      <div className="grid gap-6 md:grid-cols-3">
        {/* Left: Overview details */}
        <div className="md:col-span-2 flex flex-col gap-6">
          {/* Card: Company Overview */}
          <div
            className="bg-white border rounded-lg p-6 shadow-sm"
            style={{ borderColor: "var(--outline-variant)" }}
          >
            <div className="flex items-center gap-2 mb-6">
              <Building2 className="w-5 h-5" style={{ color: "var(--primary)" }} />
              <h3
                className="text-[16px] font-semibold"
                style={{ color: "var(--on-surface)" }}
              >
                Company Overview
              </h3>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              {[
                { label: "Company Name", value: company.name },
                { label: "Domain", value: company.domain ?? "—" },
                {
                  label: "Industry",
                  value: company.industry ?? "—",
                },
                {
                  label: "Country",
                  value: company.country ?? "—",
                },
                {
                  label: "Size Estimate",
                  value: company.size_estimate ? `${company.size_estimate} employees` : "—",
                },
                {
                  label: "Created At",
                  value: new Date(company.created_at).toLocaleDateString(),
                },
              ].map((item) => (
                <div key={item.label} className="border-b pb-3" style={{ borderColor: "var(--outline-variant)" }}>
                  <p
                    className="text-[11px] font-semibold uppercase tracking-wider mb-1"
                    style={{ color: "var(--on-surface-variant)" }}
                  >
                    {item.label}
                  </p>
                  <p className="text-[14px]" style={{ color: "var(--on-surface)" }}>
                    {item.value}
                  </p>
                </div>
              ))}
            </div>

            {company.website && (
              <div className="mt-6 flex flex-wrap gap-4 items-center">
                <a
                  href={company.website}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 text-[13px] font-medium"
                  style={{ color: "var(--primary)" }}
                >
                  <Globe className="w-4 h-4" />
                  Visit Website
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              </div>
            )}
          </div>

          {/* Card: Email Contacts */}
          <div
            className="bg-white border rounded-lg p-6 shadow-sm"
            style={{ borderColor: "var(--outline-variant)" }}
          >
            <div className="flex items-center gap-2 mb-4">
              <Mail className="w-5 h-5" style={{ color: "var(--primary)" }} />
              <h3
                className="text-[16px] font-semibold"
                style={{ color: "var(--on-surface)" }}
              >
                Discovered Emails
              </h3>
            </div>
            
            {company.email_contacts && company.email_contacts.length > 0 ? (
              <div className="space-y-3">
                {company.email_contacts.map((contact) => (
                  <div key={contact.id} className="flex items-center justify-between p-3 rounded border" style={{ borderColor: "var(--outline-variant)", background: "var(--surface-container-lowest)" }}>
                    <div>
                      <p className="text-[14px] font-medium" style={{ color: "var(--on-surface)" }}>{contact.email}</p>
                      <p className="text-[12px] mt-0.5" style={{ color: "var(--on-surface-variant)" }}>
                        Source: {contact.source_provider || "Unknown"}
                      </p>
                    </div>
                    {contact.opted_out && (
                      <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full" style={{ background: "var(--error-container)", color: "var(--on-error-container)" }}>Opted Out</span>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[13px]" style={{ color: "var(--on-surface-variant)" }}>
                No emails discovered yet for this company.
              </p>
            )}
          </div>
        </div>

        {/* Right: Enrichment Status */}
        <div className="flex flex-col gap-6">
          <div
            className="bg-white border rounded-lg p-6 shadow-sm"
            style={{ borderColor: "var(--outline-variant)" }}
          >
            <div className="flex items-center gap-2 mb-4">
              <RefreshCw className="w-5 h-5" style={{ color: "var(--primary)" }} />
              <h3
                className="text-[16px] font-semibold"
                style={{ color: "var(--on-surface)" }}
              >
                Enrichment Status
              </h3>
            </div>

            <div className="space-y-4">
              <div>
                <p
                  className="text-[11px] font-semibold uppercase tracking-wider mb-2"
                  style={{ color: "var(--on-surface-variant)" }}
                >
                  Current Status
                </p>
                <EnrichmentBadge status={company.enrichment_status} />
              </div>
              
              <div>
                <p
                  className="text-[11px] font-semibold uppercase tracking-wider mb-1.5"
                  style={{ color: "var(--on-surface-variant)" }}
                >
                  Enrichment Message
                </p>
                <div
                  className="p-3 rounded text-[13px] leading-[20px]"
                  style={{
                    background: "var(--surface-container-low)",
                    color: "var(--on-surface)",
                  }}
                >
                  {company.enrichment_message ?? "No messages recorded."}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
