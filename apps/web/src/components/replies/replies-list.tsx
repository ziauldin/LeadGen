"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Search, X } from "lucide-react";
import { DataTable, type DataTableColumn } from "@/components/data-table/data-table";
import { EmptyState } from "@/components/shared/empty-state";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import {
  AiLabelMarker,
  ReplyClassificationBadge,
} from "@/components/replies/reply-classification-badge";
import { formatRelative, formatDateTime } from "@/components/replies/format";
import { useTableState } from "@/hooks/use-table-state";
import { campaignsApi, repliesApi } from "@/lib/api/endpoints";
import type { Reply } from "@/lib/api/types";

export const REPLY_TABS: { value: string; label: string; hint: string }[] = [
  { value: "all", label: "All", hint: "No replies yet. Replies to your sent emails show up here." },
  { value: "positive", label: "Positive", hint: "No positive replies yet." },
  { value: "neutral", label: "Neutral", hint: "No neutral replies." },
  { value: "objection", label: "Objection", hint: "No objections. Nice." },
  {
    value: "unsubscribe",
    label: "Unsubscribe",
    hint: "No unsubscribe requests. People who ask are suppressed automatically.",
  },
  { value: "wrong_person", label: "Wrong person", hint: "No wrong-person replies." },
  { value: "out_of_office", label: "Out of office", hint: "No out-of-office messages." },
  { value: "auto_reply", label: "Auto-reply", hint: "No automatic replies." },
  {
    value: "unclassified",
    label: "Unclassified",
    hint: "Everything has a label. New replies without one will appear here.",
  },
  {
    value: "unmatched",
    label: "Unmatched",
    hint: "Every reply is linked to a sent email. Replies we can't link appear here for you to link by hand.",
  },
];

const ALL_CAMPAIGNS = "all";

function useCampaignOptions() {
  return useQuery({
    queryKey: ["campaigns", { limit: 200, sort: "name" }],
    queryFn: () => campaignsApi.list({ limit: 200, sort: "name" }),
    staleTime: 60_000,
  });
}

