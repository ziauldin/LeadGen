"use client";

import { Suspense, useMemo, useState } from "react";
import Link from "next/link";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ChevronDown, Download, Gauge, Plus, Search, Upload } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { DataTable, type DataTableColumn } from "@/components/data-table/data-table";
import { KpiCard } from "@/components/shared/kpi-card";
import { StatusBadge } from "@/components/shared/status-badge";
import { ScoreBadge } from "@/components/shared/score-badge";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { EmptyState } from "@/components/shared/empty-state";
import { LoadingState } from "@/components/shared/loading-error";
import { Button } from "@/components/ui/button";
import { ButtonLink } from "@/components/ui/button-link";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  DebouncedSearchInput,
  FilterBar,
  SelectField,
} from "@/components/leads/filter-controls";
import { LeadBulkActions } from "@/components/leads/lead-bulk-actions";
import { LeadRowActions } from "@/components/leads/lead-row-actions";
import { ImportCsvDialog } from "@/components/leads/import-csv-dialog";
import {
  ALL_LEAD_STATUSES,
  formatDateTime,
  formatRelativeDate,
  leadStatusLabel,
} from "@/components/leads/lead-status";
import { useTableState } from "@/hooks/use-table-state";
import { getErrorMessage } from "@/lib/api/client";
import { leadsApi, nichesApi } from "@/lib/api/endpoints";
import type { Lead } from "@/lib/api/types";

const STATUS_OPTIONS = [
  { value: "all", label: "All statuses" },
  ...ALL_LEAD_STATUSES.map((status) => ({ value: status, label: leadStatusLabel(status) })),
];
const EMAIL_OPTIONS = [
  { value: "any", label: "Any" },
  { value: "true", label: "Has email" },
  { value: "false", label: "No email" },
];
const SCORE_OPTIONS = [
  { value: "any", label: "Any score" },
  { value: "40", label: "40 or more" },
  { value: "60", label: "60 or more" },
  { value: "80", label: "80 or more" },
];

export default function LeadsPage() {
  return (
    <Suspense fallback={<LoadingState message="Loading leads…" />}>
      <LeadsView />
    </Suspense>
  );
}

