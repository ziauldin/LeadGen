"use client";

import { Suspense, useMemo } from "react";
import Link from "next/link";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, ExternalLink, Loader2, Search, Sparkles } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { DataTable, type DataTableColumn } from "@/components/data-table/data-table";
import { toastBulkResult } from "@/components/data-table/bulk-result";
import { EmptyState } from "@/components/shared/empty-state";
import { LoadingState } from "@/components/shared/loading-error";
import { Button } from "@/components/ui/button";
import { ButtonLink } from "@/components/ui/button-link";
import { DebouncedSearchInput, FilterBar, SelectField } from "@/components/leads/filter-controls";
import {
  ENRICHMENT_STATUS_OPTIONS,
  EnrichmentBadge,
} from "@/components/companies/enrichment-badge";
import { enrichBlockedReason, useEnrichCompany } from "@/components/companies/use-enrich-company";
import { useTableState } from "@/hooks/use-table-state";
import { companiesApi } from "@/lib/api/endpoints";
import type { Company } from "@/lib/api/types";

const STATUS_OPTIONS = [{ value: "all", label: "All statuses" }, ...ENRICHMENT_STATUS_OPTIONS];

export default function CompaniesPage() {
  return (
    <Suspense fallback={<LoadingState message="Loading companies…" />}>
      <CompaniesView />
    </Suspense>
  );
}

