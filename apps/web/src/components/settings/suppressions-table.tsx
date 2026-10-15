"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Search, Trash2 } from "lucide-react";
import { DataTable, type DataTableColumn } from "@/components/data-table/data-table";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { EmptyState } from "@/components/shared/empty-state";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { formatDate } from "@/components/settings/settings-card";
import { useTableState } from "@/hooks/use-table-state";
import { settingsApi } from "@/lib/api/endpoints";
import type { Suppression } from "@/lib/api/types";

const SOURCE_LABELS: Record<string, string> = {
  manual: "Added by hand",
  unsubscribe_link: "Unsubscribe link",
  reply: "Asked in a reply",
  provider: "Bounce or complaint",
  hunter: "Email finder",
};

export function SuppressionsTable({ canDelete }: { canDelete: boolean }) {
  const queryClient = useQueryClient();
  const table = useTableState({ pageSize: 25 });
  const [searchText, setSearchText] = useState(table.filters.search ?? "");
  const [deleteTarget, setDeleteTarget] = useState<Suppression | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const urlSearch = table.filters.search ?? "";
  const setFilterRef = useRef(table.setFilter);
  useEffect(() => {
    setFilterRef.current = table.setFilter;
  });
  useEffect(() => {
    if (searchText.trim() === urlSearch) return;
    const timer = window.setTimeout(
      () => setFilterRef.current("search", searchText.trim() || undefined),
      350,
    );
    return () => window.clearTimeout(timer);
  }, [searchText, urlSearch]);

  // This endpoint pages and searches but doesn't sort; newest first is the server default.
  const params = { skip: table.apiParams.skip, limit: table.apiParams.limit, search: urlSearch || undefined };
  const suppressions = useQuery({
    queryKey: ["suppressions", params],
    queryFn: () => settingsApi.listSuppressions(params),
    placeholderData: (previous) => previous,
  });

  const remove = useMutation({
    mutationFn: (id: number) => settingsApi.deleteSuppression(id),
    meta: { silent: true },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["suppressions"] });
      toast.success(`${deleteTarget?.email ?? deleteTarget?.domain ?? "Entry"} removed from the list`);
      setDeleteTarget(null);
    },
    onError: (error) => setDeleteError(error.message),
  });

  const columns = useMemo<DataTableColumn<Suppression>[]>(
    () => [
      {
        id: "value",
        header: "Blocked",
        cell: ({ row }) => (
          <div className="flex min-w-[180px] items-center gap-2">
            <span className="break-all font-medium text-[var(--on-surface)]">
              {row.original.email ?? row.original.domain ?? "—"}
            </span>
            <span className="shrink-0 rounded bg-[var(--surface-container)] px-1.5 py-0.5 text-[11px] text-[var(--on-surface-variant)]">
              {row.original.email ? "Address" : "Domain"}
            </span>
          </div>
        ),
      },
      {
        id: "reason",
        header: "Reason",
        className: "hidden md:table-cell",
        cell: ({ row }) => (
          <span className="text-[var(--on-surface-variant)]">{row.original.reason || "—"}</span>
        ),
      },
      {
        id: "source",
        header: "Source",
        cell: ({ row }) => (
          <span className="whitespace-nowrap text-[var(--on-surface-variant)]">
            {SOURCE_LABELS[row.original.source ?? ""] ?? row.original.source ?? "—"}
          </span>
        ),
      },
      {
        id: "created_at",
        header: "Added",
        className: "hidden sm:table-cell whitespace-nowrap",
        cell: ({ row }) => (
          <span className="text-[var(--on-surface-variant)]">{formatDate(row.original.created_at)}</span>
        ),
      },
      {
        id: "actions",
        header: () => <span className="sr-only">Actions</span>,
        className: "w-12 text-right",
        cell: ({ row }) =>
          canDelete ? (
            <Button
              variant="ghost"
              size="icon-sm"
              className="text-[var(--on-surface-variant)] hover:text-[var(--error)]"
              aria-label={`Remove ${row.original.email ?? row.original.domain} from the suppression list`}
              onClick={() => {
                setDeleteError(null);
                setDeleteTarget(row.original);
              }}
            >
              <Trash2 aria-hidden />
            </Button>
          ) : null,
      },
    ],
    [canDelete],
  );

  return (
    <div className="space-y-3">
      <div className="relative w-full sm:max-w-sm">
        <Search
          className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-[var(--on-surface-variant)]"
          aria-hidden
        />
        <label htmlFor="suppression-search" className="sr-only">
          Search the suppression list
        </label>
        <Input
          id="suppression-search"
          type="search"
          value={searchText}
          onChange={(event) => setSearchText(event.target.value)}
          placeholder="Search addresses and domains"
          className="h-9 bg-white pl-8"
        />
      </div>

      <DataTable<Suppression>
        caption="Suppression list"
        columns={columns}
        data={suppressions.data?.items}
        total={suppressions.data?.total ?? 0}
        page={table.page}
        pageSize={table.pageSize}
        onPageChange={table.setPage}
        isLoading={suppressions.isLoading}
        error={suppressions.error}
        onRetry={() => void suppressions.refetch()}
        emptyState={
          <div className="p-4">
            <EmptyState
              title={urlSearch ? "No matches" : "Your suppression list is empty"}
              description={
                urlSearch
                  ? "Nothing on the list matches that search."
                  : "People who unsubscribe, bounce or ask not to be contacted are added automatically. You can also add addresses or company domains above."
              }
            />
          </div>
        }
      />

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) {
            setDeleteTarget(null);
            setDeleteError(null);
          }
        }}
        title="Remove from the suppression list?"
        description={`${deleteTarget?.email ?? deleteTarget?.domain ?? "This entry"} could be emailed again. Only do this if they've agreed to hear from you.`}
        confirmLabel="Remove"
        destructive
        loading={remove.isPending}
        onConfirm={() => deleteTarget && remove.mutate(deleteTarget.id)}
      >
        {deleteError ? (
          <p role="alert" className="rounded-md bg-[var(--error-container)] px-3 py-2 text-[13px] text-[var(--on-error-container)]">
            {deleteError}
          </p>
        ) : null}
      </ConfirmDialog>
    </div>
  );
}
