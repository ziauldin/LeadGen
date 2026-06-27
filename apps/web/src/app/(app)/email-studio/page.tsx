"use client";

import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  AlertTriangle,
  CheckCircle2,
  Lock,
  Mail,
  Shield,
  User,
  XCircle,
} from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { StatusBadge } from "@/components/shared/status-badge";
import { ScoreBadge } from "@/components/shared/score-badge";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { emailsApi, leadsApi } from "@/lib/api/endpoints";

function ComplianceCheckRow({
  label,
  ok,
}: {
  label: string;
  ok: boolean;
}) {
  return (
    <div className="flex items-center gap-2.5 py-1.5">
      {ok ? (
        <CheckCircle2 className="w-4 h-4 shrink-0" style={{ color: "var(--secondary)" }} />
      ) : (
        <XCircle className="w-4 h-4 shrink-0" style={{ color: "var(--error)" }} />
      )}
      <span className="text-[13px]" style={{ color: ok ? "var(--on-surface)" : "var(--error)" }}>
        {label}
      </span>
    </div>
  );
}

export default function EmailStudioPage() {
  const searchParams = useSearchParams();
  const initialLeadId = searchParams.get("lead_id") ?? "";
  const [leadId, setLeadId] = useState(initialLeadId);
  const [messageId, setMessageId] = useState<number | null>(null);
  const [confirmApprove, setConfirmApprove] = useState(false);

  const leadQuery = useQuery({
    queryKey: ["leads", leadId],
    queryFn: () => leadsApi.get(Number(leadId)),
    enabled: Boolean(leadId),
  });

  const readinessQuery = useQuery({
    queryKey: ["leads", leadId, "outreach-readiness"],
    queryFn: () => leadsApi.outreachReadiness(Number(leadId)),
    enabled: Boolean(leadId),
  });

  const previewQuery = useQuery({
    queryKey: ["email-preview", leadId],
    queryFn: () => emailsApi.preview(Number(leadId)),
    enabled: Boolean(leadId),
  });

  const generateMutation = useMutation({
    mutationFn: () => emailsApi.generate(Number(leadId)),
    onSuccess: (data) => {
      setMessageId(data.message.id);
      if (data.compliance_errors.length > 0) {
        toast.warning("Draft created with compliance issues");
      } else {
        toast.success("Draft email created");
      }
    },
    onError: () => toast.error("Failed to generate email"),
  });

  const approveMutation = useMutation({
    mutationFn: () => emailsApi.approve(messageId!),
    onSuccess: () => {
      toast.success("Email approved for sending");
      setConfirmApprove(false);
    },
    onError: () => toast.error("Approval failed"),
  });

  const lead = leadQuery.data;
  const readiness = readinessQuery.data;
  const preview = previewQuery.data;

  const complianceChecks = [
    {
      label: "Source URL exists",
      ok: !!lead?.source_url,
    },
    {
      label: "Compliance note recorded",
      ok: !!lead?.compliance_source_note,
    },
    {
      label: "Not opted out",
      ok: lead?.status !== "opted_out",
    },
    {
      label: "Outreach-ready status",
      ok: readiness?.ready ?? false,
    },
    {
      label: "Opt-out line in email",
      ok: preview?.has_opt_out_line ?? false,
    },
    {
      label: "No compliance errors",
      ok: (preview?.compliance_errors?.length ?? 0) === 0,
    },
  ];

  const allChecksPass = complianceChecks.every((c) => c.ok);
  const canApprove = Boolean(messageId) && allChecksPass;

  return (
    <div>
      <PageHeader
        title="Email Studio"
        description="Preview generated outreach and confirm compliance before approval. One lead at a time."
      />

      {/* Compliance mandate banner */}
      <div
        className="flex items-start gap-3 px-4 py-3 rounded-lg border mb-6"
        style={{
          background: "var(--primary-fixed)",
          borderColor: "var(--primary)",
          color: "var(--on-primary-fixed)",
        }}
      >
        <Lock className="w-4 h-4 mt-0.5 shrink-0" />
        <p className="text-[13px]">
          <strong>Manual approval required.</strong> Every email must pass all compliance
          checks before it can be queued for sending. Mass send is disabled by design.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[340px_1fr]">
        {/* Left panel — Lead + compliance */}
        <div className="flex flex-col gap-4">
          {/* Lead selector */}
          <div
            className="bg-white border rounded-lg p-5 shadow-sm"
            style={{ borderColor: "var(--outline-variant)" }}
          >
            <h3
              className="text-[14px] font-semibold mb-3"
              style={{ color: "var(--on-surface)" }}
            >
              Select Lead
            </h3>
            <input
              type="text"
              placeholder="Enter lead ID…"
              value={leadId}
              onChange={(e) => {
                setLeadId(e.target.value);
                setMessageId(null);
              }}
              className="w-full px-3 py-2 border rounded text-[13px] outline-none mb-3"
              style={{
                borderColor: "var(--outline-variant)",
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

            {lead && (
              <div
                className="flex items-center gap-3 p-3 rounded"
                style={{ background: "var(--surface-container-low)" }}
              >
                <div
                  className="w-9 h-9 rounded-full flex items-center justify-center text-[11px] font-bold text-white shrink-0"
                  style={{ background: "var(--primary)" }}
                >
                  {lead.full_name.slice(0, 2).toUpperCase()}
                </div>
                <div>
                  <p
                    className="text-[13px] font-semibold"
                    style={{ color: "var(--on-surface)" }}
                  >
                    {lead.full_name}
                  </p>
                  <p className="text-[12px]" style={{ color: "var(--on-surface-variant)" }}>
                    {lead.primary_email ?? "No email"}
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    <StatusBadge status={lead.status} />
                    <ScoreBadge score={lead.score} />
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Compliance Checklist */}
          {lead && (
            <div
              className="bg-white border rounded-lg p-5 shadow-sm"
              style={{ borderColor: "var(--outline-variant)" }}
            >
              <div className="flex items-center gap-2 mb-4">
                <Shield className="w-4 h-4" style={{ color: "var(--primary)" }} />
                <h3
                  className="text-[14px] font-semibold"
                  style={{ color: "var(--on-surface)" }}
                >
                  Compliance Checklist
                </h3>
              </div>
              <div className="divide-y" style={{ borderColor: "var(--outline-variant)" }}>
                {complianceChecks.map((check) => (
                  <ComplianceCheckRow key={check.label} label={check.label} ok={check.ok} />
                ))}
              </div>
              {readiness && !readiness.ready && (
                <div
                  className="flex items-start gap-2 mt-3 p-3 rounded"
                  style={{ background: "var(--error-container)" }}
                >
                  <AlertTriangle
                    className="w-4 h-4 mt-0.5 shrink-0"
                    style={{ color: "var(--on-error-container)" }}
                  />
                  <div>
                    {readiness.issues.map((issue) => (
                      <p
                        key={issue}
                        className="text-[12px]"
                        style={{ color: "var(--on-error-container)" }}
                      >
                        {issue}
                      </p>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Action buttons */}
          <div className="flex flex-col gap-3">
            <button
              onClick={() => previewQuery.refetch()}
              disabled={!leadId || previewQuery.isFetching}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 border rounded text-[13px] font-medium transition-colors disabled:opacity-50"
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
              <Mail className="w-4 h-4" />
              {previewQuery.isFetching ? "Loading preview…" : "Refresh Preview"}
            </button>
            <button
              onClick={() => generateMutation.mutate()}
              disabled={!leadId || generateMutation.isPending}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 border rounded text-[13px] font-medium transition-colors disabled:opacity-50"
              style={{
                background: "var(--surface-container-lowest)",
                borderColor: "var(--primary)",
                color: "var(--primary)",
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.background = "var(--primary-fixed)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = "var(--surface-container-lowest)")
              }
            >
              <User className="w-4 h-4" />
              {generateMutation.isPending ? "Generating…" : "Generate Draft"}
            </button>
            <button
              onClick={() => setConfirmApprove(true)}
              disabled={!canApprove || approveMutation.isPending}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded text-[13px] font-medium transition-colors text-white disabled:opacity-40"
              style={{ background: "var(--primary)" }}
              onMouseEnter={(e) =>
                !e.currentTarget.disabled && (e.currentTarget.style.background = "var(--surface-tint)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = "var(--primary)")
              }
            >
              <CheckCircle2 className="w-4 h-4" />
              Approve Email
            </button>
          </div>
        </div>

        {/* Right panel — Email preview */}
        <div
          className="bg-white border rounded-lg shadow-sm overflow-hidden"
          style={{ borderColor: "var(--outline-variant)" }}
        >
          {!leadId ? (
            <div className="flex flex-col items-center justify-center h-full p-16 text-center">
              <Mail className="w-12 h-12 mb-4" style={{ color: "var(--outline)" }} />
              <p
                className="text-[16px] font-semibold mb-2"
                style={{ color: "var(--on-surface)" }}
              >
                No lead selected
              </p>
              <p className="text-[13px]" style={{ color: "var(--on-surface-variant)" }}>
                Enter a lead ID on the left to preview a generated email.
              </p>
            </div>
          ) : preview ? (
            <div>
              <div
                className="px-6 py-4 border-b"
                style={{
                  background: "var(--surface)",
                  borderColor: "var(--outline-variant)",
                }}
              >
                <div className="flex items-center gap-2 mb-2">
                  <span
                    className="text-[11px] font-semibold uppercase tracking-wider"
                    style={{ color: "var(--on-surface-variant)" }}
                  >
                    To:
                  </span>
                  <span className="text-[13px]" style={{ color: "var(--on-surface)" }}>
                    {preview.recipient_email}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className="text-[11px] font-semibold uppercase tracking-wider"
                    style={{ color: "var(--on-surface-variant)" }}
                  >
                    Subject:
                  </span>
                  <span
                    className="text-[14px] font-semibold"
                    style={{ color: "var(--on-surface)" }}
                  >
                    {preview.subject}
                  </span>
                </div>
              </div>
              <div className="p-6">
                <pre
                  className="whitespace-pre-wrap text-[14px] leading-[22px] font-sans"
                  style={{ color: "var(--on-surface)" }}
                >
                  {preview.body}
                </pre>
              </div>
              {preview.compliance_errors && preview.compliance_errors.length > 0 && (
                <div
                  className="mx-6 mb-6 p-3 rounded border flex items-start gap-2"
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
                      Compliance issues:
                    </p>
                    {preview.compliance_errors.map((err) => (
                      <p
                        key={err}
                        className="text-[12px]"
                        style={{ color: "var(--on-error-container)" }}
                      >
                        • {err}
                      </p>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : previewQuery.isFetching ? (
            <div className="flex items-center justify-center h-full p-16">
              <div
                className="w-5 h-5 border-2 rounded-full animate-spin"
                style={{
                  borderColor: "var(--primary-container)",
                  borderTopColor: "var(--primary)",
                }}
              />
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full p-16 text-center">
              <Mail className="w-12 h-12 mb-4" style={{ color: "var(--outline)" }} />
              <p
                className="text-[14px]"
                style={{ color: "var(--on-surface-variant)" }}
              >
                Click &ldquo;Refresh Preview&rdquo; to generate an email preview for this lead.
              </p>
            </div>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={confirmApprove}
        onOpenChange={setConfirmApprove}
        title="Approve this email?"
        description="This email will be queued for sending when the campaign is active, the sending window is open, and all suppression checks pass. You cannot undo approval."
        confirmLabel="Approve for Sending"
        onConfirm={() => approveMutation.mutate()}
        loading={approveMutation.isPending}
      />
    </div>
  );
}
