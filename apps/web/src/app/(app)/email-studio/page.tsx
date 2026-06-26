"use client";

import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { EmailPreview } from "@/components/emails/email-preview";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { PageHeader } from "@/components/layout/page-header";
import { emailsApi, leadsApi } from "@/lib/api/endpoints";

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
  });

  const approveMutation = useMutation({
    mutationFn: () => emailsApi.approve(messageId!),
    onSuccess: () => {
      toast.success("Email approved for sending");
      setConfirmApprove(false);
    },
  });

  const canApprove =
    messageId &&
    previewQuery.data &&
    readinessQuery.data?.ready &&
    (previewQuery.data.can_send ??
      (previewQuery.data.compliance_errors?.length === 0 && previewQuery.data.has_opt_out_line));

  return (
    <div>
      <PageHeader
        title="Email studio"
        description="Preview generated outreach and confirm compliance before approval."
      />
      <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Lead</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Input
              placeholder="Lead ID"
              value={leadId}
              onChange={(e) => {
                setLeadId(e.target.value);
                setMessageId(null);
              }}
            />
            {leadQuery.data ? (
              <div className="space-y-1 text-sm">
                <p className="font-medium">{leadQuery.data.full_name}</p>
                <p className="text-muted-foreground">{leadQuery.data.primary_email ?? "No email"}</p>
                <p className="text-muted-foreground">Status: {leadQuery.data.status}</p>
              </div>
            ) : null}
            <div className="flex flex-col gap-2">
              <Button onClick={() => previewQuery.refetch()} disabled={!leadId} variant="outline">
                Refresh preview
              </Button>
              <Button
                onClick={() => generateMutation.mutate()}
                disabled={!leadId || generateMutation.isPending}
              >
                Generate draft
              </Button>
              <Button
                onClick={() => setConfirmApprove(true)}
                disabled={!canApprove || approveMutation.isPending}
              >
                Approve email
              </Button>
            </div>
            {readinessQuery.data && !readinessQuery.data.ready ? (
              <p className="text-sm text-destructive">
                Lead is not outreach-ready. Fix compliance issues on the lead detail page first.
              </p>
            ) : null}
          </CardContent>
        </Card>
        {previewQuery.data ? <EmailPreview preview={previewQuery.data} /> : null}
      </div>
      <ConfirmDialog
        open={confirmApprove}
        onOpenChange={setConfirmApprove}
        title="Approve this email?"
        description="Approved emails can be sent when the campaign is active and all send gates pass."
        confirmLabel="Approve"
        onConfirm={() => approveMutation.mutate()}
        loading={approveMutation.isPending}
      />
    </div>
  );
}
