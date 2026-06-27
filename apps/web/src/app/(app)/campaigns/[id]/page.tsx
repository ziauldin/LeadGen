"use client";

import { useParams, useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  AlertTriangle,
  ArrowLeft,
  Calendar,
  Clock,
  Megaphone,
  Pause,
  Play,
  Send,
  Users,
} from "lucide-react";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { PageHeader } from "@/components/layout/page-header";
import { campaignsApi, leadsApi } from "@/lib/api/endpoints";
import { StatusBadge } from "@/components/shared/status-badge";

export default function CampaignDetailPage() {
  const params = useParams();
  const id = Number(params.id);
  const router = useRouter();
  const queryClient = useQueryClient();
  const [selectedLeadIds, setSelectedLeadIds] = useState<number[]>([]);
  const [confirmSend, setConfirmSend] = useState(false);

  const { data: campaign, isLoading } = useQuery({
    queryKey: ["campaigns", id],
    queryFn: () => campaignsApi.get(id),
    enabled: Number.isFinite(id),
  });

  const { data: leads } = useQuery({
    queryKey: ["leads", campaign?.niche_id],
    queryFn: () => leadsApi.list({ niche_id: campaign!.niche_id }),
    enabled: Boolean(campaign?.niche_id),
  });

  const eligibleLeads = useMemo(
    () =>
      leads?.items.filter(
        (lead) =>
          lead.primary_email &&
          lead.status !== "opted_out" &&
          lead.source_url &&
          lead.compliance_source_note,
      ) ?? [],
    [leads?.items],
  );

  const startMutation = useMutation({
    mutationFn: () => campaignsApi.start(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["campaigns", id] });
      toast.success("Campaign started");
    },
    onError: () => toast.error("Failed to start campaign"),
  });

  const pauseMutation = useMutation({
    mutationFn: () => campaignsApi.pause(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["campaigns", id] });
      toast.success("Campaign paused");
    },
    onError: () => toast.error("Failed to pause campaign"),
  });

  const addLeadsMutation = useMutation({
    mutationFn: () => campaignsApi.addLeads(id, selectedLeadIds),
    onSuccess: (result) => {
      toast.success(`Added ${result.created} leads to campaign`);
      setSelectedLeadIds([]);
      queryClient.invalidateQueries({ queryKey: ["campaigns", id] });
    },
    onError: () => toast.error("Failed to add leads"),
  });

  const sendMutation = useMutation({
    mutationFn: () => campaignsApi.processSends(id),
    onSuccess: (result) => {
      toast.success(`Sent ${result.sent}, blocked ${result.blocked}`);
      setConfirmSend(false);
      queryClient.invalidateQueries({ queryKey: ["campaigns", id] });
    },
    onError: () => toast.error("Sending failed"),
  });

  function toggleLead(leadId: number) {
    setSelectedLeadIds((current) =>
      current.includes(leadId) ? current.filter((x) => x !== leadId) : [...current, leadId]
    );
  }

  if (isLoading) {
    return (
      <div className="p-8 text-center">
        <div
          className="inline-block w-5 h-5 border-2 rounded-full animate-spin mb-3"
          style={{ borderColor: "var(--primary-container)", borderTopColor: "var(--primary)" }}
        />
        <p className="text-[13px]" style={{ color: "var(--on-surface-variant)" }}>
          Loading campaign…
        </p>
      </div>
    );
  }

  if (!campaign) return <p className="text-sm text-destructive">Campaign not found.</p>;

  return (
    <div>
      <PageHeader
        title={campaign.name}
        description={`Manage sequence steps, add leads, and process outreach sends under compliant rate limits.`}
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
              <ArrowLeft className="w-4 h-4" />
              Back
            </button>
            {campaign.status !== "active" ? (
              <button
                onClick={() => startMutation.mutate()}
                disabled={startMutation.isPending}
                className="flex items-center gap-2 px-5 py-2 rounded text-[13px] font-medium text-white transition-colors"
                style={{ background: "var(--primary)" }}
              >
                <Play className="w-4 h-4" />
                Start Campaign
              </button>
            ) : (
              <button
                onClick={() => pauseMutation.mutate()}
                disabled={pauseMutation.isPending}
                className="flex items-center gap-2 px-5 py-2 border rounded text-[13px] font-medium transition-colors"
                style={{
                  background: "var(--surface-container-lowest)",
                  borderColor: "var(--outline-variant)",
                  color: "var(--on-surface)",
                }}
              >
                <Pause className="w-4 h-4" />
                Pause Campaign
              </button>
            )}
            <button
              onClick={() => setConfirmSend(true)}
              disabled={campaign.status !== "active" || sendMutation.isPending}
              className="flex items-center gap-2 px-5 py-2 rounded text-[13px] font-medium text-white transition-colors disabled:opacity-50"
              style={{ background: "var(--secondary)" }}
            >
              <Send className="w-4 h-4" />
              Process Sends
            </button>
          </>
        }
      />

      {/* Campaign settings summary banner */}
      <div
        className="flex flex-wrap items-center gap-6 px-5 py-4 border rounded-lg mb-6 shadow-sm bg-white"
        style={{ borderColor: "var(--outline-variant)" }}
      >
        <div className="flex items-center gap-2">
          <span className="text-[13px]" style={{ color: "var(--on-surface-variant)" }}>
            Campaign Status:
          </span>
          <StatusBadge status={campaign.status} />
        </div>
        <div className="flex items-center gap-2 text-[13px]" style={{ color: "var(--on-surface)" }}>
          <Clock className="w-4 h-4" style={{ color: "var(--primary)" }} />
          <strong>Daily limit:</strong> {campaign.daily_send_limit} sends
        </div>
        {campaign.sending_window_start && (
          <div className="flex items-center gap-2 text-[13px]" style={{ color: "var(--on-surface)" }}>
            <Calendar className="w-4 h-4" style={{ color: "var(--primary)" }} />
            <strong>Sending Window:</strong> {campaign.sending_window_start} – {campaign.sending_window_end}
          </div>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
        {/* Left: Sequence Steps */}
        <div
          className="bg-white border rounded-lg p-6 shadow-sm"
          style={{ borderColor: "var(--outline-variant)" }}
        >
          <div className="flex items-center gap-2 mb-6">
            <Megaphone className="w-5 h-5" style={{ color: "var(--primary)" }} />
            <h3
              className="text-[16px] font-semibold"
              style={{ color: "var(--on-surface)" }}
            >
              Outreach Sequence Steps
            </h3>
          </div>

          <div className="space-y-4">
            {campaign.steps.map((step) => (
              <div
                key={step.id}
                className="border rounded-lg p-4 transition-colors"
                style={{ borderColor: "var(--outline-variant)", background: "var(--surface-container-lowest)" }}
              >
                <div className="flex items-center justify-between mb-2">
                  <span
                    className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-[11px] font-semibold uppercase tracking-wider"
                    style={{
                      background: "var(--primary-fixed)",
                      color: "var(--on-primary-fixed)",
                    }}
                  >
                    Step {step.step_number}
                  </span>
                  <span
                    className="text-[12px] flex items-center gap-1 font-medium"
                    style={{ color: "var(--on-surface-variant)" }}
                  >
                    <Clock className="w-3.5 h-3.5" />
                    +{step.delay_days} days delay
                  </span>
                </div>
                <h4
                  className="text-[14px] font-semibold mb-2"
                  style={{ color: "var(--on-surface)" }}
                >
                  Subject: {step.subject_template}
                </h4>
                <div
                  className="p-3 rounded text-[13px] leading-[20px] font-sans whitespace-pre-wrap"
                  style={{
                    background: "var(--surface-container-low)",
                    color: "var(--on-surface)",
                  }}
                >
                  {step.body_template}
                </div>
              </div>
            ))}

            {campaign.steps.length === 0 && (
              <p className="text-[13px] text-center py-10" style={{ color: "var(--on-surface-variant)" }}>
                No steps defined in this campaign sequence.
              </p>
            )}
          </div>
        </div>

        {/* Right: Add eligible leads */}
        <div className="flex flex-col gap-6">
          <div
            className="bg-white border rounded-lg p-5 shadow-sm"
            style={{ borderColor: "var(--outline-variant)" }}
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Users className="w-4.5 h-4.5" style={{ color: "var(--primary)" }} />
                <h3
                  className="text-[14px] font-semibold"
                  style={{ color: "var(--on-surface)" }}
                >
                  Eligible Leads
                </h3>
              </div>
              <button
                onClick={() => addLeadsMutation.mutate()}
                disabled={selectedLeadIds.length === 0 || addLeadsMutation.isPending}
                className="px-3 py-1.5 rounded text-[12px] font-medium text-white transition-colors disabled:opacity-50"
                style={{ background: "var(--primary)" }}
              >
                Add Selected ({selectedLeadIds.length})
              </button>
            </div>

            <p className="text-[12px] mb-4" style={{ color: "var(--on-surface-variant)" }}>
              Leads from the target niche that meet compliance conditions (Email, Source URL, and
              Compliance Source Note recorded).
            </p>

            <div className="max-h-[360px] overflow-y-auto space-y-2 pr-1">
              {eligibleLeads.map((lead) => (
                <div
                  key={lead.id}
                  onClick={() => toggleLead(lead.id)}
                  className="flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors"
                  style={{
                    borderColor: selectedLeadIds.includes(lead.id)
                      ? "var(--primary)"
                      : "var(--outline-variant)",
                    background: selectedLeadIds.includes(lead.id)
                      ? "var(--primary-fixed)"
                      : "var(--surface-container-lowest)",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={selectedLeadIds.includes(lead.id)}
                    onChange={() => {}}
                    className="mt-1 rounded shrink-0 pointer-events-none"
                  />
                  <div className="min-w-0">
                    <p
                      className="text-[13px] font-semibold truncate"
                      style={{ color: "var(--on-surface)" }}
                    >
                      {lead.full_name}
                    </p>
                    <p className="text-[12px] truncate" style={{ color: "var(--on-surface-variant)" }}>
                      {lead.primary_email}
                    </p>
                  </div>
                </div>
              ))}

              {eligibleLeads.length === 0 && (
                <div
                  className="p-4 rounded border text-center"
                  style={{ borderColor: "var(--outline-variant)", background: "var(--surface-container-low)" }}
                >
                  <AlertTriangle className="w-5 h-5 mx-auto mb-2" style={{ color: "var(--outline)" }} />
                  <p className="text-[12px]" style={{ color: "var(--on-surface-variant)" }}>
                    No outreach-ready leads in this niche. Ensure leads have email, source URL, and
                    compliance notes set first.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <ConfirmDialog
        open={confirmSend}
        onOpenChange={setConfirmSend}
        title="Process campaign sends?"
        description="This will scan approved email drafts and trigger sends through configured providers. Only approved messages that pass compliance checks will be sent. Daily limits and per-domain throttles will be enforced."
        confirmLabel="Process Sends"
        onConfirm={() => sendMutation.mutate()}
        loading={sendMutation.isPending}
      />
    </div>
  );
}
