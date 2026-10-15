"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { CircleStop, UserPlus } from "lucide-react";
import { DataTable, type DataTableColumn } from "@/components/data-table/data-table";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { EmptyState } from "@/components/shared/empty-state";
import { Button } from "@/components/ui/button";
import { SequenceStatusBadge } from "@/components/campaigns/campaign-status-badge";
import { NativeSelect } from "@/components/campaigns/form-controls";
import { formatDateTime } from "@/components/campaigns/format";
import { useTableState } from "@/hooks/use-table-state";
import { campaignsApi } from "@/lib/api/endpoints";
import type { Enrollment } from "@/lib/api/types";

const ENROLLMENT_STATUSES = [
  ["active", "Active"],
  ["paused", "Paused"],
  ["completed", "Completed"],
  ["replied", "Replied"],
  ["bounced", "Bounced"],
  ["opted_out", "Opted out"],
  ["stopped", "Stopped"],
  ["failed", "Failed"],
] as const;

const STOPPABLE = new Set(["active", "paused"]);

export function CampaignEnrollmentsTable({
  campaignId,
  totalSteps,
  onAddLeads,
}: {
  campaignId: number;
  totalSteps: number;
  onAddLeads: () => void;
}) {
  const queryClient = useQueryClient();
  const table = useTableState({ pageSize: 25 });
  const status = table.filters.status;
  const [stopping, setStopping] = useState<Enrollment | null>(null);

  const params = { skip: table.apiParams.skip, limit: table.apiParams.limit, status };
  const enrollments = useQuery({
    queryKey: ["campaign", campaignId, "enrollments", params],
    queryFn: () => campaignsApi.enrollments(campaignId, params),
    placeholderData: keepPreviousData,
  });

  const stop = useMutation({
    mutationFn: (enrollment: Enrollment) => campaignsApi.stopEnrollment(campaignId, enrollment.id),
    onSuccess: (enrollment) => {
      toast.success(`Sequence stopped for ${enrollment.lead_name ?? enrollment.recipient_email}`, {
        description: "Any unsent emails for this lead were cancelled.",
      });
      setStopping(null);
      queryClient.invalidateQueries({ queryKey: ["campaign", campaignId] });
      queryClient.invalidateQueries({ queryKey: ["approvals"] });
    },
  });

  const columns = useMemo<DataTableColumn<Enrollment>[]>(
    () => [
      {
        id: "lead",
        header: "Lead",
        cell: ({ row }) => (
          <div className="min-w-[180px]">
            <Link
              href={`/leads/${row.original.lead_id}`}
              className="rounded font-semibold text-[var(--on-surface)] outline-none hover:text-[var(--primary)] focus-visible:ring-2 focus-visible:ring-[var(--primary)]"
            >
              {row.original.lead_name ?? `Lead #${row.original.lead_id}`}
            </Link>
            <p className="text-[12px] text-[var(--on-surface-variant)]">{row.original.recipient_email}</p>
          </div>
        ),
      },
      {
        id: "status",
        header: "Status",
        cell: ({ row }) => <SequenceStatusBadge status={row.original.status} />,
      },
      {
        id: "current_step",
        header: "Progress",
        cell: ({ row }) => (
          <span className="whitespace-nowrap tabular-nums">
            {row.original.current_step > 0
              ? `Step ${row.original.current_step} of ${totalSteps}`
              : "Not started"}
          </span>
        ),
      },
      {
        id: "next_send_at",
        header: "Next email",
        cell: ({ row }) =>
          row.original.next_step_number ? (
            <div className="whitespace-nowrap">
              <p>Step {row.original.next_step_number}</p>
              <p className="text-[12px] text-[var(--on-surface-variant)]">
                {row.original.next_send_at ? `Due ${formatDateTime(row.original.next_send_at)}` : "Not scheduled"}
              </p>
            </div>
          ) : (
            <span className="text-[var(--on-surface-variant)]">—</span>
          ),
      },
      {
        id: "last_sent_at",
        header: "Last sent",
        cell: ({ row }) => (
          <span className="whitespace-nowrap text-[var(--on-surface-variant)]">
            {formatDateTime(row.original.last_sent_at)}
          </span>
        ),
      },
      {
        id: "stopped_reason",
        header: "Stopped because",
        cell: ({ row }) => (
          <span className="block max-w-[220px] text-[12px] text-[var(--on-surface-variant)]">
            {row.original.stopped_reason ?? "—"}
          </span>
        ),
      },
      {
        id: "actions",
        header: () => <span className="sr-only">Actions</span>,
        className: "w-20 text-right",
        cell: ({ row }) =>
          STOPPABLE.has(row.original.status) ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setStopping(row.original)}
              aria-label={`Stop sequence for ${row.original.lead_name ?? row.original.recipient_email}`}
            >
              <CircleStop aria-hidden />
              Stop
            </Button>
          ) : null,
      },
    ],
    [totalSteps],
  );

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="w-full sm:w-56">
          <label htmlFor="enrollment-status-filter" className="sr-only">
            Filter by enrollment status
          </label>
          <NativeSelect
            id="enrollment-status-filter"
            value={status ?? ""}
            onChange={(event) => table.setFilter("status", event.target.value || undefined)}
          >
            <option value="">All statuses</option>
            {ENROLLMENT_STATUSES.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </NativeSelect>
        </div>
        <Button variant="outline" onClick={onAddLeads}>
          <UserPlus aria-hidden />
          Add leads
        </Button>
      </div>

      <DataTable<Enrollment>
        caption="Enrolled leads"
        columns={columns}
        data={enrollments.data?.items}
        total={enrollments.data?.total ?? 0}
        page={table.page}
        pageSize={table.pageSize}
        onPageChange={table.setPage}
        isLoading={enrollments.isLoading || (enrollments.isFetching && enrollments.isPlaceholderData)}
        error={enrollments.error}
        onRetry={() => enrollments.refetch()}
        emptyState={
          status ? (
            <EmptyState
              title="No leads with this status"
              description="Choose another status to see more leads."
              action={
                <Button variant="outline" onClick={() => table.setFilter("status", undefined)}>
                  Show all
                </Button>
              }
            />
          ) : (
            <EmptyState
              title="No leads in this campaign yet"
              description="Add leads from the campaign's niche. Each one gets a step 1 draft to approve."
              action={
                <Button onClick={onAddLeads}>
                  <UserPlus aria-hidden />
                  Add leads
                </Button>
              }
            />
          )
        }
      />

      <ConfirmDialog
        open={stopping !== null}
        onOpenChange={(open) => !open && setStopping(null)}
        title="Stop this lead's sequence?"
        description={`${stopping?.lead_name ?? stopping?.recipient_email ?? "This lead"} won't get any more emails from this campaign. Unsent emails, including drafts awaiting approval, are cancelled.`}
        confirmLabel="Stop sequence"
        destructive
        loading={stop.isPending}
        onConfirm={() => stopping && stop.mutate(stopping)}
      />
    </div>
  );
}