function LeadsView() {
  const queryClient = useQueryClient();
  const table = useTableState({ sort: "-updated_at" });
  const { filters } = table;
  const nicheId = filters.niche_id ? Number(filters.niche_id) : undefined;
  const hasFilters = Object.keys(filters).length > 0;

  const [importOpen, setImportOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Lead | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const leads = useQuery({
    queryKey: ["leads", "list", table.apiParams],
    queryFn: () => leadsApi.list(table.apiParams),
    placeholderData: keepPreviousData,
  });
  const stats = useQuery({
    queryKey: ["leads", "stats", nicheId ?? null],
    queryFn: () => leadsApi.stats(nicheId),
  });
  const niches = useQuery({
    queryKey: ["niches", { limit: 200 }],
    queryFn: () => nichesApi.list({ limit: 200 }),
  });

  const nicheOptions = useMemo(
    () => [
      { value: "all", label: "All niches" },
      ...(niches.data?.items ?? []).map((niche) => ({
        value: String(niche.id),
        label: niche.name,
      })),
    ],
    [niches.data],
  );

  const recalc = useMutation({
    mutationFn: () => leadsApi.recalculateScores(nicheId),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      toast.success(`Recalculated scores for ${result.updated.toLocaleString()} leads`);
    },
  });
  const exportCsv = useMutation({
    mutationFn: () => leadsApi.exportCsv(nicheId),
    onSuccess: () => toast.success("Export downloaded"),
  });
  const remove = useMutation({
    mutationFn: (lead: Lead) => leadsApi.delete(lead.id),
    // The API explains refusals (e.g. the lead was already emailed); show that in the dialog.
    onError: (error) => setDeleteError(getErrorMessage(error)),
    onSuccess: (_data, lead) => {
      toast.success(`Deleted ${lead.full_name}`);
      setDeleteTarget(null);
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  const columns = useMemo<DataTableColumn<Lead>[]>(
    () => [
      {
        id: "name",
        header: "Name",
        sortKey: "full_name",
        className: "min-w-[180px]",
        cell: ({ row }) => (
          <div className="min-w-0">
            <Link
              href={`/leads/${row.original.id}`}
              className="font-semibold text-[var(--on-surface)] hover:text-[var(--primary)] hover:underline focus-visible:rounded focus-visible:ring-2 focus-visible:ring-[var(--primary)] focus-visible:outline-none"
            >
              {row.original.full_name}
            </Link>
            <p className="truncate text-[12px] text-[var(--on-surface-variant)]">
              {row.original.job_title || "No job title"}
            </p>
          </div>
        ),
      },
      {
        id: "company",
        header: "Company",
        cell: ({ row }) =>
          row.original.company ? (
            <Link
              href={`/companies/${row.original.company.id}`}
              className="text-[var(--on-surface)] hover:text-[var(--primary)] hover:underline"
            >
              {row.original.company.name}
            </Link>
          ) : (
            <span className="text-[var(--on-surface-variant)]">—</span>
          ),
      },
      {
        id: "email",
        header: "Email",
        cell: ({ row }) =>
          row.original.primary_email ? (
            <span className="text-[var(--on-surface)]">{row.original.primary_email}</span>
          ) : (
            <span className="text-[12px] text-[var(--on-surface-variant)] italic">No email</span>
          ),
      },
      {
        id: "status",
        header: "Status",
        sortKey: "status",
        cell: ({ row }) => <StatusBadge status={row.original.status} />,
      },
      {
        id: "score",
        header: "Score",
        sortKey: "score",
        cell: ({ row }) => <ScoreBadge score={Math.round(row.original.score)} />,
      },
      {
        id: "updated",
        header: "Updated",
        sortKey: "updated_at",
        cell: ({ row }) => (
          <time
            dateTime={row.original.updated_at}
            title={formatDateTime(row.original.updated_at)}
            className="whitespace-nowrap text-[var(--on-surface-variant)]"
          >
            {formatRelativeDate(row.original.updated_at)}
          </time>
        ),
      },
      {
        id: "actions",
        header: () => <span className="sr-only">Actions</span>,
        className: "w-12 text-right",
        cell: ({ row }) => (
          <LeadRowActions
            lead={row.original}
            onDelete={(lead) => {
              setDeleteError(null);
              setDeleteTarget(lead);
            }}
          />
        ),
      },
    ],
    [],
  );

  const s = stats.data;

  return (
    <div>
      <PageHeader
        title="Leads"
        description="Everyone you've found or imported. Filter, enrich, score and add them to campaigns."
        actions={
          <>
            <Button variant="outline" onClick={() => setImportOpen(true)}>
              <Upload aria-hidden />
              Import CSV
            </Button>
            <Button
              variant="outline"
              onClick={() => exportCsv.mutate()}
              disabled={exportCsv.isPending}
            >
              <Download aria-hidden />
              {exportCsv.isPending ? "Exporting…" : "Export CSV"}
            </Button>
            <Button variant="outline" onClick={() => recalc.mutate()} disabled={recalc.isPending}>
              <Gauge aria-hidden />
              {recalc.isPending ? "Recalculating…" : "Recalculate scores"}
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger render={<Button />}>
                <Plus aria-hidden />
                Add leads
                <ChevronDown aria-hidden />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-52">
                <DropdownMenuItem render={<Link href={nicheId ? `/search?niche_id=${nicheId}` : "/search"} />}>
                  <Search aria-hidden />
                  Find leads with search
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => setImportOpen(true)}>
                  <Upload aria-hidden />
                  Import from CSV
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </>
        }
      />

      <section
        aria-label="Lead summary"
        className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5"
      >
        {stats.isError ? (
          <p className="col-span-full text-[13px] text-destructive" role="alert">
            Couldn&apos;t load lead stats: {getErrorMessage(stats.error)}{" "}
            <button type="button" className="underline" onClick={() => stats.refetch()}>
              Try again
            </button>
          </p>
        ) : (
          <>
            <KpiCard label="Total leads" value={s ? s.total : "—"} />
            <KpiCard
              label="With email"
              value={s ? s.with_email : "—"}
              dot="green"
              trend={
                s && s.total > 0 ? (
                  <span className="text-[11px] text-[var(--on-surface-variant)]">
                    {Math.round((s.with_email / s.total) * 100)}% of leads
                  </span>
                ) : null
              }
            />
            <KpiCard label="Average score" value={s ? Math.round(s.average_score) : "—"} />
            <KpiCard label="Added last 7 days" value={s ? s.added_last_7_days : "—"} dot="blue" />
            <KpiCard
              label="In active sequences"
              value={s ? s.in_active_sequences : "—"}
              highlight
            />
          </>
        )}
      </section>

      <FilterBar>
        <DebouncedSearchInput
          label="Search"
          placeholder="Name, job title or company"
          value={filters.search ?? ""}
          onChange={(value) => table.setFilter("search", value || undefined)}
          className="sm:col-span-2 lg:w-72"
        />
        <SelectField
          label="Niche"
          value={filters.niche_id ?? "all"}
          onChange={(value) => table.setFilter("niche_id", value === "all" ? undefined : value)}
          options={nicheOptions}
          className="lg:w-48"
        />
        <SelectField
          label="Status"
          value={filters.status ?? "all"}
          onChange={(value) => table.setFilter("status", value === "all" ? undefined : value)}
          options={STATUS_OPTIONS}
          className="lg:w-44"
        />
        <SelectField
          label="Email"
          value={filters.has_email ?? "any"}
          onChange={(value) => table.setFilter("has_email", value === "any" ? undefined : value)}
          options={EMAIL_OPTIONS}
          className="lg:w-36"
        />
        <SelectField
          label="Minimum score"
          value={filters.min_score ?? "any"}
          onChange={(value) => table.setFilter("min_score", value === "any" ? undefined : value)}
          options={SCORE_OPTIONS}
          className="lg:w-36"
        />
        {hasFilters ? (
          <Button variant="ghost" className="h-9 self-end" onClick={table.clearFilters}>
            Clear filters
          </Button>
        ) : null}
      </FilterBar>

      <DataTable<Lead>
        caption="Leads"
        columns={columns}
        data={leads.data?.items}
        total={leads.data?.total ?? 0}
        page={table.page}
        pageSize={table.pageSize}
        sort={table.sort}
        onPageChange={table.setPage}
        onSortChange={table.setSort}
        isLoading={leads.isLoading || leads.isPlaceholderData}
        error={leads.error}
        onRetry={() => leads.refetch()}
        bulkActions={(ids, clear) => (
          <LeadBulkActions selectedIds={ids} clear={clear} nicheId={nicheId} />
        )}
        emptyState={
          hasFilters ? (
            <EmptyState
              title="No leads match these filters"
              description="Try a different search or clear the filters to see everyone."
              action={
                <Button variant="outline" onClick={table.clearFilters}>
                  Clear filters
                </Button>
              }
            />
          ) : (
            <EmptyState
              title="No leads yet"
              description="Run a search for your niche to find people, or import a CSV you already have."
              action={
                <div className="flex flex-wrap justify-center gap-2">
                  <ButtonLink href="/search">
                    <Search aria-hidden />
                    Find leads
                  </ButtonLink>
                  <Button variant="outline" onClick={() => setImportOpen(true)}>
                    <Upload aria-hidden />
                    Import CSV
                  </Button>
                </div>
              }
            />
          )
        }
      />

      <ImportCsvDialog open={importOpen} onOpenChange={setImportOpen} />

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        title={`Delete ${deleteTarget?.full_name ?? "this lead"}?`}
        description="This removes the lead, its contacts and any unsent drafts. Leads that have already been emailed can't be deleted; disqualify them instead."
        confirmLabel="Delete lead"
        destructive
        loading={remove.isPending}
        onConfirm={() => deleteTarget && remove.mutate(deleteTarget)}
      >
        {deleteError ? (
          <p role="alert" className="rounded-lg bg-destructive/5 p-3 text-[13px] text-destructive">
            {deleteError}
          </p>
        ) : null}
      </ConfirmDialog>
    </div>
  );
}
