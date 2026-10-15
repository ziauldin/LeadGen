"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
  type RowSelectionState,
} from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/shared/loading-error";
import { cn } from "@/lib/utils";

export type DataTableColumn<T> = ColumnDef<T> & {
  /** API sort key; when set the header becomes a sort toggle. */
  sortKey?: string;
  className?: string;
};

type Props<T extends { id: number }> = {
  columns: DataTableColumn<T>[];
  data: T[] | undefined;
  total: number;
  page: number;
  pageSize: number;
  sort?: string;
  onPageChange: (page: number) => void;
  onSortChange?: (sort: string | undefined) => void;
  isLoading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  emptyState?: ReactNode;
  /** Enables row checkboxes; renders the returned node in a bar while rows are selected. */
  bulkActions?: (selectedIds: number[], clear: () => void) => ReactNode;
  onRowClick?: (row: T) => void;
  caption?: string;
};

function SortIcon({ direction }: { direction: "asc" | "desc" | null }) {
  if (direction === "asc") return <ArrowUp className="size-3" aria-hidden />;
  if (direction === "desc") return <ArrowDown className="size-3" aria-hidden />;
  return <ArrowUpDown className="size-3 opacity-40" aria-hidden />;
}

/** Server-driven table: the API pages and sorts; this renders, selects and paginates. */
export function DataTable<T extends { id: number }>({
  columns,
  data,
  total,
  page,
  pageSize,
  sort,
  onPageChange,
  onSortChange,
  isLoading,
  error,
  onRetry,
  emptyState,
  bulkActions,
  onRowClick,
  caption,
}: Props<T>) {
  const [selection, setSelection] = useState<RowSelectionState>({});
  const rows = useMemo(() => data ?? [], [data]);

  // A new page or filter starts with nothing selected.
  useEffect(() => setSelection({}), [page, pageSize, sort, total]);

  const allColumns = useMemo<DataTableColumn<T>[]>(() => {
    if (!bulkActions) return columns;
    const select: DataTableColumn<T> = {
      id: "__select",
      className: "w-10",
      header: ({ table }) => (
        <input
          type="checkbox"
          aria-label="Select all rows on this page"
          className="size-4 cursor-pointer accent-[var(--primary)]"
          checked={table.getIsAllPageRowsSelected()}
          ref={(el) => {
            if (el) el.indeterminate = table.getIsSomePageRowsSelected();
          }}
          onChange={table.getToggleAllPageRowsSelectedHandler()}
        />
      ),
      cell: ({ row }) => (
        <input
          type="checkbox"
          aria-label={`Select row ${row.index + 1}`}
          className="size-4 cursor-pointer accent-[var(--primary)]"
          checked={row.getIsSelected()}
          onChange={row.getToggleSelectedHandler()}
          onClick={(event) => event.stopPropagation()}
        />
      ),
    };
    return [select, ...columns];
  }, [bulkActions, columns]);

  const table = useReactTable({
    data: rows,
    columns: allColumns,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (row) => String(row.id),
    manualPagination: true,
    manualSorting: true,
    enableRowSelection: Boolean(bulkActions),
    state: { rowSelection: selection },
    onRowSelectionChange: setSelection,
  });

  const selectedIds = Object.keys(selection)
    .filter((key) => selection[key])
    .map(Number);
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : page * pageSize + 1;
  const to = Math.min(total, (page + 1) * pageSize);

  function sortState(key?: string): "asc" | "desc" | null {
    if (!key || !sort) return null;
    const first = sort.split(",")[0];
    if (first === key) return "asc";
    if (first === `-${key}`) return "desc";
    return null;
  }

  function toggleSort(key: string) {
    const current = sortState(key);
    onSortChange?.(current === null ? key : current === "asc" ? `-${key}` : undefined);
  }

  if (error) return <ErrorState error={error} onRetry={onRetry} />;

  return (
    <div className="space-y-3">
      {bulkActions && selectedIds.length > 0 && (
        <div
          role="region"
          aria-label="Bulk actions"
          className="sticky top-16 z-[5] flex flex-wrap items-center gap-2 rounded-lg border border-[var(--primary)]/30 bg-[var(--primary-container)] px-4 py-2 text-[13px]"
        >
          <span className="font-semibold text-[var(--on-primary-container)]">
            {selectedIds.length} selected
          </span>
          <div className="flex flex-1 flex-wrap items-center gap-2">
            {bulkActions(selectedIds, () => setSelection({}))}
          </div>
          <Button variant="ghost" size="sm" onClick={() => setSelection({})}>
            Clear
          </Button>
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border border-[var(--outline-variant)] bg-white">
        <Table>
          {caption ? <caption className="sr-only">{caption}</caption> : null}
          <TableHeader>
            {table.getHeaderGroups().map((group) => (
              <TableRow key={group.id}>
                {group.headers.map((header) => {
                  const column = header.column.columnDef as DataTableColumn<T>;
                  const direction = sortState(column.sortKey);
                  const content = header.isPlaceholder
                    ? null
                    : flexRender(column.header, header.getContext());
                  return (
                    <TableHead
                      key={header.id}
                      className={column.className}
                      aria-sort={
                        direction === "asc"
                          ? "ascending"
                          : direction === "desc"
                            ? "descending"
                            : undefined
                      }
                    >
                      {column.sortKey && onSortChange ? (
                        <button
                          type="button"
                          onClick={() => toggleSort(column.sortKey!)}
                          className="inline-flex items-center gap-1 font-medium hover:text-[var(--primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)]"
                        >
                          {content}
                          <SortIcon direction={direction} />
                        </button>
                      ) : (
                        content
                      )}
                    </TableHead>
                  );
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {isLoading && rows.length === 0 ? (
              Array.from({ length: 5 }).map((_, index) => (
                <TableRow key={`skeleton-${index}`}>
                  {allColumns.map((_column, cell) => (
                    <TableCell key={cell}>
                      <div className="h-4 animate-pulse rounded bg-[var(--surface-container-high)]" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={allColumns.length} className="p-0">
                  {emptyState ?? (
                    <p className="p-8 text-center text-sm text-muted-foreground">No results.</p>
                  )}
                </TableCell>
              </TableRow>
            ) : (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-state={row.getIsSelected() ? "selected" : undefined}
                  className={cn("group", onRowClick && "cursor-pointer")}
                  onClick={onRowClick ? () => onRowClick(row.original) : undefined}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell
                      key={cell.id}
                      className={(cell.column.columnDef as DataTableColumn<T>).className}
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex flex-col items-center justify-between gap-2 text-[13px] text-[var(--on-surface-variant)] sm:flex-row">
        <p aria-live="polite">
          {total === 0 ? "No results" : `Showing ${from}–${to} of ${total.toLocaleString()}`}
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(page - 1)}
            disabled={page === 0 || isLoading}
            aria-label="Previous page"
          >
            <ChevronLeft className="size-4" aria-hidden />
          </Button>
          <span>
            Page {page + 1} of {pageCount}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(page + 1)}
            disabled={page + 1 >= pageCount || isLoading}
            aria-label="Next page"
          >
            <ChevronRight className="size-4" aria-hidden />
          </Button>
        </div>
      </div>
    </div>
  );
}
