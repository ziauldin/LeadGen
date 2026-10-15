"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Gauge, ListChecks, Send, Sparkles, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { toastBulkResult } from "@/components/data-table/bulk-result";
import { AddToCampaignDialog } from "@/components/leads/add-to-campaign-dialog";
import { SelectField } from "@/components/leads/filter-controls";
import { SETTABLE_LEAD_STATUSES, leadStatusLabel } from "@/components/leads/lead-status";
import { leadsApi } from "@/lib/api/endpoints";
import type { LeadBulkRequest, LeadStatus } from "@/lib/api/types";

type Action = LeadBulkRequest["action"];

const VERBS: Record<Action, string> = {
  add_to_campaign: "added",
  enrich: "queued for enrichment",
  set_status: "updated",
  rescore: "rescored",
  delete: "deleted",
};

const STATUS_OPTIONS = SETTABLE_LEAD_STATUSES.map((status) => ({
  value: status,
  label: leadStatusLabel(status),
}));

/** Actions shown in the DataTable bulk bar while leads are selected. */
export function LeadBulkActions({
  selectedIds,
  clear,
  nicheId,
}: {
  selectedIds: number[];
  clear: () => void;
  nicheId?: number;
}) {
  const queryClient = useQueryClient();
  const [dialog, setDialog] = useState<"campaign" | "status" | "delete" | null>(null);
  const [status, setStatus] = useState<string>("");
  const count = selectedIds.length;
  const plural = count === 1 ? "lead" : "leads";

  const bulk = useMutation({
    mutationFn: (payload: Omit<LeadBulkRequest, "lead_ids">) =>
      leadsApi.bulk({ lead_ids: selectedIds, ...payload }),
    onSuccess: (result, payload) => {
      toastBulkResult(result, VERBS[payload.action]);
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      if (payload.action === "enrich") queryClient.invalidateQueries({ queryKey: ["companies"] });
      if (payload.action === "delete") {
        queryClient.invalidateQueries({ queryKey: ["onboarding"] });
        queryClient.invalidateQueries({ queryKey: ["approvals"] });
      }
      setDialog(null);
      setStatus("");
      if (result.succeeded > 0) clear();
    },
  });

  const running = bulk.isPending ? bulk.variables?.action : undefined;

  return (
    <>
      <Button size="sm" variant="outline" onClick={() => setDialog("campaign")}>
        <Send aria-hidden />
        Add to campaign
      </Button>
      <Button
        size="sm"
        variant="outline"
        onClick={() => bulk.mutate({ action: "enrich" })}
        disabled={bulk.isPending}
      >
        <Sparkles aria-hidden />
        {running === "enrich" ? "Queuing…" : "Enrich companies"}
      </Button>
      <Button size="sm" variant="outline" onClick={() => setDialog("status")}>
        <ListChecks aria-hidden />
        Set status
      </Button>
      <Button
        size="sm"
        variant="outline"
        onClick={() => bulk.mutate({ action: "rescore" })}
        disabled={bulk.isPending}
      >
        <Gauge aria-hidden />
        {running === "rescore" ? "Rescoring…" : "Rescore"}
      </Button>
      <Button size="sm" variant="destructive" onClick={() => setDialog("delete")}>
        <Trash2 aria-hidden />
        Delete
      </Button>

      <AddToCampaignDialog
        open={dialog === "campaign"}
        onOpenChange={(open) => setDialog(open ? "campaign" : null)}
        leadIds={selectedIds}
        nicheId={nicheId}
        onDone={clear}
      />

      <ConfirmDialog
        open={dialog === "status"}
        onOpenChange={(open) => {
          setDialog(open ? "status" : null);
          if (!open) setStatus("");
        }}
        title={`Set status for ${count} ${plural}`}
        description="Opted out can't be set by hand. It's applied automatically when someone unsubscribes."
        confirmLabel="Apply status"
        confirmDisabled={!status}
        loading={running === "set_status"}
        onConfirm={() =>
          bulk.mutate({ action: "set_status", status: status as LeadStatus })
        }
      >
        <SelectField
          label="New status"
          value={status}
          onChange={setStatus}
          options={STATUS_OPTIONS}
          placeholder="Choose a status"
        />
      </ConfirmDialog>

      <ConfirmDialog
        open={dialog === "delete"}
        onOpenChange={(open) => setDialog(open ? "delete" : null)}
        title={`Delete ${count} ${plural}?`}
        description="This permanently removes the leads, their contacts and unsent drafts. Leads that have already been emailed are kept for your records and will be reported as failed."
        confirmLabel={`Delete ${plural}`}
        destructive
        loading={running === "delete"}
        onConfirm={() => bulk.mutate({ action: "delete" })}
      />
    </>
  );
}
