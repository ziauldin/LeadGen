"use client";

import { useMemo } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ArrowRight, Sparkles } from "lucide-react";
import { DataTable, type DataTableColumn } from "@/components/data-table/data-table";
import { EmptyState } from "@/components/shared/empty-state";
import { Button } from "@/components/ui/button";
import { SequenceStatusBadge } from "@/components/campaigns/campaign-status-badge";
import { NativeSelect } from "@/components/campaigns/form-controls";
import { formatDateTime, humanize } from "@/components/campaigns/format";
import { useTableState } from "@/hooks/use-table-state";
import { campaignsApi } from "@/lib/api/endpoints";
import type { CampaignMessage, EmailMessageStatus } from "@/lib/api/types";

const MESSAGE_STATUSES: [EmailMessageStatus, string][] = [
  ["draft", "Draft"],
  ["pending_approval", "Awaiting approval"],
  ["approved", "Approved"],
  ["queued", "Queued"],
  ["sending", "Sending"],
  ["sent", "Sent"],
  ["failed", "Failed"],
  ["bounced", "Bounced"],
  ["complained", "Complaint"],
  ["rejected", "Rejected"],
  ["cancelled", "Cancelled"],
];
const AWAITING = new Set(["draft", "pending_approval"]);

export function CampaignMessagesTable({
  campaignId,
  totalSteps,
}: {
  campaignId: number;
  totalSteps: number;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const table = useTableState({ pageSize: 25 });
  const status = table.filters.status;
  const stepNumber = table.filters.step_number;

  const params = {
    skip: table.apiParams.skip,
    limit: table.apiParams.limit,
    sort: table.sort,
    status,
    step_number: stepNumber ? Number(stepNumber) : undefined,
  };
  const messages = useQuery({
    queryKey: ["campaign", campaignId, "messages", params],
    queryFn: () => campaignsApi.messages(campaignId, params),
    placeholderData: keepPreviousData,
  });

  const columns = useMemo<DataTableColumn<CampaignMessage>[]>(
    () => [
      {
        id: "recipient_email",
        header: "Recipient",
        sortKey: "recipient_email",
        cell: ({ row }) => (
          <div className="min-w-[200px] max-w-[280px]">
            <Link
              href={`/leads/${row.original.lead_id}`}
              className="rounded font-semibold text-[var(--on-surface)] outline-none hover:text-[var(--primary)] focus-visible:ring-2 focus-visible:ring-[var(--primary)]"
            >
              {row.original.lead_name ?? row.original.recipient_email}
            </Link>
            {row.original.lead_name ? (
              <p className="truncate text-[12px] text-[var(--on-surface-variant)]">{row.original.recipient_email}</p>
            ) : null}
            <p className="truncate text-[12px] text-[var(--on-surface-variant)]" title={row.original.subject}>
              {row.original.subject}
            </p>
          </div>
        ),
      },
      {
        id: "step_number",
        header: "Step",
        sortKey: "step_number",
        cell: ({ row }) => <span className="tabular-nums">{row.original.step_number ?? "—"}</span>,
      },
      {
        id: "status",
        header: "Status",
        sortKey: "status",
        cell: ({ row }) => (
          <div className="flex flex-col items-start gap-1">
            <SequenceStatusBadge status={row.original.status} />
            {row.original.reply_status ? (
              <span className="text-[12px] text-[var(--secondary)]">Reply: {humanize(row.original.reply_status)}</span>
            ) : null}
            {AWAITING.has(row.original.status) ? (
              <Link
                href={`/approvals?campaign_id=${campaignId}`}
                className="inline-flex items-center gap-0.5 rounded text-[12px] font-medium text-[var(--primary)] outline-none hover:underline focus-visible:ring-2 focus-visible:ring-[var(--primary)]"
              >
                Review <ArrowRight className="size-3" aria-hidden />
              </Link>
            ) : null}
          </div>
        ),
      },
      {
        id: "scheduled_for",
        header: "Scheduled for",
        sortKey: "scheduled_for",
        cell: ({ row }) => (
          <span className="whitespace-nowrap text-[var(--on-surface-variant)]">
            {formatDateTime(row.original.scheduled_for)}
          </span>
        ),
      },
      {
        id: "sent_at",
        header: "Sent",
        sortKey: "sent_at",
        cell: ({ row }) => (
          <span className="whitespace-nowrap text-[var(--on-surface-variant)]">
            {formatDateTime(row.original.sent_at)}
          </span>
        ),
      },
      {
        id: "failure_reason",
        header: "Problem",
        cell: ({ row }) =>
          row.original.failure_reason ? (
            <span className="block max-w-[240px] text-[12px] text-[var(--error)]">{row.original.failure_reason}</span>
          ) : (
            <span className="text-[var(--on-surface-variant)]">—</span>
          ),
      },
      {
        id: "generation_mode",
        header: "Written by",
        cell: ({ row }) =>
          row.original.generation_mode === "ai" ? (
            <span className="inline-flex items-center gap-1 whitespace-nowrap rounded-full bg-[var(--primary-fixed)] px-2 py-0.5 text-[12px] font-medium text-[var(--primary)]">
              <Sparkles className="size-3" aria-hidden />
              AI draft
            </span>
          ) : (
            <span className="whitespace-nowrap text-[12px] text-[var(--on-surface-variant)]">
              {row.original.generation_mode ? humanize(row.original.generation_mode) : "Template"}
            </span>
          ),
      },
    ],
    [campaignId],
  );

  const filtered = Boolean(status || stepNumber);

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row">
        <div className="w-full sm:w-56">
          <label htmlFor="message-status-filter" className="sr-only">
            Filter by email status
          </label>
          <NativeSelect
            id="message-status-filter"
            value={status ?? ""}
            onChange={(event) => table.setFilter("status", event.target.value || undefined)}
          >
            <option value="">All statuses</option>
            {MESSAGE_STATUSES.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </NativeSelect>
        </div>
        <div className="w-full sm:w-40">
          <label htmlFor="message-step-filter" className="sr-only">
            Filter by step
          </label>
          <NativeSelect
            id="message-step-filter"
            value={stepNumber ?? ""}
            onChange={(event) => table.setFilter("step_number", event.target.value || undefined)}
          >
            <option value="">All steps</option>
            {Array.from({ length: Math.max(totalSteps, 1) }, (_, index) => (
              <option key={index + 1} value={String(index + 1)}>
                Step {index + 1}
              </option>
            ))}
          </NativeSelect>
        </div>
      </div>

      <DataTable<CampaignMessage>
        caption="Campaign emails"
        columns={columns}
        data={messages.data?.items}
        total={messages.data?.total ?? 0}
        page={table.page}
        pageSize={table.pageSize}
        sort={table.sort}
        onPageChange={table.setPage}
        onSortChange={table.setSort}
        isLoading={messages.isLoading || (messages.isFetching && messages.isPlaceholderData)}
        error={messages.error}
        onRetry={() => messages.refetch()}
        emptyState={
          filtered ? (
            <EmptyState
              title="No emails match these filters"
              action={
                <Button
                  variant="outline"
                  onClick={() => router.replace(`${pathname}?tab=messages`, { scroll: false })}
                >
                  Clear filters
                </Button>
              }
            />
          ) : (
            <EmptyState
              title="No emails yet"
              description="Emails appear here once you add leads. Each starts as a draft that needs approval."
            />
          )
        }
      />
    </div>
  );
}
