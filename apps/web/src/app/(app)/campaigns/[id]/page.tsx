"use client";

import { useParams } from "next/navigation";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { PageHeader } from "@/components/layout/page-header";
import { campaignsApi, leadsApi } from "@/lib/api/endpoints";

export default function CampaignDetailPage() {
  const params = useParams();
  const id = Number(params.id);
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
  });

  const pauseMutation = useMutation({
    mutationFn: () => campaignsApi.pause(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["campaigns", id] });
      toast.success("Campaign paused");
    },
  });

  const addLeadsMutation = useMutation({
    mutationFn: () => campaignsApi.addLeads(id, selectedLeadIds),
    onSuccess: (result) => {
      toast.success(`Added ${result.created} leads to campaign`);
      setSelectedLeadIds([]);
    },
  });

  const sendMutation = useMutation({
    mutationFn: () => campaignsApi.processSends(id),
    onSuccess: (result) => {
      toast.success(`Sent ${result.sent}, blocked ${result.blocked}`);
      setConfirmSend(false);
    },
  });

  function toggleLead(leadId: number) {
    setSelectedLeadIds((current) =>
      current.includes(leadId) ? current.filter((x) => x !== leadId) : [...current, leadId],
    );
  }

  if (isLoading) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (!campaign) return <p className="text-sm text-destructive">Campaign not found.</p>;

  return (
    <div>
      <PageHeader
        title={campaign.name}
        description={`Status: ${campaign.status}`}
        actions={
          <>
            {campaign.status !== "active" ? (
              <Button onClick={() => startMutation.mutate()} disabled={startMutation.isPending}>
                Start
              </Button>
            ) : (
              <Button variant="outline" onClick={() => pauseMutation.mutate()} disabled={pauseMutation.isPending}>
                Pause
              </Button>
            )}
            <Button
              variant="secondary"
              onClick={() => setConfirmSend(true)}
              disabled={campaign.status !== "active"}
            >
              Process sends
            </Button>
          </>
        }
      />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Steps</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {campaign.steps.map((step) => (
              <div key={step.id} className="rounded-lg border p-4">
                <div className="mb-2 flex items-center gap-2">
                  <Badge>Step {step.step_number}</Badge>
                  <span className="text-sm text-muted-foreground">+{step.delay_days} days</span>
                </div>
                <p className="text-sm font-medium">{step.subject_template}</p>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Add leads</CardTitle>
            <Button
              size="sm"
              onClick={() => addLeadsMutation.mutate()}
              disabled={selectedLeadIds.length === 0 || addLeadsMutation.isPending}
            >
              Add selected
            </Button>
          </CardHeader>
          <CardContent className="max-h-80 space-y-2 overflow-y-auto">
            {eligibleLeads.map((lead) => (
              <label
                key={lead.id}
                className="flex cursor-pointer items-start gap-2 rounded-lg border p-3 text-sm"
              >
                <input
                  type="checkbox"
                  checked={selectedLeadIds.includes(lead.id)}
                  onChange={() => toggleLead(lead.id)}
                  className="mt-1"
                />
                <span>
                  <span className="font-medium">{lead.full_name}</span>
                  <span className="block text-muted-foreground">{lead.primary_email}</span>
                </span>
              </label>
            ))}
            {eligibleLeads.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No outreach-ready leads. Ensure email, source URL, and compliance note are set.
              </p>
            ) : null}
          </CardContent>
        </Card>
      </div>
      <ConfirmDialog
        open={confirmSend}
        onOpenChange={setConfirmSend}
        title="Process campaign sends?"
        description="Only approved messages that pass compliance gates will be sent."
        confirmLabel="Process sends"
        onConfirm={() => sendMutation.mutate()}
        loading={sendMutation.isPending}
      />
    </div>
  );
}
