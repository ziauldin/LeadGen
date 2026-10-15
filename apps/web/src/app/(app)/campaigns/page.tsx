"use client";

import { Suspense, useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Plus, Sparkles } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { DataTable, type DataTableColumn } from "@/components/data-table/data-table";
import { EmptyState } from "@/components/shared/empty-state";
import { LoadingState } from "@/components/shared/loading-error";
import { Button } from "@/components/ui/button";
import { ButtonLink } from "@/components/ui/button-link";
import { CampaignStatusBadge } from "@/components/campaigns/campaign-status-badge";
import { NativeSelect } from "@/components/campaigns/form-controls";
import { formatDate } from "@/components/campaigns/format";
import { useTableState } from "@/hooks/use-table-state";
import { campaignsApi, nichesApi } from "@/lib/api/endpoints";
import type { Campaign } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const STATUS_TABS = [
  { value: undefined, label: "All" },
  { value: "draft", label: "Draft" },
  { value: "active", label: "Active" },
  { value: "paused", label: "Paused" },
  { value: "completed", label: "Completed" },
] as const;

function CampaignsTable() {
  const router = useRouter();
  const table = useTableState({ pageSize: 25 });
  const status = table.filters.status;
  const nicheId = table.filters.niche_id;

  const params = {
    skip: table.apiParams.skip,
    limit: table.apiParams.limit,
    sort: table.sort,
    status,
    niche_id: nicheId ? Number(nicheId) : undefined,
  };
  const campaigns = useQuery({
    queryKey: ["campaigns", params],
    queryFn: () => campaignsApi.list(params),
    placeholderData: keepPreviousData,
  });
  const niches = useQuery({
    queryKey: ["niches", { limit: 200 }],
    queryFn: () => nichesApi.list({ limit: 200 }),
  });
  const nicheNames = useMemo(
    () => new Map((niches.data?.items ?? []).map((niche) => [niche.id, niche.name])),
    [niches.data],
  );

  const columns = useMemo<DataTableColumn<Campaign>[]>(
    () => [
      {
        id: "name",
        header: "Name",
        sortKey: "name",
        cell: ({ row }) => (
          <div className="min-w-[180px]">
            <Link
              href={`/campaigns/${row.original.id}`}
              onClick={(event) => event.stopPropagation()}
              className="rounded font-semibold text-[var(--on-surface)] outline-none hover:text-[var(--primary)] focus-visible:ring-2 focus-visible:ring-[var(--primary)]"
            >
              {row.original.name}
            </Link>
            {row.original.auto_paused_reason && row.original.status === "paused" ? (
              <p className="mt-0.5 text-[12px] text-[var(--error)]">Paused automatically</p>
            ) : null}
          </div>
        ),
      },
      {
        id: "niche",
        header: "Niche",
        cell: ({ row }) => (
          <span className="text-[var(--on-surface-variant)]">
            {nicheNames.get(row.original.niche_id) ?? (niches.isLoading ? "…" : `#${row.original.niche_id}`)}
          </span>
        ),
      },
      {
        id: "status",
        header: "Status",
        sortKey: "status",
        cell: ({ row }) => <CampaignStatusBadge status={row.original.status} />,
      },
      {
        id: "steps",
        header: "Steps",
        cell: ({ row }) => {
          const steps = row.original.steps;
          const ai = steps.some((step) => step.use_ai);
          return (
            <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
              {steps.length} {steps.length === 1 ? "step" : "steps"}
              {ai ? (
                <span
                  title="Uses AI drafts"
                  className="inline-flex items-center gap-1 rounded-full bg-[var(--primary-fixed)] px-1.5 py-0.5 text-[11px] font-medium text-[var(--primary)]"
                >
                  <Sparkles className="size-3" aria-hidden />
                  AI
                </span>
              ) : null}
            </span>
          );
        },
      },
      {
        id: "created_at",
        header: "Created",
        sortKey: "created_at",
        cell: ({ row }) => (
          <span className="whitespace-nowrap text-[var(--on-surface-variant)]">
            {formatDate(row.original.created_at)}
          </span>
        ),
      },
    ],
    [nicheNames, niches.isLoading],
  );

  const filtered = Boolean(status || nicheId);

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div
          role="group"
          aria-label="Filter by status"
          className="flex max-w-full gap-1 overflow-x-auto rounded-lg border border-[var(--outline-variant)] bg-white p-1"
        >
          {STATUS_TABS.map((tab) => {
            const active = (status ?? undefined) === tab.value;
            return (
              <button
                key={tab.label}
                type="button"
                aria-pressed={active}
                onClick={() => table.setFilter("status", tab.value)}
                className={cn(
                  "shrink-0 rounded-md px-3 py-1.5 text-[13px] font-medium transition-colors outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)]",
                  active
                    ? "bg-[var(--primary)] text-white"
                    : "text-[var(--on-surface-variant)] hover:bg-[var(--surface-container-low)] hover:text-[var(--on-surface)]",
                )}
              >
                {tab.label}
              </button>
            );
          })}
        </div>
        <div className="w-full sm:w-60">
          <label htmlFor="campaign-niche-filter" className="sr-only">
            Filter by niche
          </label>
          <NativeSelect
            id="campaign-niche-filter"
            value={nicheId ?? ""}
            onChange={(event) => table.setFilter("niche_id", event.target.value || undefined)}
          >
            <option value="">All niches</option>
            {(niches.data?.items ?? []).map((niche) => (
              <option key={niche.id} value={String(niche.id)}>
                {niche.name}
              </option>
            ))}
          </NativeSelect>
        </div>
      </div>

      <DataTable<Campaign>
        caption="Campaigns"
        columns={columns}
        data={campaigns.data?.items}
        total={campaigns.data?.total ?? 0}
        page={table.page}
        pageSize={table.pageSize}
        sort={table.sort}
        onPageChange={table.setPage}
        onSortChange={table.setSort}
        isLoading={campaigns.isLoading || (campaigns.isFetching && campaigns.isPlaceholderData)}
        error={campaigns.error}
        onRetry={() => campaigns.refetch()}
        onRowClick={(campaign) => router.push(`/campaigns/${campaign.id}`)}
        emptyState={
          filtered ? (
            <EmptyState
              title="No campaigns match these filters"
              description="Try another status or niche."
              action={
                <Button variant="outline" onClick={table.clearFilters}>
                  Clear filters
                </Button>
              }
            />
          ) : (
            <EmptyState
              title="No campaigns yet"
              description="Create a campaign to send a sequence of emails to leads in a niche. Every email waits for your approval before it sends."
              action={
                <ButtonLink href="/campaigns/new">
                  <Plus aria-hidden />
                  New campaign
                </ButtonLink>
              }
            />
          )
        }
      />
    </div>
  );
}

export default function CampaignsPage() {
  return (
    <div>
      <PageHeader
        title="Campaigns"
        description="Multi-step email sequences. Each email is drafted for your approval before it sends."
        actions={
          <ButtonLink href="/campaigns/new" size="lg">
            <Plus aria-hidden />
            New campaign
          </ButtonLink>
        }
      />
      <Suspense fallback={<LoadingState message="Loading campaigns…" />}>
        <CampaignsTable />
      </Suspense>
    </div>
  );
}
