"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { SelectField } from "@/components/leads/filter-controls";
import { toastBulkResult } from "@/components/data-table/bulk-result";
import { campaignsApi, leadsApi, nichesApi } from "@/lib/api/endpoints";
import type { BulkResult } from "@/lib/api/types";

/** Groups non-ok bulk results by reason: "Lead has no email" × 3. */
export function summariseBulkProblems(result: BulkResult) {
  const groups = new Map<string, { status: string; count: number }>();
  for (const item of result.results) {
    if (item.status === "ok") continue;
    const reason = item.detail || (item.status === "skipped" ? "Skipped" : "Failed");
    const key = `${item.status}:${reason}`;
    const entry = groups.get(key) ?? { status: item.status, count: 0 };
    entry.count += 1;
    groups.set(key, entry);
  }
  return [...groups.entries()].map(([key, value]) => ({
    reason: key.slice(key.indexOf(":") + 1),
    status: value.status,
    count: value.count,
  }));
}

export function BulkResultSummary({ result, verb }: { result: BulkResult; verb: string }) {
  const problems = summariseBulkProblems(result);
  return (
    <div className="space-y-3 text-[13px]" aria-live="polite">
      <p className="flex items-center gap-2 font-medium text-[var(--on-surface)]">
        <CheckCircle2 className="size-4 text-emerald-600" aria-hidden />
        {result.succeeded} {verb}
        {result.skipped ? `, ${result.skipped} skipped` : ""}
        {result.failed ? `, ${result.failed} failed` : ""}
      </p>
      {problems.length > 0 ? (
        <ul className="space-y-1.5 rounded-lg border border-amber-200 bg-amber-50 p-3 text-amber-900">
          {problems.map((problem) => (
            <li key={`${problem.status}-${problem.reason}`} className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
              <span>
                <span className="font-semibold">
                  {problem.count} {problem.status}:
                </span>{" "}
                {problem.reason}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export function AddToCampaignDialog({
  open,
  onOpenChange,
  leadIds,
  nicheId,
  onDone,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  leadIds: number[];
  /** When known, only campaigns in this niche are offered. */
  nicheId?: number;
  onDone?: () => void;
}) {
  const queryClient = useQueryClient();
  const [campaignId, setCampaignId] = useState("");
  const [result, setResult] = useState<BulkResult | null>(null);

  const campaigns = useQuery({
    queryKey: ["campaigns", "picker", nicheId ?? null],
    queryFn: () => campaignsApi.list({ niche_id: nicheId, limit: 200, sort: "-created_at" }),
    enabled: open,
  });
  const niches = useQuery({
    queryKey: ["niches", { limit: 200 }],
    queryFn: () => nichesApi.list({ limit: 200 }),
    enabled: open && !nicheId,
  });

  const options = useMemo(() => {
    const nicheNames = new Map((niches.data?.items ?? []).map((n) => [n.id, n.name]));
    return (campaigns.data?.items ?? [])
      .filter((campaign) => campaign.status !== "completed")
      .map((campaign) => {
        const niche = nicheId ? null : nicheNames.get(campaign.niche_id);
        const status = campaign.status === "active" ? "" : ` (${campaign.status})`;
        return {
          value: String(campaign.id),
          label: `${campaign.name}${status}${niche ? ` · ${niche}` : ""}`,
        };
      });
  }, [campaigns.data, niches.data, nicheId]);

  const add = useMutation({
    mutationFn: () =>
      leadsApi.bulk({
        lead_ids: leadIds,
        action: "add_to_campaign",
        campaign_id: Number(campaignId),
      }),
    onSuccess: (data) => {
      toastBulkResult(data, "added");
      queryClient.invalidateQueries({ queryKey: ["approvals"] });
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["campaigns"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["onboarding"] });
      onDone?.();
      if (data.skipped || data.failed) setResult(data);
      else close(false);
    },
  });

  function close(next: boolean) {
    if (add.isPending) return;
    onOpenChange(next);
    if (!next) {
      setResult(null);
      setCampaignId("");
    }
  }

  const count = leadIds.length;

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>
            Add {count} lead{count === 1 ? "" : "s"} to a campaign
          </DialogTitle>
          <DialogDescription>
            Each lead gets a first-step draft that waits in Approvals until someone approves it.
            Leads can only join campaigns in their own niche; others are skipped.
          </DialogDescription>
        </DialogHeader>

        {result ? (
          <BulkResultSummary result={result} verb="added" />
        ) : campaigns.isError ? (
          <p role="alert" className="text-[13px] text-destructive">
            Couldn&apos;t load campaigns.{" "}
            <button type="button" className="underline" onClick={() => campaigns.refetch()}>
              Try again
            </button>
          </p>
        ) : !campaigns.isLoading && options.length === 0 ? (
          <div className="rounded-lg border border-dashed border-[var(--outline-variant)] p-4 text-[13px] text-[var(--on-surface-variant)]">
            No open campaigns{nicheId ? " in this niche" : ""} yet.{" "}
            <Link href="/campaigns/new" className="font-medium text-[var(--primary)] underline">
              Create a campaign
            </Link>{" "}
            first.
          </div>
        ) : (
          <SelectField
            label="Campaign"
            value={campaignId}
            onChange={setCampaignId}
            options={options}
            placeholder={campaigns.isLoading ? "Loading campaigns…" : "Choose a campaign"}
            disabled={campaigns.isLoading}
          />
        )}

        <DialogFooter>
          {result ? (
            <Button onClick={() => close(false)}>Done</Button>
          ) : (
            <>
              <Button variant="outline" onClick={() => close(false)} disabled={add.isPending}>
                Cancel
              </Button>
              <Button onClick={() => add.mutate()} disabled={!campaignId || add.isPending}>
                {add.isPending ? "Adding…" : "Add to campaign"}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
