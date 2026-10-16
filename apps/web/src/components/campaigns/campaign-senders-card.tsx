"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useWorkspace } from "@/hooks/use-workspace";
import { mailboxesApi } from "@/lib/api/endpoints";

/** Which sending accounts a campaign rotates through. Empty means the campaign's default sender. */
export function CampaignSendersCard({ campaignId }: { campaignId: number }) {
  const queryClient = useQueryClient();
  const { can } = useWorkspace();
  const canEdit = can("campaigns.manage");
  const accounts = useQuery({ queryKey: ["sending-accounts"], queryFn: mailboxesApi.accounts });
  const current = useQuery({
    queryKey: ["campaign-senders", campaignId],
    queryFn: () => mailboxesApi.campaignSenders(campaignId),
  });
  const [selected, setSelected] = useState<Set<number>>(new Set());
  useEffect(() => {
    if (current.data) setSelected(new Set(current.data.map((a) => a.id)));
  }, [current.data]);

  const save = useMutation({
    mutationFn: () => mailboxesApi.setCampaignSenders(campaignId, [...selected]),
    onSuccess: (data) => {
      queryClient.setQueryData(["campaign-senders", campaignId], data);
      toast.success(data.length ? `Rotating between ${data.length} sending accounts` : "Using the campaign's default sender");
    },
  });

  const options = accounts.data ?? [];
  if (options.length < 2 && !current.data?.length) return null;
  const dirty =
    current.data !== undefined &&
    (current.data.length !== selected.size || current.data.some((a) => !selected.has(a.id)));

  return (
    <section aria-labelledby="senders-heading" className="mt-6 rounded-lg border border-[var(--outline-variant)] bg-white p-4">
      <h3 id="senders-heading" className="text-[14px] font-semibold">
        Sending accounts
      </h3>
      <p className="mt-1 text-[13px] text-[var(--on-surface-variant)]">
        Pick several to spread sending across mailboxes. Each lead&apos;s follow-ups come from the same mailbox
        as their first email, and paused or full mailboxes are skipped.
      </p>
      <fieldset className="mt-3 grid gap-1.5 sm:grid-cols-2" disabled={!canEdit}>
        <legend className="sr-only">Sending accounts for this campaign</legend>
        {options.map((account) => (
          <label key={account.id} className="flex items-center gap-2 text-[13px]">
            <input
              type="checkbox"
              className="size-4 accent-[var(--primary)]"
              checked={selected.has(account.id)}
              onChange={(event) =>
                setSelected((prev) => {
                  const next = new Set(prev);
                  if (event.target.checked) next.add(account.id);
                  else next.delete(account.id);
                  return next;
                })
              }
            />
            <span className={account.healthy ? "" : "text-[var(--on-surface-variant)] line-through"}>
              {account.email ?? account.label}
            </span>
            {account.cap_today !== null ? (
              <span className="text-[12px] text-[var(--on-surface-variant)]">({account.cap_today}/day)</span>
            ) : null}
          </label>
        ))}
      </fieldset>
      {canEdit ? (
        <Button className="mt-3" size="sm" disabled={!dirty || save.isPending} onClick={() => save.mutate()}>
          Save sending accounts
        </Button>
      ) : null}
    </section>
  );
}
