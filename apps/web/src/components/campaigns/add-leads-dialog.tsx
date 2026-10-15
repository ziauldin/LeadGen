"use client";

import { useEffect, useId, useState } from "react";
import Link from "next/link";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  ArrowRight,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CircleSlash,
  Search,
  XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ErrorState } from "@/components/shared/loading-error";
import { campaignsApi, leadsApi } from "@/lib/api/endpoints";
import type { AddLeadsResult, Campaign, Lead } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 20;
const MAX_LEADS = 500;
const BLOCKED_STATUSES: Record<string, string> = {
  opted_out: "Opted out",
  disqualified: "Disqualified",
};

function useDebounced<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

/** Per-lead outcome of adding leads to a campaign. */
export function AddLeadsResults({
  result,
  leadNames,
  campaignId,
}: {
  result: AddLeadsResult;
  leadNames: Map<number, string>;
  campaignId: number;
}) {
  const ok = result.results.filter((item) => item.status === "ok").length;
  const skipped = result.results.filter((item) => item.status === "skipped").length;
  const failed = result.results.filter((item) => item.status === "failed").length;
  const created = result.created ?? ok;
  // Problems first, so the user sees what needs attention without scrolling.
  const order = { failed: 0, skipped: 1, ok: 2 } as const;
  const rows = [...result.results].sort((a, b) => order[a.status] - order[b.status]);

  return (
    <div className="space-y-4">
      <div role="group" className="grid grid-cols-3 gap-2" aria-label="Summary">
        <SummaryTile label="Drafts created" value={created} tone="good" />
        <SummaryTile label="Skipped" value={skipped} tone={skipped ? "warn" : "neutral"} />
        <SummaryTile label="Failed" value={failed} tone={failed ? "bad" : "neutral"} />
      </div>

      {created > 0 ? (
        <div className="flex flex-col gap-2 rounded-lg border border-[var(--secondary)]/30 bg-[var(--secondary-fixed)]/40 p-3 text-[13px] text-[var(--on-surface)] sm:flex-row sm:items-center">
          <p className="flex-1">
            {created === 1 ? "1 draft is" : `${created} drafts are`} waiting for approval. Nothing
            sends until someone approves it.
          </p>
          <Link
            href={`/approvals?campaign_id=${campaignId}`}
            className="inline-flex items-center gap-1 rounded font-semibold text-[var(--primary)] outline-none hover:underline focus-visible:ring-2 focus-visible:ring-[var(--primary)]"
          >
            Review in Approvals
            <ArrowRight className="size-3.5" aria-hidden />
          </Link>
        </div>
      ) : null}

      {rows.length > 0 ? (
        <ul
          aria-label="Results for each lead"
          className="max-h-72 divide-y divide-[var(--outline-variant)] overflow-y-auto rounded-lg border border-[var(--outline-variant)]"
        >
          {rows.map((item) => {
            const Icon =
              item.status === "ok" ? CheckCircle2 : item.status === "skipped" ? CircleSlash : XCircle;
            const statusLabel =
              item.status === "ok" ? "Added" : item.status === "skipped" ? "Skipped" : "Failed";
            return (
              <li key={item.id} className="flex items-start gap-2.5 px-3 py-2.5 text-[13px]">
                <Icon
                  className={cn(
                    "mt-0.5 size-4 shrink-0",
                    item.status === "ok" && "text-[var(--secondary)]",
                    item.status === "skipped" && "text-[var(--tertiary)]",
                    item.status === "failed" && "text-[var(--error)]",
                  )}
                  aria-hidden
                />
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-[var(--on-surface)]">
                    {leadNames.get(item.id) ?? `Lead #${item.id}`}
                    <span className="sr-only"> – {statusLabel}</span>
                  </p>
                  <p className="text-[12px] text-[var(--on-surface-variant)]">
                    <span className="font-medium">{statusLabel}</span>
                    {item.detail ? ` · ${item.detail}` : null}
                  </p>
                </div>
              </li>
            );
          })}
        </ul>
      ) : result.errors.length > 0 ? (
        <ul className="list-disc space-y-1 pl-5 text-[13px] text-[var(--error)]">
          {result.errors.map((error) => (
            <li key={error}>{error}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function SummaryTile({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "good" | "warn" | "bad" | "neutral";
}) {
  return (
    <div
      className={cn(
        "rounded-lg border px-3 py-2",
        tone === "good" && "border-[var(--secondary)]/30 bg-[var(--secondary-fixed)]/30",
        tone === "warn" && "border-[var(--tertiary)]/30 bg-[var(--tertiary-fixed)]/50",
        tone === "bad" && "border-[var(--error)]/30 bg-[var(--error-container)]/50",
        tone === "neutral" && "border-[var(--outline-variant)] bg-white",
      )}
    >
      <p className="text-[20px] leading-[28px] font-semibold text-[var(--on-surface)]">{value}</p>
      <p className="text-[12px] text-[var(--on-surface-variant)]">{label}</p>
    </div>
  );
}

/** Pick leads from the campaign's niche and enroll them (creates step-1 drafts). */
export function AddLeadsDialog({
  campaign,
  open,
  onOpenChange,
}: {
  campaign: Pick<Campaign, "id" | "niche_id" | "name">;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto sm:max-w-2xl">
        {open ? <AddLeadsBody campaign={campaign} onClose={() => onOpenChange(false)} /> : null}
      </DialogContent>
    </Dialog>
  );
}

function AddLeadsBody({
  campaign,
  onClose,
}: {
  campaign: Pick<Campaign, "id" | "niche_id" | "name">;
  onClose: () => void;
}) {
  const uid = useId();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<Map<number, Lead>>(new Map());
  const [result, setResult] = useState<AddLeadsResult | null>(null);
  const [submittedNames, setSubmittedNames] = useState<Map<number, string>>(new Map());
  const debouncedSearch = useDebounced(search.trim());

  const params = {
    niche_id: campaign.niche_id,
    search: debouncedSearch || undefined,
    has_email: true,
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
  };
  const leads = useQuery({
    queryKey: ["leads", "campaign-picker", params],
    queryFn: () => leadsApi.list(params),
    placeholderData: keepPreviousData,
    enabled: result === null,
  });

  const add = useMutation({
    mutationFn: (ids: number[]) => campaignsApi.addLeads(campaign.id, ids),
    onSuccess: (data) => {
      setSubmittedNames(new Map([...selected.values()].map((lead) => [lead.id, lead.full_name])));
      setResult(data);
      setSelected(new Map());
      queryClient.invalidateQueries({ queryKey: ["campaign", campaign.id] });
      queryClient.invalidateQueries({ queryKey: ["campaigns"] });
      queryClient.invalidateQueries({ queryKey: ["approvals"] });
      if (data.created > 0) {
        toast.success(
          `${data.created} ${data.created === 1 ? "lead" : "leads"} added`,
          data.skipped ? { description: `${data.skipped} skipped – see the details.` } : undefined,
        );
      } else {
        toast.warning("No leads were added", { description: "See the reasons for each lead." });
      }
    },
  });

  const items = leads.data?.items ?? [];
  const total = leads.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const selectable = items.filter((lead) => !BLOCKED_STATUSES[lead.status]);
  const allOnPage = selectable.length > 0 && selectable.every((lead) => selected.has(lead.id));
  const someOnPage = selectable.some((lead) => selected.has(lead.id));
  const atLimit = selected.size >= MAX_LEADS;

  function toggle(lead: Lead) {
    setSelected((current) => {
      const next = new Map(current);
      if (next.has(lead.id)) next.delete(lead.id);
      else if (next.size < MAX_LEADS) next.set(lead.id, lead);
      return next;
    });
  }

  function togglePage() {
    setSelected((current) => {
      const next = new Map(current);
      if (allOnPage) selectable.forEach((lead) => next.delete(lead.id));
      else
        for (const lead of selectable) {
          if (next.size >= MAX_LEADS) break;
          next.set(lead.id, lead);
        }
      return next;
    });
  }

  if (result) {
    return (
      <>
        <DialogHeader>
          <DialogTitle>Leads added to {campaign.name}</DialogTitle>
          <DialogDescription>
            Each added lead gets a step 1 draft. Follow-ups are drafted later, when they come due.
          </DialogDescription>
        </DialogHeader>
        <AddLeadsResults result={result} leadNames={submittedNames} campaignId={campaign.id} />
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => {
              setResult(null);
              add.reset();
            }}
          >
            Add more leads
          </Button>
          <Button onClick={onClose}>Done</Button>
        </DialogFooter>
      </>
    );
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>Add leads to {campaign.name}</DialogTitle>
        <DialogDescription>
          Showing leads with an email address in this campaign&apos;s niche. We&apos;ll draft step 1
          for each one; nothing sends until it&apos;s approved.
        </DialogDescription>
      </DialogHeader>

      <div className="relative">
        <label htmlFor={`${uid}-search`} className="sr-only">
          Search leads
        </label>
        <Search
          className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-[var(--on-surface-variant)]"
          aria-hidden
        />
        <Input
          id={`${uid}-search`}
          type="search"
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(0);
          }}
          placeholder="Search by name, job title or company"
          className="h-9 bg-white pl-8 text-[13px]"
        />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 text-[13px]">
        <label className="inline-flex cursor-pointer items-center gap-2 font-medium">
          <input
            type="checkbox"
            className="size-4 cursor-pointer accent-[var(--primary)]"
            checked={allOnPage}
            ref={(element) => {
              if (element) element.indeterminate = !allOnPage && someOnPage;
            }}
            disabled={selectable.length === 0}
            onChange={togglePage}
          />
          Select all on this page
        </label>
        <p aria-live="polite" className="text-[var(--on-surface-variant)]">
          {selected.size} selected
          {atLimit ? ` (maximum ${MAX_LEADS} at a time)` : ""}
        </p>
      </div>

      {leads.error ? (
        <ErrorState error={leads.error} onRetry={() => leads.refetch()} />
      ) : (
        <div
          className={cn(
            "max-h-[45dvh] overflow-y-auto rounded-lg border border-[var(--outline-variant)]",
            leads.isFetching && "opacity-70",
          )}
          aria-busy={leads.isFetching}
        >
          {leads.isLoading ? (
            <ul aria-label="Loading leads">
              {Array.from({ length: 5 }).map((_, index) => (
                <li key={index} className="flex items-center gap-3 border-b border-[var(--outline-variant)] px-3 py-3 last:border-0">
                  <div className="size-4 animate-pulse rounded bg-[var(--surface-container-high)]" />
                  <div className="h-4 flex-1 animate-pulse rounded bg-[var(--surface-container-high)]" />
                </li>
              ))}
            </ul>
          ) : items.length === 0 ? (
            <div className="px-4 py-10 text-center">
              <p className="text-[14px] font-medium text-[var(--on-surface)]">
                {debouncedSearch ? "No leads match your search" : "No leads with an email in this niche yet"}
              </p>
              <p className="mt-1 text-[13px] text-[var(--on-surface-variant)]">
                {debouncedSearch ? (
                  "Try a different name, job title or company."
                ) : (
                  <>
                    Find or import leads first, then come back.{" "}
                    <Link
                      href={`/search?niche_id=${campaign.niche_id}`}
                      className="font-medium text-[var(--primary)] underline"
                    >
                      Find leads
                    </Link>
                  </>
                )}
              </p>
            </div>
          ) : (
            <ul aria-label="Leads">
              {items.map((lead) => {
                const blocked = BLOCKED_STATUSES[lead.status];
                const checked = selected.has(lead.id);
                return (
                  <li key={lead.id} className="border-b border-[var(--outline-variant)] last:border-0">
                    <label
                      className={cn(
                        "flex items-center gap-3 px-3 py-2.5 text-[13px]",
                        blocked ? "cursor-not-allowed opacity-60" : "cursor-pointer hover:bg-[var(--surface-container-low)]",
                        checked && "bg-[var(--primary-fixed)]/50",
                      )}
                    >
                      <input
                        type="checkbox"
                        className="size-4 shrink-0 cursor-pointer accent-[var(--primary)]"
                        checked={checked}
                        disabled={Boolean(blocked) || (!checked && atLimit)}
                        onChange={() => toggle(lead)}
                        aria-label={`Select ${lead.full_name}`}
                      />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-medium text-[var(--on-surface)]">
                          {lead.full_name}
                          {lead.company?.name ? (
                            <span className="font-normal text-[var(--on-surface-variant)]"> · {lead.company.name}</span>
                          ) : null}
                        </span>
                        <span className="block truncate text-[12px] text-[var(--on-surface-variant)]">
                          {lead.primary_email ?? "No email"}
                          {lead.job_title ? ` · ${lead.job_title}` : ""}
                        </span>
                      </span>
                      {blocked ? (
                        <span className="shrink-0 rounded-full bg-[var(--error-container)] px-2 py-0.5 text-[11px] font-semibold text-[var(--on-error-container)]">
                          {blocked}
                        </span>
                      ) : null}
                    </label>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}

      {total > PAGE_SIZE ? (
        <div className="flex items-center justify-between text-[13px] text-[var(--on-surface-variant)]">
          <span>
            Page {page + 1} of {pageCount} · {total.toLocaleString()} leads
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((current) => current - 1)}
              disabled={page === 0 || leads.isFetching}
              aria-label="Previous page of leads"
            >
              <ChevronLeft aria-hidden />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((current) => current + 1)}
              disabled={page + 1 >= pageCount || leads.isFetching}
              aria-label="Next page of leads"
            >
              <ChevronRight aria-hidden />
            </Button>
          </div>
        </div>
      ) : null}

      <DialogFooter>
        <Button variant="outline" onClick={onClose} disabled={add.isPending}>
          Cancel
        </Button>
        <Button
          onClick={() => add.mutate([...selected.keys()])}
          disabled={selected.size === 0 || add.isPending}
        >
          {add.isPending
            ? "Adding…"
            : selected.size === 0
              ? "Add leads"
              : `Add ${selected.size} ${selected.size === 1 ? "lead" : "leads"}`}
        </Button>
      </DialogFooter>
    </>
  );
}
