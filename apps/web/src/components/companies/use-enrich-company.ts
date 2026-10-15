"use client";

import { useCallback, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { companiesApi } from "@/lib/api/endpoints";
import type { Company } from "@/lib/api/types";

/** Can this company be enriched right now? Returns the reason when it can't. */
export function enrichBlockedReason(company: Pick<Company, "website" | "enrichment_status">) {
  if (!company.website) return "Add a website to enrich this company";
  if (company.enrichment_status === "in_progress") return "Enrichment is already running";
  return null;
}

/**
 * Queues enrichment for one company at a time per call, tracking which rows are busy so each
 * row shows its own spinner instead of one global one.
 */
export function useEnrichCompany() {
  const queryClient = useQueryClient();
  const [pending, setPending] = useState<ReadonlySet<number>>(new Set());

  const mutation = useMutation({
    mutationFn: (id: number) => companiesApi.enrich(id),
    onMutate: (id) => setPending((current) => new Set(current).add(id)),
    onSuccess: (result) => {
      toast.success(
        result.status === "queued"
          ? "Enrichment started. We'll update this company when it finishes."
          : result.message,
      );
    },
    onSettled: (_data, _error, id) => {
      setPending((current) => {
        const next = new Set(current);
        next.delete(id);
        return next;
      });
      queryClient.invalidateQueries({ queryKey: ["companies"] });
      queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });

  const { mutate } = mutation;
  const enrich = useCallback((id: number) => mutate(id), [mutate]);
  const isPending = useCallback((id: number) => pending.has(id), [pending]);

  return { enrich, isPending };
}
