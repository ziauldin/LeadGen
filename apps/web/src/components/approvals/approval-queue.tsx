"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { toast } from "sonner";
import { Check, ChevronLeft, ChevronRight, Inbox, MailCheck, X } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/loading-error";
import { toastBulkResult } from "@/components/data-table/bulk-result";
import { ApprovalList, approvalItemDomId } from "@/components/approvals/approval-list";
import { ApprovalDetail } from "@/components/approvals/approval-detail";
import { RejectDialog } from "@/components/approvals/reject-dialog";
import { RegenerateDialog } from "@/components/approvals/regenerate-dialog";
import { ShortcutHint, ShortcutsDialog } from "@/components/approvals/shortcuts-help";
import { useApprovalShortcuts } from "@/components/approvals/use-approval-shortcuts";
import { useAuth } from "@/hooks/use-auth";
import { useTableState } from "@/hooks/use-table-state";
import { getErrorMessage } from "@/lib/api/client";
import { approvalsApi, campaignsApi, emailsApi, type DraftOptions } from "@/lib/api/endpoints";
import type { ApprovalItem, ApprovalQueue as Queue, GenerationMode } from "@/lib/api/types";
import { cn } from "@/lib/utils";

export const PAGE_SIZE = 50;

const MODE_FILTERS = [
  { value: "all", label: "All" },
  { value: "ai", label: "AI drafts" },
  { value: "template", label: "Template" },
  { value: "template_fallback", label: "AI fallback" },
] as const;

type Selection = { id: number | null; index: number };
type RejectTarget = { ids: number[]; bulk: boolean };

/** Remove reviewed drafts from every cached queue page so the list updates instantly. */
function dropFromQueues(
  queryClient: ReturnType<typeof useQueryClient>,
  ids: number[],
) {
  const gone = new Set(ids);
  queryClient.setQueriesData<Queue>({ queryKey: ["approvals", "queue"] }, (queue) => {
    if (!queue) return queue;
    const items = queue.items.filter((item) => !gone.has(item.id));
    return { ...queue, items, total: Math.max(0, queue.total - (queue.items.length - items.length)) };
  });
}