export function RepliesList() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const table = useTableState({ sort: "-received_at" });
  const classification = table.filters.classification ?? "all";
  const campaignId = table.filters.campaign_id ?? ALL_CAMPAIGNS;
  const [searchText, setSearchText] = useState(table.filters.search ?? "");

  // Debounce typing into the URL (which drives the query).
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

  function clearExtraFilters() {
    setSearchText("");
    const next = new URLSearchParams(searchParams.toString());
    for (const key of ["search", "campaign_id", "page"]) next.delete(key);
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }

  const replies = useQuery({
    queryKey: ["replies", table.apiParams],
    queryFn: () => repliesApi.list(table.apiParams),
    placeholderData: (previous) => previous,
  });
  const campaigns = useCampaignOptions();

  const campaignItems = useMemo(() => {
    const items: Record<string, string> = { [ALL_CAMPAIGNS]: "All campaigns" };
    for (const campaign of campaigns.data?.items ?? []) items[String(campaign.id)] = campaign.name;
    return items;
  }, [campaigns.data]);

  const campaignNames = useMemo(() => {
    const map = new Map<number, string>();
    for (const campaign of campaigns.data?.items ?? []) map.set(campaign.id, campaign.name);
    return map;
  }, [campaigns.data]);

  const columns = useMemo<DataTableColumn<Reply>[]>(
    () => [
      {
        id: "from",
        header: "From",
        className: "min-w-[180px]",
        cell: ({ row }) => (
          <div className="max-w-[220px]">
            <p className="truncate font-medium text-[var(--on-surface)]">{row.original.from_email}</p>
            {row.original.lead_id && row.original.lead_name ? (
              <Link
                href={`/leads/${row.original.lead_id}`}
                onClick={(event) => event.stopPropagation()}
                className="truncate text-[12px] text-[var(--primary)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)] rounded-sm"
              >
                {row.original.lead_name}
              </Link>
            ) : (
              <p className="text-[12px] text-[var(--on-surface-variant)]">
                {row.original.email_message_id ? "Lead not found" : "Not linked to a lead"}
              </p>
            )}
          </div>
        ),
      },
      {
        id: "message",
        header: "Message",
        className: "min-w-[260px]",
        cell: ({ row }) => (
          <div className="max-w-[460px]">
            <Link
              href={`/replies/${row.original.id}`}
              onClick={(event) => event.stopPropagation()}
              className="block truncate font-medium text-[var(--on-surface)] hover:text-[var(--primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)] rounded-sm"
            >
              {row.original.subject || "(no subject)"}
            </Link>
            <p className="line-clamp-1 text-[12px] text-[var(--on-surface-variant)]">
              {row.original.snippet || "(empty message)"}
            </p>
            {row.original.campaign_id ? (
              <p className="mt-0.5 truncate text-[11px] text-[var(--on-surface-variant)]">
                {campaignNames.get(row.original.campaign_id) ?? `Campaign #${row.original.campaign_id}`}
              </p>
            ) : null}
          </div>
        ),
      },
      {
        id: "classification",
        header: "Label",
        sortKey: "classification",
        cell: ({ row }) => (
          <div className="flex flex-wrap items-center gap-1.5">
            <ReplyClassificationBadge classification={row.original.classification} />
            <AiLabelMarker
              classifiedBy={row.original.classified_by}
              confidence={row.original.classification_confidence}
            />
            {!row.original.email_message_id ? (
              <span className="rounded border border-dashed border-[var(--outline)] px-1.5 text-[11px] leading-[16px] text-[var(--on-surface-variant)]">
                Unmatched
              </span>
            ) : null}
          </div>
        ),
      },
      {
        id: "received_at",
        header: "Received",
        sortKey: "received_at",
        className: "whitespace-nowrap",
        cell: ({ row }) => (
          <time
            dateTime={row.original.received_at}
            title={formatDateTime(row.original.received_at)}
            className="text-[var(--on-surface-variant)]"
          >
            {formatRelative(row.original.received_at)}
          </time>
        ),
      },
    ],
    [campaignNames],
  );

  const activeTab = REPLY_TABS.find((tab) => tab.value === classification) ?? REPLY_TABS[0];
  const hasExtraFilters = Boolean(table.filters.search || table.filters.campaign_id);

  return (
    <Tabs
      value={classification}
      onValueChange={(value) =>
        table.setFilter("classification", value === "all" ? undefined : String(value))
      }
      className="gap-4"
    >
      <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
        <TabsList variant="line" aria-label="Filter replies by label" className="w-max">
          {REPLY_TABS.map((tab) => (
            <TabsTrigger key={tab.value} value={tab.value} className="px-2.5 text-[13px]">
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative w-full sm:max-w-sm">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-[var(--on-surface-variant)]"
            aria-hidden
          />
          <label htmlFor="reply-search" className="sr-only">
            Search replies
          </label>
          <Input
            id="reply-search"
            type="search"
            value={searchText}
            onChange={(event) => setSearchText(event.target.value)}
            placeholder="Search sender, subject or message"
            className="h-9 bg-white pl-8"
          />
        </div>
        <div className="flex items-center gap-2">
          <label htmlFor="reply-campaign" className="sr-only">
            Campaign
          </label>
          <Select
            value={campaignId}
            items={campaignItems}
            onValueChange={(value) =>
              table.setFilter(
                "campaign_id",
                !value || value === ALL_CAMPAIGNS ? undefined : String(value),
              )
            }
          >
            <SelectTrigger id="reply-campaign" className="h-9 w-full bg-white sm:w-[220px]">
              <SelectValue placeholder="All campaigns" />
            </SelectTrigger>
            <SelectContent alignItemWithTrigger={false}>
              <SelectItem value={ALL_CAMPAIGNS}>All campaigns</SelectItem>
              {(campaigns.data?.items ?? []).map((campaign) => (
                <SelectItem key={campaign.id} value={String(campaign.id)}>
                  {campaign.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {hasExtraFilters ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={clearExtraFilters}
            >
              <X aria-hidden />
              Clear
            </Button>
          ) : null}
        </div>
      </div>

      <TabsContent value={classification}>
        <DataTable<Reply>
          caption={`Replies: ${activeTab.label}`}
          columns={columns}
          data={replies.data?.items}
          total={replies.data?.total ?? 0}
          page={table.page}
          pageSize={table.pageSize}
          sort={table.sort}
          onPageChange={table.setPage}
          onSortChange={table.setSort}
          isLoading={replies.isLoading}
          error={replies.error}
          onRetry={() => void replies.refetch()}
          onRowClick={(reply) => router.push(`/replies/${reply.id}`)}
          emptyState={
            <div className="p-4">
              <EmptyState
                title={hasExtraFilters ? "No replies match these filters" : "Nothing here yet"}
                description={
                  hasExtraFilters
                    ? "Try a different search or campaign, or clear the filters."
                    : activeTab.hint
                }
              />
            </div>
          }
        />
      </TabsContent>
    </Tabs>
  );
}
