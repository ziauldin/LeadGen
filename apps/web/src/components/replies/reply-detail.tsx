"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Megaphone, User } from "lucide-react";
import { ErrorState } from "@/components/shared/loading-error";
import { EmptyState } from "@/components/shared/empty-state";
import { ButtonLink } from "@/components/ui/button-link";
import { ApiError } from "@/lib/api/client";
import { campaignsApi, repliesApi } from "@/lib/api/endpoints";
import {
  AiLabelMarker,
  ReplyClassificationBadge,
} from "@/components/replies/reply-classification-badge";
import { ReplyConversation } from "@/components/replies/reply-conversation";
import { ReplyLinkPanel } from "@/components/replies/reply-link-panel";
import { ReplyTriagePanel } from "@/components/replies/reply-triage-panel";
import { formatDateTime } from "@/components/replies/format";

function DetailSkeleton() {
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]" role="status" aria-label="Loading reply">
      <div className="space-y-3">
        {[0, 1, 2].map((key) => (
          <div key={key} className="h-28 animate-pulse rounded-lg bg-[var(--surface-container-high)]" />
        ))}
      </div>
      <div className="space-y-3">
        {[0, 1].map((key) => (
          <div key={key} className="h-32 animate-pulse rounded-lg bg-[var(--surface-container-high)]" />
        ))}
      </div>
    </div>
  );
}

export function ReplyDetailView({ id }: { id: number }) {
  const reply = useQuery({
    queryKey: ["reply", id],
    queryFn: () => repliesApi.get(id),
    enabled: Number.isFinite(id),
  });
  const campaignId = reply.data?.campaign_id ?? null;
  const campaign = useQuery({
    queryKey: ["campaign", campaignId],
    queryFn: () => campaignsApi.get(campaignId!),
    enabled: campaignId != null,
    staleTime: 60_000,
  });

  const back = (
    <ButtonLink
      variant="ghost"
      size="sm"
      className="-ml-2 mb-3"
      href="/replies"
    >
      <ArrowLeft aria-hidden />
      All replies
    </ButtonLink>
  );

  if (!Number.isFinite(id) || (reply.error instanceof ApiError && reply.error.status === 404)) {
    return (
      <div>
        {back}
        <EmptyState
          title="Reply not found"
          description="It may have been deleted, or it belongs to another workspace."
        />
      </div>
    );
  }
  if (reply.error) {
    return (
      <div>
        {back}
        <ErrorState error={reply.error} onRetry={() => void reply.refetch()} />
      </div>
    );
  }
  if (!reply.data) {
    return (
      <div>
        {back}
        <DetailSkeleton />
      </div>
    );
  }

  const data = reply.data;
  return (
    <div>
      {back}
      <header className="mb-6 space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <ReplyClassificationBadge classification={data.classification} />
          <AiLabelMarker
            classifiedBy={data.classified_by}
            confidence={data.classification_confidence}
          />
          {!data.email_message_id ? (
            <span className="rounded border border-dashed border-[var(--outline)] px-1.5 text-[11px] leading-[18px] text-[var(--on-surface-variant)]">
              Unmatched
            </span>
          ) : null}
        </div>
        <h1 className="break-words text-[24px] font-bold leading-[32px] tracking-[-0.01em] text-[var(--on-surface)]">
          {data.subject || "(no subject)"}
        </h1>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-[var(--on-surface-variant)]">
          <span>
            From <span className="font-medium text-[var(--on-surface)]">{data.from_email}</span>
          </span>
          <span>{formatDateTime(data.received_at)}</span>
          {data.lead_id ? (
            <Link
              href={`/leads/${data.lead_id}`}
              className="inline-flex items-center gap-1 rounded-sm text-[var(--primary)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)]"
            >
              <User className="size-3.5" aria-hidden />
              {data.lead_name ?? "View lead"}
            </Link>
          ) : null}
          {data.campaign_id ? (
            <Link
              href={`/campaigns/${data.campaign_id}`}
              className="inline-flex items-center gap-1 rounded-sm text-[var(--primary)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)]"
            >
              <Megaphone className="size-3.5" aria-hidden />
              {campaign.data?.name ?? "View campaign"}
            </Link>
          ) : null}
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0 space-y-6">
          {!data.email_message_id ? <ReplyLinkPanel reply={data} /> : null}
          <ReplyConversation reply={data} />
        </div>
        <aside aria-label="Reply actions">
          <ReplyTriagePanel reply={data} />
        </aside>
      </div>
    </div>
  );
}
