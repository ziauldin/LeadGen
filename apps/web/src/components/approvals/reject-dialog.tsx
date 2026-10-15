"use client";

import { useState } from "react";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { Textarea } from "@/components/ui/textarea";

/** Asks for an optional reason before rejecting one draft or several. */
export function RejectDialog({
  open,
  onOpenChange,
  count,
  onConfirm,
  loading,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  count: number;
  onConfirm: (reason: string) => void;
  loading?: boolean;
}) {
  const [reason, setReason] = useState("");
  const plural = count === 1 ? "this draft" : `${count} drafts`;

  return (
    <ConfirmDialog
      open={open}
      onOpenChange={(next) => {
        if (!next) setReason("");
        onOpenChange(next);
      }}
      title={count === 1 ? "Reject this draft?" : `Reject ${count} drafts?`}
      description={`Rejected emails are never sent. You can note why to help your team spot patterns in ${plural}.`}
      confirmLabel={count === 1 ? "Reject draft" : `Reject ${count} drafts`}
      destructive
      loading={loading}
      onConfirm={() => onConfirm(reason.trim())}
    >
      <div className="grid gap-1.5">
        <label htmlFor="reject-reason" className="text-[13px] font-medium">
          Reason <span className="font-normal text-muted-foreground">(optional)</span>
        </label>
        <Textarea
          id="reject-reason"
          value={reason}
          maxLength={500}
          rows={3}
          placeholder="e.g. Wrong contact, tone too pushy, already in touch"
          onChange={(event) => setReason(event.target.value)}
        />
      </div>
    </ConfirmDialog>
  );
}
