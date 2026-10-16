"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Download, Search } from "lucide-react";
import { DataTable, type DataTableColumn } from "@/components/data-table/data-table";
import { EmptyState } from "@/components/shared/empty-state";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useTableState } from "@/hooks/use-table-state";
import { auditApi, workspacesApi } from "@/lib/api/endpoints";
import type { components } from "@/lib/api/schema";

type Entry = components["schemas"]["AuditEntry"];

function formatTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "—"
    : date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

/** "member_role_changed" / "role.created" → "Member role changed" / "Role created". */
export function describeAction(action: string) {
  const words = action.replace(/[._]/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function Details({ metadata }: { metadata: Entry["metadata"] }) {
  if (!metadata || !Object.keys(metadata).length) return <span>—</span>;
  return (
    <span className="line-clamp-2 break-all font-mono text-[12px]" title={JSON.stringify(metadata)}>
      {Object.entries(metadata)
        .map(([key, value]) => `${key}: ${typeof value === "object" ? JSON.stringify(value) : String(value)}`)
        .join(" · ")}
    </span>
  );
}

export function AuditLogTable() {
  const table = useTableState({ pageSize: 50 });
  const urlAction = table.filters.action ?? "";
  const [actionText, setActionText] = useState(urlAction);
  const setFilterRef = useRef(table.setFilter);
  useEffect(() => {
    setFilterRef.current = table.setFilter;
  });
  useEffect(() => {
    if (actionText.trim() === urlAction) return;
    const timer = window.setTimeout(() => setFilterRef.current("action", actionText.trim() || undefined), 350);
    return () => window.clearTimeout(timer);
  }, [actionText, urlAction]);

  const filters = {
    action: urlAction || undefined,
    actor_id: table.filters.actor_id || undefined,
    since: table.filters.since ? `${table.filters.since}T00:00:00` : undefined,
    until: table.filters.until ? `${table.filters.until}T23:59:59` : undefined,
  };
  const params = { skip: table.apiParams.skip, limit: table.apiParams.limit, ...filters };
  const logs = useQuery({
    queryKey: ["audit-logs", params],
    queryFn: () => auditApi.list(params),
    placeholderData: (previous) => previous,
  });
  const members = useQuery({ queryKey: ["members"], queryFn: workspacesApi.members });
  const exportCsv = useMutation({ mutationFn: () => auditApi.exportCsv(filters) });

  const actorItems = useMemo(
    () => ({
      all: "Everyone",
      ...Object.fromEntries((members.data ?? []).map((m) => [String(m.user_id), m.name])),
    }),
    [members.data],
  );

  const columns = useMemo<DataTableColumn<Entry>[]>(
    () => [
      {
        id: "created_at",
        header: "When",
        className: "whitespace-nowrap",
        cell: ({ row }) => (
          <span className="text-[var(--on-surface-variant)]">{formatTime(row.original.created_at)}</span>
        ),
      },
      {
        id: "actor",
        header: "Who",
        cell: ({ row }) => (
          <div className="min-w-[140px]">
            <p className="font-medium text-[var(--on-surface)]">{row.original.actor_name ?? "System"}</p>
            {row.original.actor_email ? (
              <p className="text-[12px] text-[var(--on-surface-variant)]">{row.original.actor_email}</p>
            ) : null}
          </div>
        ),
      },
      {
        id: "action",
        header: "What",
        cell: ({ row }) => (
          <div className="min-w-[160px]">
            <p className="text-[var(--on-surface)]" title={row.original.action}>
              {describeAction(row.original.action)}
            </p>
            <p className="text-[12px] text-[var(--on-surface-variant)]">
              {row.original.entity_type}
              {row.original.entity_id ? ` #${row.original.entity_id}` : ""}
            </p>
          </div>
        ),
      },
      {
        id: "details",
        header: "Details",
        className: "hidden lg:table-cell max-w-[320px] text-[var(--on-surface-variant)]",
        cell: ({ row }) => <Details metadata={row.original.metadata} />,
      },
    ],
    [],
  );

  const filtered = Boolean(urlAction || table.filters.actor_id || table.filters.since || table.filters.until);

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-end">
        <div className="relative w-full sm:max-w-[220px]">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-[var(--on-surface-variant)]"
            aria-hidden
          />
          <label htmlFor="audit-action" className="sr-only">
            Filter by action
          </label>
          <Input
            id="audit-action"
            type="search"
            value={actionText}
            onChange={(event) => setActionText(event.target.value)}
            placeholder="Action, e.g. member"
            className="h-9 bg-white pl-8"
          />
        </div>
        <Select
          value={table.filters.actor_id ?? "all"}
          items={actorItems}
          onValueChange={(value) => table.setFilter("actor_id", !value || value === "all" ? undefined : String(value))}
        >
          <SelectTrigger className="h-9 w-full bg-white sm:w-[180px]" aria-label="Filter by person">
            <SelectValue />
          </SelectTrigger>
          <SelectContent alignItemWithTrigger={false}>
            {Object.entries(actorItems).map(([value, label]) => (
              <SelectItem key={value} value={value}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="flex gap-2">
          <div className="grid gap-1">
            <label htmlFor="audit-since" className="text-[12px] text-[var(--on-surface-variant)]">
              From
            </label>
            <Input
              id="audit-since"
              type="date"
              className="h-9 bg-white"
              value={table.filters.since ?? ""}
              onChange={(event) => table.setFilter("since", event.target.value || undefined)}
            />
          </div>
          <div className="grid gap-1">
            <label htmlFor="audit-until" className="text-[12px] text-[var(--on-surface-variant)]">
              To
            </label>
            <Input
              id="audit-until"
              type="date"
              className="h-9 bg-white"
              value={table.filters.until ?? ""}
              onChange={(event) => table.setFilter("until", event.target.value || undefined)}
            />
          </div>
        </div>
        <div className="flex gap-2 sm:ml-auto">
          {filtered ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setActionText("");
                table.clearFilters();
              }}
            >
              Clear filters
            </Button>
          ) : null}
          <Button variant="outline" size="sm" disabled={exportCsv.isPending} onClick={() => exportCsv.mutate()}>
            <Download aria-hidden /> {exportCsv.isPending ? "Exporting…" : "Export CSV"}
          </Button>
        </div>
      </div>

      <DataTable<Entry>
        caption="Audit log"
        columns={columns}
        data={logs.data?.items}
        total={logs.data?.total ?? 0}
        page={table.page}
        pageSize={table.pageSize}
        onPageChange={table.setPage}
        isLoading={logs.isLoading}
        error={logs.error}
        onRetry={() => void logs.refetch()}
        emptyState={
          <div className="p-4">
            <EmptyState
              title={filtered ? "No matching activity" : "No activity yet"}
              description={
                filtered
                  ? "Nothing in the audit log matches these filters."
                  : "Changes to members, roles, settings, sending accounts and sign-in methods show up here."
              }
            />
          </div>
        }
      />
      {logs.data ? (
        <p className="text-[12px] text-[var(--on-surface-variant)]">
          Your plan keeps {logs.data.retention_days} days of activity.
        </p>
      ) : null}
    </div>
  );
}