export function ApprovalQueueView() {
  const queryClient = useQueryClient();
  const { isVerified } = useAuth();
  const table = useTableState({ pageSize: PAGE_SIZE });
  const campaignId = table.filters.campaign_id;
  const mode = table.filters.mode;
  const hasFilters = Boolean(campaignId || mode);

  const params = useMemo(
    () => ({
      skip: table.page * PAGE_SIZE,
      limit: PAGE_SIZE,
      campaign_id: campaignId ? Number(campaignId) : undefined,
      mode: mode || undefined,
    }),
    [table.page, campaignId, mode],
  );
  const queue = useQuery({
    queryKey: ["approvals", "queue", params],
    queryFn: () => approvalsApi.list(params),
    placeholderData: keepPreviousData,
  });
  const campaigns = useQuery({
    queryKey: ["campaigns", { limit: 200 }],
    queryFn: () => campaignsApi.list({ limit: 200 }),
    staleTime: 60_000,
  });

  const items = useMemo(() => queue.data?.items ?? [], [queue.data]);
  const total = queue.data?.total ?? 0;

  // Selection follows an id; when that draft leaves the queue we stay at the same position.
  const [selection, setSelection] = useState<Selection>({ id: null, index: 0 });
  const selectedIndex = useMemo(() => {
    if (!items.length) return -1;
    const found = items.findIndex((item) => item.id === selection.id);
    if (found >= 0) return found;
    return Math.min(selection.index, items.length - 1);
  }, [items, selection]);
  const selected: ApprovalItem | null = selectedIndex >= 0 ? items[selectedIndex] : null;

  const [detailOpen, setDetailOpen] = useState(false); // mobile only
  const [checked, setChecked] = useState<Set<number>>(new Set());
  const [editingId, setEditingId] = useState<number | null>(null);
  const [rejectTarget, setRejectTarget] = useState<RejectTarget | null>(null);
  const [regenerateMode, setRegenerateMode] = useState<GenerationMode | null>(null);
  const [helpOpen, setHelpOpen] = useState(false);
  const editing = selected !== null && editingId === selected.id;

  const select = useCallback((item: ApprovalItem | undefined, index: number) => {
    if (!item) return;
    setSelection({ id: item.id, index });
    setEditingId(null);
  }, []);

  // Keep the selected row visible while moving with j/k.
  const selectedId = selected?.id ?? null;
  useEffect(() => {
    if (selectedId === null) return;
    document.getElementById(approvalItemDomId(selectedId))?.scrollIntoView?.({ block: "nearest" });
  }, [selectedId]);

  // A page emptied by approvals falls back to the previous page.
  useEffect(() => {
    if (queue.isSuccess && !queue.isPlaceholderData && items.length === 0 && table.page > 0) {
      table.setPage(Math.max(0, Math.ceil(total / PAGE_SIZE) - 1));
    }
  }, [queue.isSuccess, queue.isPlaceholderData, items.length, table, total]);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["approvals"] });

  /** After acting on the draft at `index`, select the one that will take its place. */
  const advanceFrom = (index: number) => {
    const next = items[index + 1] ?? items[index - 1];
    setSelection({ id: next?.id ?? null, index });
    setEditingId(null);
  };

  const approve = useMutation({
    mutationFn: (id: number) => emailsApi.approve(id),
    onSuccess: (_data, id) => {
      toast.success("Approved and queued for sending");
      const index = items.findIndex((item) => item.id === id);
      if (index >= 0) advanceFrom(index);
      dropFromQueues(queryClient, [id]);
      setChecked((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
      void invalidate();
    },
  });

  const reject = useMutation({
    mutationFn: ({ ids, reason, bulk }: { ids: number[]; reason: string; bulk: boolean }) =>
      bulk
        ? approvalsApi.bulkReject(ids, reason)
        : emailsApi.reject(ids[0], reason).then(() => null),
    onSuccess: (result, { ids }) => {
      if (result) toastBulkResult(result, "rejected");
      else toast.success("Draft rejected. It won't be sent.");
      if (selected && ids.includes(selected.id)) advanceFrom(selectedIndex);
      dropFromQueues(queryClient, result ? result.results.filter((r) => r.status === "ok").map((r) => r.id) : ids);
      setChecked(new Set());
      setRejectTarget(null);
      void invalidate();
    },
  });

  const bulkApprove = useMutation({
    mutationFn: (ids: number[]) => approvalsApi.bulkApprove(ids),
    onSuccess: (result) => {
      toastBulkResult(result, "approved");
      const done = result.results.filter((r) => r.status === "ok").map((r) => r.id);
      if (selected && done.includes(selected.id)) advanceFrom(selectedIndex);
      dropFromQueues(queryClient, done);
      setChecked(new Set());
      void invalidate();
    },
  });

  const edit = useMutation({
    mutationFn: ({ id, changes }: { id: number; changes: { subject?: string; body?: string } }) =>
      emailsApi.edit(id, changes),
    meta: { silent: true },
    onSuccess: (updated) => {
      queryClient.setQueriesData<Queue>({ queryKey: ["approvals", "queue"] }, (data) =>
        data
          ? { ...data, items: data.items.map((item) => (item.id === updated.id ? updated : item)) }
          : data,
      );
      setEditingId(null);
      toast.success("Changes saved");
      void invalidate();
    },
  });

  const regenerate = useMutation({
    mutationFn: ({ id, options }: { id: number; options: DraftOptions }) =>
      emailsApi.regenerate(id, options),
    meta: { silent: true },
    onSuccess: (message) => {
      setRegenerateMode(null);
      if (message.generation_mode === "template_fallback") {
        toast.warning("Written from the template instead", {
          description: message.generation_note ?? undefined,
        });
      } else {
        toast.success(message.generation_mode === "ai" ? "New AI draft ready" : "Draft rewritten");
      }
      void invalidate();
    },
  });

  const busy =
    approve.isPending || reject.isPending || edit.isPending || regenerate.isPending || bulkApprove.isPending;

  const approveSelected = () => {
    if (!selected || busy) return;
    if (!isVerified) {
      toast.error("Confirm your email address to approve drafts.");
      return;
    }
    if (!selected.can_approve) {
      toast.error("This draft can't be approved yet", {
        description: selected.problems.join(" · "),
      });
      return;
    }
    approve.mutate(selected.id);
  };

  const openReject = () => {
    if (!selected || busy) return;
    setRejectTarget({ ids: [selected.id], bulk: false });
  };

  const startEdit = () => {
    if (!selected || busy) return;
    edit.reset();
    setEditingId(selected.id);
  };

  const openRegenerate = (nextMode: GenerationMode) => {
    regenerate.reset();
    setRegenerateMode(nextMode);
  };

  const dialogOpen = rejectTarget !== null || regenerateMode !== null || helpOpen;
  useApprovalShortcuts(
    {
      next: () => select(items[selectedIndex + 1], selectedIndex + 1),
      previous: () => select(items[selectedIndex - 1], selectedIndex - 1),
      approve: approveSelected,
      reject: openReject,
      edit: startEdit,
      help: () => setHelpOpen(true),
    },
    !editing && !dialogOpen,
  );

  const checkedIds = items.filter((item) => checked.has(item.id)).map((item) => item.id);

  // Campaign filter options: campaigns with drafts waiting, named from the campaign list.
  const campaignOptions = useMemo(() => {
    const names = new Map((campaigns.data?.items ?? []).map((c) => [String(c.id), c.name]));
    const counts = queue.data?.by_campaign ?? {};
    const options = Object.entries(counts)
      .filter(([id]) => id !== "none")
      .map(([id, count]) => ({ value: id, label: `${names.get(id) ?? `Campaign #${id}`} (${count})` }));
    if (campaignId && !options.some((option) => option.value === campaignId)) {
      options.push({ value: campaignId, label: names.get(campaignId) ?? `Campaign #${campaignId}` });
    }
    return options.sort((a, b) => a.label.localeCompare(b.label));
  }, [campaigns.data, queue.data?.by_campaign, campaignId]);
  const campaignItems = useMemo(
    () => ({
      all: "All campaigns",
      ...Object.fromEntries(campaignOptions.map((option) => [option.value, option.label])),
    }),
    [campaignOptions],
  );

  const from = total === 0 ? 0 : table.page * PAGE_SIZE + 1;
  const to = Math.min(total, (table.page + 1) * PAGE_SIZE);
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const filters = (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
      <Select
        value={campaignId ?? "all"}
        items={campaignItems}
        onValueChange={(value) => {
          table.setFilter("campaign_id", !value || value === "all" ? undefined : String(value));
          setChecked(new Set());
        }}
      >
        <SelectTrigger aria-label="Filter by campaign" className="w-full bg-white sm:w-64">
          <SelectValue />
        </SelectTrigger>
        <SelectContent alignItemWithTrigger={false}>
          <SelectItem value="all">All campaigns</SelectItem>
          {campaignOptions.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Tabs
        value={mode ?? "all"}
        onValueChange={(value) => {
          table.setFilter("mode", value === "all" ? undefined : String(value));
          setChecked(new Set());
        }}
        className="max-w-full overflow-x-auto"
      >
        <TabsList aria-label="Filter by how drafts were written">
          {MODE_FILTERS.map((option) => (
            <TabsTrigger key={option.value} value={option.value} className="px-3 text-[13px]">
              {option.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
    </div>
  );

  if (queue.isError && !queue.data) {
    return (
      <div className="grid gap-4">
        {filters}
        <ErrorState error={queue.error} onRetry={() => queue.refetch()} />
      </div>
    );
  }

  if (queue.isPending) {
    return (
      <div className="grid gap-4">
        {filters}
        <div
          role="status"
          aria-label="Loading drafts"
          className="grid gap-4 lg:grid-cols-[minmax(320px,400px)_1fr]"
        >
          <div className="space-y-2 rounded-lg border border-[var(--outline-variant)] bg-white p-3">
            {Array.from({ length: 6 }, (_, i) => (
              <div key={i} className="h-16 animate-pulse rounded bg-[var(--surface-container-high)]/60" />
            ))}
          </div>
          <div className="hidden h-96 animate-pulse rounded-lg border border-[var(--outline-variant)] bg-white lg:block" />
        </div>
      </div>
    );
  }

  if (total === 0 && items.length === 0) {
    return (
      <div className="grid gap-4">
        {hasFilters ? filters : null}
        {hasFilters ? (
          <EmptyState
            title="No drafts match these filters"
            description="Try another campaign or show all drafts."
            action={
              <Button variant="outline" onClick={() => table.clearFilters()}>
                Clear filters
              </Button>
            }
          />
        ) : (
          <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-[var(--outline-variant)] bg-white p-10 text-center">
            <div className="mb-3 flex size-12 items-center justify-center rounded-full bg-[var(--secondary-container)]/50">
              <MailCheck className="size-6 text-[var(--secondary)]" aria-hidden />
            </div>
            <h3 className="text-base font-semibold text-[var(--on-surface)]">
              Nothing waiting for review
            </h3>
            <p className="mt-1 max-w-md text-sm text-[var(--on-surface-variant)]">
              New drafts from your campaigns and Email Studio land here. Nothing is sent until
              someone approves it.
            </p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              <Link href="/campaigns" className={buttonVariants({ variant: "default" })}>
                Go to campaigns
              </Link>
              <Link href="/email-studio" className={buttonVariants({ variant: "outline" })}>
                Write a one-off email
              </Link>
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="grid gap-4">
      {filters}

      {checkedIds.length ? (
        <div
          role="region"
          aria-label="Bulk actions"
          className="sticky top-16 z-[5] flex flex-wrap items-center gap-2 rounded-lg border border-[var(--primary)]/30 bg-[var(--primary-fixed)] px-4 py-2 text-[13px]"
        >
          <span className="font-semibold text-[var(--on-primary-fixed)]">
            {checkedIds.length} selected
          </span>
          <div className="flex flex-1 flex-wrap items-center gap-2">
            <Button
              size="sm"
              onClick={() => bulkApprove.mutate(checkedIds)}
              disabled={!isVerified || busy}
              title={!isVerified ? "Confirm your email address to approve drafts" : undefined}
            >
              <Check aria-hidden />
              {bulkApprove.isPending ? "Approving…" : "Approve selected"}
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="bg-white"
              onClick={() => setRejectTarget({ ids: checkedIds, bulk: true })}
              disabled={busy}
            >
              <X aria-hidden />
              Reject selected
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setChecked(new Set())}>
              Clear
            </Button>
          </div>
          {!isVerified ? (
            <p className="w-full text-xs text-[var(--on-primary-fixed)]">
              Confirm your email address to approve drafts. You can still reject them.
            </p>
          ) : (
            <p className="w-full text-xs text-[var(--on-primary-fixed)]/80">
              Drafts with compliance problems are skipped and listed in the result.
            </p>
          )}
        </div>
      ) : null}

      <div className="grid items-start gap-4 lg:grid-cols-[minmax(320px,400px)_1fr]">
        {/* List */}
        <section
          aria-label="Review queue"
          className={cn(
            "overflow-hidden rounded-lg border border-[var(--outline-variant)] bg-white lg:sticky lg:top-20 lg:block",
            detailOpen && "hidden",
          )}
        >
          <div className="lg:max-h-[calc(100vh-15rem)] lg:overflow-y-auto">
            <ApprovalList
              items={items}
              selectedId={selected?.id ?? null}
              onSelect={(item) => {
                select(item, items.indexOf(item));
                setDetailOpen(true);
              }}
              checked={checked}
              onToggle={(id) =>
                setChecked((prev) => {
                  const next = new Set(prev);
                  if (next.has(id)) next.delete(id);
                  else next.add(id);
                  return next;
                })
              }
              onToggleAll={(all) =>
                setChecked(all ? new Set(items.map((item) => item.id)) : new Set())
              }
            />
          </div>
          <nav
            aria-label="Queue pages"
            className="flex items-center justify-between gap-2 border-t border-[var(--outline-variant)] px-3 py-2 text-xs text-[var(--on-surface-variant)]"
          >
            <span>
              {from}–{to} of {total}
            </span>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label="Previous page"
                disabled={table.page === 0 || queue.isFetching}
                onClick={() => table.setPage(table.page - 1)}
              >
                <ChevronLeft aria-hidden />
              </Button>
              <span>
                Page {table.page + 1} of {pageCount}
              </span>
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label="Next page"
                disabled={table.page + 1 >= pageCount || queue.isFetching}
                onClick={() => table.setPage(table.page + 1)}
              >
                <ChevronRight aria-hidden />
              </Button>
            </div>
          </nav>
        </section>

        {/* Detail */}
        <section
          aria-label="Selected draft"
          className={cn(
            "min-w-0 overflow-hidden rounded-lg border border-[var(--outline-variant)] bg-white lg:block",
            !detailOpen && "hidden",
          )}
        >
          {selected ? (
            <ApprovalDetail
              item={selected}
              index={selectedIndex}
              count={items.length}
              onPrevious={() => select(items[selectedIndex - 1], selectedIndex - 1)}
              onNext={() => select(items[selectedIndex + 1], selectedIndex + 1)}
              onBack={() => setDetailOpen(false)}
              isVerified={isVerified}
              onApprove={approveSelected}
              approving={approve.isPending}
              onReject={openReject}
              editing={editing}
              onEditStart={startEdit}
              onEditCancel={() => setEditingId(null)}
              onEditSave={(changes) => edit.mutate({ id: selected.id, changes })}
              saving={edit.isPending}
              saveError={edit.error ? getErrorMessage(edit.error) : null}
              onRegenerate={openRegenerate}
              busy={busy}
            />
          ) : (
            <div className="flex flex-col items-center justify-center p-12 text-center text-sm text-[var(--on-surface-variant)]">
              <Inbox className="mb-2 size-8" aria-hidden />
              Choose a draft to review it.
            </div>
          )}
        </section>
      </div>

      <ShortcutHint onShowAll={() => setHelpOpen(true)} />

      <RejectDialog
        open={rejectTarget !== null}
        onOpenChange={(open) => !open && setRejectTarget(null)}
        count={rejectTarget?.ids.length ?? 1}
        loading={reject.isPending}
        onConfirm={(reason) =>
          rejectTarget && reject.mutate({ ids: rejectTarget.ids, reason, bulk: rejectTarget.bulk })
        }
      />
      <RegenerateDialog
        mode={regenerateMode}
        onOpenChange={(open) => !open && setRegenerateMode(null)}
        defaultTemplateId={selected?.template_id}
        loading={regenerate.isPending}
        error={regenerate.error ? getErrorMessage(regenerate.error) : null}
        onConfirm={(options) => selected && regenerate.mutate({ id: selected.id, options })}
      />
      <ShortcutsDialog open={helpOpen} onOpenChange={setHelpOpen} />
    </div>
  );
}
