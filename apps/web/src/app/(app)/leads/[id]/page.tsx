"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import {
  AlertTriangle,
  Building2,
  CheckCircle2,
  ExternalLink,
  FileText,
  Mail,
  Shield,
  User,
  XCircle,
} from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { StatusBadge } from "@/components/shared/status-badge";
import { ScoreBadge } from "@/components/shared/score-badge";
import { LoadingState } from "@/components/shared/loading-error";
import { leadsApi } from "@/lib/api/endpoints";

export default function LeadDetailPage() {
  const params = useParams();
  const id = Number(params.id);
  const router = useRouter();

  const { data: lead, isLoading } = useQuery({
    queryKey: ["leads", id],
    queryFn: () => leadsApi.get(id),
    enabled: Number.isFinite(id),
  });

  const { data: readiness } = useQuery({
    queryKey: ["leads", id, "outreach-readiness"],
    queryFn: () => leadsApi.outreachReadiness(id),
    enabled: Number.isFinite(id),
  });

  if (isLoading) return <LoadingState />;
  if (!lead) return <p className="text-sm text-destructive">Lead not found.</p>;

  const outreachReady = readiness?.ready ?? false;
  const suppressed = readiness?.issues.some((issue) =>
    issue.toLowerCase().includes("suppression")
  );

  const checks = [
    { label: "Email contact on file", passed: Boolean(lead.primary_email) },
    { label: "Not opted out", passed: lead.status !== "opted_out" },
    { label: "Source URL recorded", passed: Boolean(lead.source_url) },
    { label: "Compliance / source note", passed: Boolean(lead.compliance_source_note) },
    { label: "Not on suppression list", passed: !suppressed },
  ];

  return (
    <div>
      <PageHeader
        title={lead.full_name}
        description={lead.job_title ?? "No title recorded"}
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
              Back to Leads
            </button>
            <Link
              href={`/email-studio?lead_id=${lead.id}`}
              className="flex items-center gap-2 px-5 py-2 rounded text-[13px] font-medium text-white transition-colors active:scale-95 shadow-sm"
              style={{
                background: outreachReady ? "var(--primary)" : "var(--outline)",
                pointerEvents: outreachReady ? "auto" : "none",
                opacity: outreachReady ? 1 : 0.6,
              }}
            >
              <Mail className="w-4 h-4" />
              Open Email Studio
            </Link>
          </>
        }
      />

      <div className="grid gap-6 md:grid-cols-3">
        {/* Left: Overview details */}
        <div className="md:col-span-2 flex flex-col gap-6">
          {/* Card: Lead Overview */}
          <div
            className="bg-white border rounded-lg p-6 shadow-sm"
            style={{ borderColor: "var(--outline-variant)" }}
          >
            <div className="flex items-center gap-2 mb-6">
              <User className="w-5 h-5" style={{ color: "var(--primary)" }} />
              <h3
                className="text-[16px] font-semibold"
                style={{ color: "var(--on-surface)" }}
              >
                Lead Overview
              </h3>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              {[
                { label: "Full Name", value: lead.full_name },
                { label: "Job Title", value: lead.job_title ?? "—" },
                {
                  label: "Email Address",
                  value: lead.primary_email ?? "No email",
                },
                {
                  label: "Source Provider",
                  value: lead.source_provider ?? "—",
                },
                {
                  label: "Database ID",
                  value: lead.id,
                },
                {
                  label: "Created At",
                  value: new Date(lead.created_at).toLocaleDateString(),
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

            <div className="mt-6 flex flex-wrap gap-4 items-center">
              <div className="flex items-center gap-2">
                <span className="text-[13px]" style={{ color: "var(--on-surface-variant)" }}>Status:</span>
                <StatusBadge status={lead.status} />
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[13px]" style={{ color: "var(--on-surface-variant)" }}>Calculated Score:</span>
                <ScoreBadge score={lead.score} />
              </div>
            </div>
          </div>

          {/* Card: Associated Company */}
          <div
            className="bg-white border rounded-lg p-6 shadow-sm"
            style={{ borderColor: "var(--outline-variant)" }}
          >
            <div className="flex items-center gap-2 mb-4">
              <Building2 className="w-5 h-5" style={{ color: "var(--primary)" }} />
              <h3
                className="text-[16px] font-semibold"
                style={{ color: "var(--on-surface)" }}
              >
                Company Details
              </h3>
            </div>

            {lead.company ? (
              <div className="space-y-4">
                <div className="flex items-center gap-3">
                  <div
                    className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
                    style={{ background: "var(--primary-fixed)" }}
                  >
                    <Building2 className="w-5 h-5" style={{ color: "var(--primary)" }} />
                  </div>
                  <div>
                    <h4
                      className="text-[15px] font-semibold"
                      style={{ color: "var(--on-surface)" }}
                    >
                      {lead.company.name}
                    </h4>
                    {lead.company.website && (
                      <a
                        href={lead.company.website}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-[13px] mt-0.5"
                        style={{ color: "var(--primary)" }}
                      >
                        {lead.company.domain ?? lead.company.website}
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    )}
                  </div>
                </div>

                <div className="pt-4 border-t" style={{ borderColor: "var(--outline-variant)" }}>
                  <Link
                    href={`/companies`}
                    className="text-[13px] font-medium"
                    style={{ color: "var(--primary)" }}
                  >
                    View in Company Directory →
                  </Link>
                </div>
              </div>
            ) : (
              <p className="text-[13px]" style={{ color: "var(--on-surface-variant)" }}>
                No associated company information.
              </p>
            )}
          </div>
        </div>

        {/* Right: Compliance Status */}
        <div className="flex flex-col gap-6">
          {/* Card: Outreach Readiness Checklist */}
          <div
            className="bg-white border rounded-lg p-6 shadow-sm"
            style={{ borderColor: "var(--outline-variant)" }}
          >
            <div className="flex items-center gap-2 mb-4">
              <Shield className="w-5 h-5" style={{ color: "var(--primary)" }} />
              <h3
                className="text-[16px] font-semibold"
                style={{ color: "var(--on-surface)" }}
              >
                Outreach Readiness
              </h3>
            </div>

            <div className="space-y-3 mb-6">
              {checks.map((check) => (
                <div key={check.label} className="flex items-center gap-3">
                  {check.passed ? (
                    <CheckCircle2 className="w-5 h-5 shrink-0" style={{ color: "var(--secondary)" }} />
                  ) : (
                    <XCircle className="w-5 h-5 shrink-0" style={{ color: "var(--error)" }} />
                  )}
                  <span
                    className="text-[13px] font-medium"
                    style={{ color: check.passed ? "var(--on-surface)" : "var(--error)" }}
                  >
                    {check.label}
                  </span>
                </div>
              ))}
            </div>

            {readiness && readiness.issues.length > 0 && (
              <div
                className="p-3.5 rounded-lg border mb-4 flex items-start gap-2.5"
                style={{
                  background: "var(--error-container)",
                  borderColor: "var(--error)",
                }}
              >
                <AlertTriangle
                  className="w-4 h-4 shrink-0 mt-0.5"
                  style={{ color: "var(--on-error-container)" }}
                />
                <div>
                  <p
                    className="text-[12px] font-semibold mb-1"
                    style={{ color: "var(--on-error-container)" }}
                  >
                    Compliance issues found:
                  </p>
                  {readiness.issues.map((issue) => (
                    <p
                      key={issue}
                      className="text-[12px]"
                      style={{ color: "var(--on-error-container)" }}
                    >
                      • {issue}
                    </p>
                  ))}
                </div>
              </div>
            )}

            <p className="text-[12px] leading-[18px]" style={{ color: "var(--on-surface-variant)" }}>
              {outreachReady
                ? "This lead meets all initial requirements. You may generate outreach emails in the Email Studio."
                : "Outreach is blocked for this lead until all compliance requirements are satisfied."}
            </p>
          </div>

          {/* Card: Source compliance details */}
          <div
            className="bg-white border rounded-lg p-6 shadow-sm"
            style={{ borderColor: "var(--outline-variant)" }}
          >
            <div className="flex items-center gap-2 mb-4">
              <FileText className="w-5 h-5" style={{ color: "var(--primary)" }} />
              <h3
                className="text-[16px] font-semibold"
                style={{ color: "var(--on-surface)" }}
              >
                Data Source Audit
              </h3>
            </div>

            <div className="space-y-4">
              <div>
                <p
                  className="text-[11px] font-semibold uppercase tracking-wider mb-1.5"
                  style={{ color: "var(--on-surface-variant)" }}
                >
                  Compliance Source Note
                </p>
                <div
                  className="p-3 rounded text-[13px] leading-[20px]"
                  style={{
                    background: "var(--surface-container-low)",
                    color: "var(--on-surface)",
                  }}
                >
                  {lead.compliance_source_note ?? "No compliance / source note recorded."}
                </div>
              </div>

              {lead.source_url && (
                <div>
                  <p
                    className="text-[11px] font-semibold uppercase tracking-wider mb-1.5"
                    style={{ color: "var(--on-surface-variant)" }}
                  >
                    Source URL
                  </p>
                  <a
                    href={lead.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 text-[13px] font-medium"
                    style={{ color: "var(--primary)" }}
                  >
                    {lead.source_url}
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
