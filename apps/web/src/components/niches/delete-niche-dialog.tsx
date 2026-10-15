"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { getErrorMessage } from "@/lib/api/client";
import { nichesApi } from "@/lib/api/endpoints";
import type { Niche } from "@/lib/api/types";

/** Destructive confirm for deleting a niche (which also removes its leads and campaigns). */
export function DeleteNicheDialog({
  niche,
  open,
  onOpenChange,
  onDeleted,
}: {
  niche: Pick<Niche, "id" | "name"> | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onDeleted?: () => void;
}) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const remove = useMutation({
    mutationFn: (id: number) => nichesApi.delete(id),
    onError: (err) => setError(getErrorMessage(err)),
    onSuccess: () => {
      toast.success(`Deleted ${niche?.name ?? "niche"}`);
      for (const key of ["niches", "leads", "campaigns", "companies", "dashboard", "onboarding", "approvals"]) {
        queryClient.invalidateQueries({ queryKey: [key] });
      }
      onOpenChange(false);
      onDeleted?.();
    },
  });

  return (
    <ConfirmDialog
      open={open}
      onOpenChange={(next) => {
        if (!next) setError(null);
        onOpenChange(next);
      }}
      title={`Delete ${niche?.name ?? "this niche"}?`}
      description="This permanently deletes the niche along with all of its leads, campaigns, drafts and search history. It can't be undone."
      confirmLabel="Delete niche"
      destructive
      loading={remove.isPending}
      onConfirm={() => niche && remove.mutate(niche.id)}
    >
      {error ? (
        <p role="alert" className="rounded-lg bg-destructive/5 p-3 text-[13px] text-destructive">
          {error}
        </p>
      ) : null}
    </ConfirmDialog>
  );
}