function CompaniesView() {
  const queryClient = useQueryClient();
  const table = useTableState({ sort: "name" });
  const { filters } = table;
  const hasFilters = Object.keys(filters).length > 0;
  const { enrich, isPending } = useEnrichCompany();

  const companies = useQuery({
    queryKey: ["companies", "list", table.apiParams],
    queryFn: () => companiesApi.list(table.apiParams),
    placeholderData: keepPreviousData,
    // Keep checking while a visible company is being enriched in the background.
    refetchInterval: (query) =>
      query.state.data?.items.some((c) => c.enrichment_status === "in_progress") ? 5000 : false,
  });

  const bulkEnrich = useMutation({
    mutationFn: (ids: number[]) => companiesApi.bulkEnrich(ids),
    onSuccess: (result) => {
      toastBulkResult(result, "queued for enrichment");
      queryClient.invalidateQueries({ queryKey: ["companies"] });
    },
  });

  const columns = useMemo<DataTableColumn<Company>[]>(
    () => [
      {
        id: "name",
        header: "Company",
        sortKey: "name",
        className: "min-w-[180px]",
        cell: ({ row }) => (
          <div className="flex items-center gap-3">
            <span
              className="flex size-8 shrink-0 items-center justify-center rounded-md bg-[var(--primary-fixed)]"
              aria-hidden
            >
              <Building2 className="size-4 text-[var(--primary)]" />
            </span>
            <div className="min-w-0">
              <Link
                href={`/companies/${row.original.id}`}
                className="font-semibold text-[var(--on-surface)] hover:text-[var(--primary)] hover:underline focus-visible:rounded focus-visible:ring-2 focus-visible:ring-[var(--primary)] focus-visible:outline-none"
              >
                {row.original.name}
              </Link>
              {row.original.country ? (
                <p className="text-[12px] text-[var(--on-surface-variant)]">
                  {row.original.country}
                </p>
              ) : null}
            </div>
          </div>
        ),
      },
      {
        id: "domain",
        header: "Website",
        sortKey: "domain",
        cell: ({ row }) =>
          row.original.website ? (
            <a
              href={row.original.website}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-[var(--primary)] hover:underline"
            >
              {row.original.domain ?? row.original.website}
              <ExternalLink className="size-3 opacity-70" aria-hidden />
              <span className="sr-only">(opens in a new tab)</span>
            </a>
          ) : (
            <span className="text-[12px] text-[var(--on-surface-variant)] italic">No website</span>
          ),
      },
      {
        id: "industry",
        header: "Industry",
        sortKey: "industry",
        cell: ({ row }) => row.original.industry ?? <span className="text-[var(--on-surface-variant)]">—</span>,
      },
      {
        id: "size",
        header: "Size",
        cell: ({ row }) =>
          row.original.size_estimate ? (
            `${row.original.size_estimate.toLocaleString()} people`
          ) : (
            <span className="text-[var(--on-surface-variant)]">—</span>
          ),
      },
      {
        id: "enrichment",
        header: "Enrichment",
        sortKey: "enrichment_status",
        className: "min-w-[160px]",
        cell: ({ row }) => (
          <div className="max-w-[240px]">
            <EnrichmentBadge
              status={row.original.enrichment_status}
              message={row.original.enrichment_message}
            />
            {row.original.enrichment_message && row.original.enrichment_status !== "pending" ? (
              <p
                className="mt-1 truncate text-[12px] text-[var(--on-surface-variant)]"
                title={row.original.enrichment_message}
              >
                {row.original.enrichment_message}
              </p>
            ) : null}
          </div>
        ),
      },
      {
        id: "contacts",
        header: "Contacts",
        className: "text-right",
        cell: ({ row }) => (
          <span className="tabular-nums">{row.original.email_contacts.length}</span>
        ),
      },
      {
        id: "actions",
        header: () => <span className="sr-only">Actions</span>,
        className: "w-28 text-right",
        cell: ({ row }) => {
          const company = row.original;
          const busy = isPending(company.id);
          const blocked = enrichBlockedReason(company);
          return (
            <Button
              size="sm"
              variant="outline"
              onClick={() => enrich(company.id)}
              disabled={busy || Boolean(blocked)}
              title={blocked ?? undefined}
              aria-label={`Enrich ${company.name}`}
            >
              {busy ? (
                <Loader2 className="animate-spin" aria-hidden />
              ) : (
                <Sparkles aria-hidden />
              )}
              {busy ? "Starting…" : "Enrich"}
            </Button>
          );
        },
      },
    ],
    [enrich, isPending],
  );

  return (
    <div>
      <PageHeader
        title="Companies"
        description="Companies behind your leads. Enrich them to find public contact addresses from their websites."
      />

      <FilterBar>
        <DebouncedSearchInput
          label="Search"
          placeholder="Name or domain"
          value={filters.search ?? ""}
          onChange={(value) => table.setFilter("search", value || undefined)}
          className="lg:w-80"
        />
        <SelectField
          label="Enrichment"
          value={filters.enrichment_status ?? "all"}
          onChange={(value) =>
            table.setFilter("enrichment_status", value === "all" ? undefined : value)
          }
          options={STATUS_OPTIONS}
          className="lg:w-48"
        />
        {hasFilters ? (
          <Button variant="ghost" className="h-9 self-end" onClick={table.clearFilters}>
            Clear filters
          </Button>
        ) : null}
      </FilterBar>

      <DataTable<Company>
        caption="Companies"
        columns={columns}
        data={companies.data?.items}
        total={companies.data?.total ?? 0}
        page={table.page}
        pageSize={table.pageSize}
        sort={table.sort}
        onPageChange={table.setPage}
        onSortChange={table.setSort}
        isLoading={companies.isLoading || companies.isPlaceholderData}
        error={companies.error}
        onRetry={() => companies.refetch()}
        bulkActions={(ids, clear) => (
          <Button
            size="sm"
            variant="outline"
            disabled={bulkEnrich.isPending}
            onClick={() => bulkEnrich.mutate(ids, { onSuccess: () => clear() })}
          >
            <Sparkles aria-hidden />
            {bulkEnrich.isPending ? "Queuing…" : "Enrich selected"}
          </Button>
        )}
        emptyState={
          hasFilters ? (
            <EmptyState
              title="No companies match these filters"
              description="Try another search or clear the filters."
              action={
                <Button variant="outline" onClick={table.clearFilters}>
                  Clear filters
                </Button>
              }
            />
          ) : (
            <EmptyState
              title="No companies yet"
              description="Companies are added automatically when you save search results or import leads with a company and website."
              action={
                <div className="flex flex-wrap justify-center gap-2">
                  <ButtonLink href="/search">
                    <Search aria-hidden />
                    Find leads
                  </ButtonLink>
                  <ButtonLink variant="outline" href="/leads">
                    Go to leads
                  </ButtonLink>
                </div>
              }
            />
          )
        }
      />
    </div>
  );
}
