"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Link2, Unlink } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ErrorState, LoadingState } from "@/components/shared/loading-error";
import { emailDomain, formatDateTime } from "@/components/replies/format";
import { campaignsApi, repliesApi } from "@/lib/api/endpoints";
import type { CampaignMessage, ReplyDetail } from "@/lib/api/types";
import { cn } from "@/lib/utils";

/** For replies we couldn't tie to a sent email: pick the campaign and the email it answers. */
export function ReplyLinkPanel({ reply }: { reply: ReplyDetail }) {
  const queryClient = useQueryClient();
  const [campaignId, setCampaignId] = useState<string>("");
  const [messageId, setMessageId] = useState<number | null>(null);
  const [sameDomainOnly, setSameDomainOnly] = useState(true);
  const domain = emailDomain(reply.from_email);

  const campaigns = useQuery({
    queryKey: ["campaigns", { limit: 200, sort: "name" }],
    queryFn: () => campaignsApi.list({ limit: 200, sort: "name" }),
    staleTime: 60_000,
  });

  const messageParams = { status: "sent", limit: 50, sort: "-sent_at" };
  const messages = useQuery({
    queryKey: ["campaign-messages", Number(campaignId), messageParams],
    queryFn: () => campaignsApi.messages(Number(campaignId), messageParams),
    enabled: Boolean(campaignId),
  });

  const { matching, visible } = useMemo(() => {
    const items = messages.data?.items ?? [];
    const same = items.filter((item) => emailDomain(item.recipient_email) === domain);
    return {
      matching: same,
      visible: sameDomainOnly && same.length > 0 ? same : items,
    };
  }, [messages.data, domain, sameDomainOnly]);

  const link = useMutation({
    mutationFn: (emailMessageId: number) => repliesApi.link(reply.id, emailMessageId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["reply", reply.id] });
      void queryClient.invalidateQueries({ queryKey: ["replies"] });
      void queryClient.invalidateQueries({ queryKey: ["leads"] });
      void queryClient.invalidateQueries({ queryKey: ["campaign-messages"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success("Reply linked. The lead and campaign have been updated.");
    },
  });

  const campaignItems = useMemo(
    () =>
      Object.fromEntries(
        (campaigns.data?.items ?? []).map((campaign) => [String(campaign.id), campaign.name]),
      ),
    [campaigns.data],
  );

  return (
    <section
      aria-labelledby="link-heading"
      className="rounded-lg border border-[var(--tertiary-fixed-dim)] bg-[var(--tertiary-fixed)]/40 p-4"
    >
      <div className="mb-3 flex items-start gap-2">
        <Unlink className="mt-0.5 size-4 shrink-0 text-[var(--tertiary)]" aria-hidden />
        <div>
          <h2 id="link-heading" className="text-[14px] font-semibold text-[var(--on-surface)]">
            Link to a sent email
          </h2>
          <p className="text-[13px] text-[var(--on-surface-variant)]">
            We couldn&apos;t tell which email this answers. Linking it updates the lead, stops
            follow-ups if needed and counts the reply in the campaign&apos;s stats.
          </p>
        </div>
      </div>

      <div className="space-y-3">
        <div>
          <label
            htmlFor="link-campaign"
            className="mb-1 block text-[12px] font-semibold text-[var(--on-surface)]"
          >
            Campaign
          </label>
          {campaigns.error ? (
            <ErrorState error={campaigns.error} onRetry={() => void campaigns.refetch()} />
          ) : (
            <Select
              value={campaignId || null}
              items={campaignItems}
              onValueChange={(value) => {
                setCampaignId(value ? String(value) : "");
                setMessageId(null);
              }}
              disabled={campaigns.isLoading}
            >
              <SelectTrigger id="link-campaign" className="h-9 w-full bg-white sm:max-w-sm">
                <SelectValue
                  placeholder={campaigns.isLoading ? "Loading campaigns…" : "Choose a campaign"}
                />
              </SelectTrigger>
              <SelectContent alignItemWithTrigger={false}>
                {(campaigns.data?.items ?? []).map((campaign) => (
                  <SelectItem key={campaign.id} value={String(campaign.id)}>
                    {campaign.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          {campaigns.data && campaigns.data.items.length === 0 ? (
            <p className="mt-1 text-[12px] text-[var(--on-surface-variant)]">
              You don&apos;t have any campaigns yet, so there&apos;s nothing to link to.
            </p>
          ) : null}
        </div>

        {campaignId ? (
          messages.isLoading ? (
            <LoadingState message="Loading sent emails…" />
          ) : messages.error ? (
            <ErrorState error={messages.error} onRetry={() => void messages.refetch()} />
          ) : (messages.data?.items.length ?? 0) === 0 ? (
            <p className="rounded-md bg-white p-3 text-[13px] text-[var(--on-surface-variant)]">
              This campaign hasn&apos;t sent any emails yet. Try another campaign.
            </p>
          ) : (
            <fieldset className="space-y-2">
              <legend className="mb-1 text-[12px] font-semibold text-[var(--on-surface)]">
                Which email is this a reply to?
              </legend>
              {domain ? (
                matching.length > 0 ? (
                  <label className="flex items-center gap-2 text-[12px] text-[var(--on-surface-variant)]">
                    <input
                      type="checkbox"
                      className="size-4 accent-[var(--primary)]"
                      checked={sameDomainOnly}
                      onChange={(event) => setSameDomainOnly(event.target.checked)}
                    />
                    Only show recipients at @{domain} ({matching.length})
                  </label>
                ) : (
                  <p className="text-[12px] text-[var(--on-surface-variant)]">
                    No recent emails went to @{domain}, so all sent emails are shown.
                  </p>
                )
              ) : null}
              <ul className="max-h-80 space-y-1.5 overflow-y-auto pr-1">
                {visible.map((message: CampaignMessage) => {
                  const selected = messageId === message.id;
                  return (
                    <li key={message.id}>
                      <label
                        className={cn(
                          "flex cursor-pointer items-start gap-3 rounded-md border bg-white p-2.5 text-[13px] transition-colors focus-within:ring-2 focus-within:ring-[var(--primary)]",
                          selected
                            ? "border-[var(--primary)] bg-[var(--primary-fixed)]/40"
                            : "border-[var(--outline-variant)] hover:bg-[var(--surface-container-low)]",
                        )}
                      >
                        <input
                          type="radio"
                          name="link-message"
                          value={message.id}
                          checked={selected}
                          onChange={() => setMessageId(message.id)}
                          className="mt-1 size-4 accent-[var(--primary)]"
                        />
                        <span className="min-w-0 flex-1">
                          <span className="block truncate font-medium text-[var(--on-surface)]">
                            {message.lead_name
                              ? `${message.lead_name} · ${message.recipient_email}`
                              : message.recipient_email}
                          </span>
                          <span className="block truncate text-[var(--on-surface-variant)]">
                            {message.subject}
                          </span>
                          <span className="block text-[11px] text-[var(--on-surface-variant)]">
                            {message.step_number ? `Step ${message.step_number} · ` : ""}
                            Sent {formatDateTime(message.sent_at)}
                          </span>
                        </span>
                      </label>
                    </li>
                  );
                })}
              </ul>
              {(messages.data?.total ?? 0) > (messages.data?.items.length ?? 0) ? (
                <p className="text-[11px] text-[var(--on-surface-variant)]">
                  Showing the 50 most recent sent emails in this campaign.
                </p>
              ) : null}
            </fieldset>
          )
        ) : null}

        <Button
          onClick={() => messageId && link.mutate(messageId)}
          disabled={!messageId || link.isPending}
        >
          <Link2 aria-hidden />
          {link.isPending ? "Linking…" : "Link reply"}
        </Button>
      </div>
    </section>
  );
}
