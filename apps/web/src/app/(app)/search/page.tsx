"use client";

import { Suspense, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  CheckCircle2,
  Info,
  Loader2,
  Play,
  Save,
  Search,
  Sparkles,
  Trash2,
} from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { ButtonLink } from "@/components/ui/button-link";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState, LoadingState } from "@/components/shared/loading-error";
import { SelectField } from "@/components/leads/filter-controls";
import {
  SearchResultsTable,
  toResultRows,
} from "@/components/search/search-results-table";
import { nichesApi, providerSettingsApi, searchesApi } from "@/lib/api/endpoints";
import type { SearchQuery } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const PROVIDER_LABELS: Record<string, string> = {
  mock: "Mock (sample data)",
  google_cse: "Google Custom Search",
  bing: "Bing",
  serpapi: "SerpAPI",
};
const providerLabel = (name: string) => PROVIDER_LABELS[name] ?? name;

function Step({
  number,
  title,
  children,
  className,
}: {
  number: number;
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      aria-labelledby={`search-step-${number}`}
      className={cn(
        "rounded-lg border border-[var(--outline-variant)] bg-white p-5 shadow-sm",
        className,
      )}
    >
      <h3
        id={`search-step-${number}`}
        className="mb-3 flex items-center gap-2 text-[14px] font-semibold text-[var(--on-surface)]"
      >
        <span
          className="flex size-5 items-center justify-center rounded-full bg-[var(--primary)] text-[11px] font-bold text-white"
          aria-hidden
        >
          {number}
        </span>
        {title}
      </h3>
      {children}
    </section>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<LoadingState message="Loading search…" />}>
      <SearchView />
    </Suspense>
  );
}

function SearchView() {
  const params = useSearchParams();
  const queryClient = useQueryClient();

  const [rawNicheId, setNicheId] = useState(params.get("niche_id") ?? "");
  const [queries, setQueries] = useState<string[]>([]);
  const [showAll, setShowAll] = useState(false);
  const [query, setQuery] = useState("");
  const [provider, setProvider] = useState<string | null>(null);
  const [search, setSearch] = useState<SearchQuery | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [saved, setSaved] = useState<{ created: number; skipped: number } | null>(null);

  const niches = useQuery({
    queryKey: ["niches", { limit: 200 }],
    queryFn: () => nichesApi.list({ limit: 200 }),
  });
  const providers = useQuery({
    queryKey: ["provider-settings"],
    queryFn: providerSettingsApi.list,
  });

  const providerOptions = useMemo(() => {
    const configured = (providers.data?.items ?? []).filter(
      (credential) =>
        credential.provider_type === "search" &&
        (credential.status === "configured" || credential.is_active),
    );
    const options = configured.map((credential) => ({
      value: credential.provider_name,
      label: `${credential.display_name || providerLabel(credential.provider_name)}${credential.is_active ? " (active)" : ""}`,
    }));
    if (!options.some((option) => option.value === "mock")) {
      options.push({ value: "mock", label: providerLabel("mock") });
    }
    return options;
  }, [providers.data]);

  const activeProvider = useMemo(
    () =>
      providers.data?.items.find((c) => c.provider_type === "search" && c.is_active)
        ?.provider_name ?? "mock",
    [providers.data],
  );
  const selectedProvider = provider ?? activeProvider;

  // A niche id from the URL only counts once we know it exists in this workspace.
  const nicheId =
    rawNicheId && niches.data && !niches.data.items.some((n) => String(n.id) === rawNicheId)
      ? ""
      : rawNicheId;

  const rows = useMemo(
    () => toResultRows(search?.results as unknown[] | undefined, search?.provider ?? selectedProvider),
    [search, selectedProvider],
  );

  function resetResults() {
    setSearch(null);
    setSelected(new Set());
    setSaved(null);
  }

  const generate = useMutation({
    mutationFn: () => searchesApi.generateQueries(Number(nicheId)),
    onSuccess: (data) => {
      setQueries(data.queries);
      setQuery(data.queries[0] ?? "");
      setShowAll(false);
      resetResults();
      toast.success(`Generated ${data.queries.length} search queries`);
    },
  });

  const run = useMutation({
    mutationFn: () => searchesApi.run(Number(nicheId), query.trim(), selectedProvider),
    onMutate: resetResults,
    onSuccess: (result) => {
      setSearch(result);
      const found = toResultRows(result.results as unknown[], result.provider);
      setSelected(new Set(found.map((row) => row.url)));
      if (found.length === 0) toast.info("The search finished with no results.");
    },
  });

  const save = useMutation({
    mutationFn: () => searchesApi.saveResults(search!.id, [...selected]),
    onSuccess: (data) => {
      setSaved(data);
      setSelected(new Set());
      for (const key of ["leads", "companies", "dashboard", "onboarding"]) {
        queryClient.invalidateQueries({ queryKey: [key] });
      }
      toast.success(
        `Saved ${data.created} new lead${data.created === 1 ? "" : "s"}` +
          (data.skipped ? ` (${data.skipped} already saved or skipped)` : ""),
      );
    },
  });

  const nicheOptions = (niches.data?.items ?? []).map((n) => ({
    value: String(n.id),
    label: `${n.name} · ${n.industry}`,
  }));
  const visibleQueries = showAll ? queries : queries.slice(0, 12);
  const ranWith = search?.provider;

  return (
    <div>
      <PageHeader
        title="Search"
        description="Find people in your niche with an approved search provider, review the results and save the ones worth contacting."
      />

      <div
        role="note"
        className="mb-6 flex items-start gap-3 rounded-lg border border-[var(--primary)]/30 bg-[var(--primary-fixed)] p-4 text-[13px] text-[var(--on-primary-fixed)]"
      >
        <Info className="mt-0.5 size-4 shrink-0 text-[var(--primary)]" aria-hidden />
        <p>
          Search finds public web pages, not email addresses. After saving, enrich the companies
          to look for public contact details. Scraping search engines or LinkedIn directly isn&apos;t
          supported.
        </p>
      </div>

      {niches.error ? (
        <ErrorState error={niches.error} onRetry={() => niches.refetch()} />
      ) : !niches.isLoading && nicheOptions.length === 0 ? (
        <EmptyState
          title="Create a niche first"
          description="A niche describes who you're looking for. We use it to suggest search queries."
          action={<ButtonLink href="/niches/new">Create a niche</ButtonLink>}
        />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
          <div className="flex min-w-0 flex-col gap-4">
            <Step number={1} title="Choose a niche">
              <SelectField
                label="Niche"
                hideLabel
                value={nicheId}
                onChange={(value) => {
                  setNicheId(value);
                  setQueries([]);
                  setQuery("");
                  resetResults();
                }}
                options={nicheOptions}
                placeholder={niches.isLoading ? "Loading niches…" : "Choose a niche"}
                disabled={niches.isLoading}
              />
              <Button
                variant="outline"
                className="mt-3 w-full"
                onClick={() => generate.mutate()}
                disabled={!nicheId || generate.isPending}
              >
                {generate.isPending ? (
                  <Loader2 className="animate-spin" aria-hidden />
                ) : (
                  <Sparkles aria-hidden />
                )}
                {generate.isPending ? "Generating…" : "Suggest search queries"}
              </Button>
            </Step>

            <Step number={2} title="Pick or write a query">
              {queries.length > 0 ? (
                <>
                  <p className="mb-2 text-[12px] text-[var(--on-surface-variant)]">
                    {queries.length} suggestions from your niche
                  </p>
                  <ul className="flex max-h-72 flex-col gap-1.5 overflow-y-auto pr-1">
                    {visibleQueries.map((suggestion) => {
                      const active = suggestion === query;
                      return (
                        <li key={suggestion}>
                          <button
                            type="button"
                            aria-pressed={active}
                            onClick={() => {
                              setQuery(suggestion);
                              resetResults();
                            }}
                            className={cn(
                              "flex w-full items-start gap-2 rounded-md border px-3 py-2 text-left text-[12px] transition-colors focus-visible:ring-2 focus-visible:ring-[var(--primary)] focus-visible:outline-none",
                              active
                                ? "border-[var(--primary)] bg-[var(--primary-fixed)] text-[var(--on-primary-fixed)]"
                                : "border-[var(--outline-variant)] text-[var(--on-surface)] hover:bg-[var(--surface-container-low)]",
                            )}
                          >
                            <Search className="mt-0.5 size-3.5 shrink-0" aria-hidden />
                            <span className="break-words">{suggestion}</span>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                  {queries.length > 12 ? (
                    <Button
                      variant="link"
                      size="sm"
                      className="mt-1 px-0"
                      onClick={() => setShowAll((value) => !value)}
                    >
                      {showAll ? "Show fewer" : `Show all ${queries.length}`}
                    </Button>
                  ) : null}
                </>
              ) : (
                <p className="mb-3 text-[12px] text-[var(--on-surface-variant)]">
                  {nicheId
                    ? "Get suggestions from your niche, or type your own query below."
                    : "Choose a niche first."}
                </p>
              )}
              <div className="mt-3 flex flex-col gap-1.5 border-t border-[var(--outline-variant)] pt-3">
                <label
                  htmlFor="search-query"
                  className="text-[12px] font-medium text-[var(--on-surface-variant)]"
                >
                  Query
                </label>
                <Input
                  id="search-query"
                  value={query}
                  onChange={(event) => {
                    setQuery(event.target.value);
                    if (search) resetResults();
                  }}
                  placeholder="e.g. head of sales B2B SaaS London"
                  className="h-9 text-[13px]"
                  disabled={!nicheId}
                />
              </div>
            </Step>
          </div>

          <div className="flex min-w-0 flex-col gap-4">
            <Step number={3} title="Run the search">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                <SelectField
                  label="Search provider"
                  value={selectedProvider}
                  onChange={setProvider}
                  options={providerOptions}
                  disabled={providers.isLoading}
                  className="flex-1"
                />
                <Button
                  onClick={() => run.mutate()}
                  disabled={!nicheId || !query.trim() || run.isPending}
                  className="h-9"
                >
                  {run.isPending ? (
                    <Loader2 className="animate-spin" aria-hidden />
                  ) : (
                    <Play aria-hidden />
                  )}
                  {run.isPending ? "Searching…" : "Run search"}
                </Button>
              </div>
              <p className="mt-2 text-[12px] text-[var(--on-surface-variant)]">
                Add or switch providers in{" "}
                <Link href="/settings/providers" className="text-[var(--primary)] underline">
                  Settings → Providers
                </Link>
                .
              </p>
            </Step>

            <section
              aria-labelledby="search-results-title"
              aria-busy={run.isPending}
              className="flex min-h-[320px] flex-col overflow-hidden rounded-lg border border-[var(--outline-variant)] bg-white shadow-sm"
            >
              <h3 id="search-results-title" className="sr-only">
                Results
              </h3>
              {run.isPending ? (
                <div className="flex flex-1 flex-col items-center justify-center gap-3 p-12 text-center">
                  <Loader2 className="size-8 animate-spin text-[var(--primary)]" aria-hidden />
                  <p className="text-[13px] text-[var(--on-surface-variant)]" role="status">
                    Searching with {providerLabel(selectedProvider)}…
                  </p>
                </div>
              ) : run.isError ? (
                <div className="p-5">
                  <ErrorState error={run.error} onRetry={() => run.mutate()} />
                </div>
              ) : !search ? (
                <div className="flex flex-1 flex-col items-center justify-center p-12 text-center">
                  <Search className="mb-3 size-10 text-[var(--on-surface-variant)]" aria-hidden />
                  <p className="text-[15px] font-semibold text-[var(--on-surface)]">
                    {!nicheId ? "Choose a niche to start" : !query.trim() ? "Pick a query" : "Ready to search"}
                  </p>
                  <p className="mt-1 max-w-sm text-[13px] text-[var(--on-surface-variant)]">
                    Results appear here. Nothing is saved until you choose which ones to keep.
                  </p>
                </div>
              ) : rows.length === 0 ? (
                <div className="flex flex-1 flex-col items-center justify-center p-12 text-center">
                  <p className="text-[15px] font-semibold text-[var(--on-surface)]">No results</p>
                  <p className="mt-1 max-w-sm text-[13px] text-[var(--on-surface-variant)]">
                    {providerLabel(search.provider)} returned nothing for this query. Try a broader
                    query or another suggestion.
                  </p>
                </div>
              ) : (
                <>
                  <div className="flex flex-col gap-3 border-b border-[var(--outline-variant)] bg-[var(--surface-container-low)] px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                    <p className="text-[13px] text-[var(--on-surface-variant)]" aria-live="polite">
                      {rows.length} result{rows.length === 1 ? "" : "s"} from{" "}
                      {providerLabel(search.provider)} ·{" "}
                      <span className="font-medium text-[var(--on-surface)]">
                        {selected.size} selected
                      </span>
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" variant="ghost" onClick={resetResults}>
                        <Trash2 aria-hidden />
                        Clear
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => save.mutate()}
                        disabled={selected.size === 0 || save.isPending}
                      >
                        <Save aria-hidden />
                        {save.isPending
                          ? "Saving…"
                          : `Save ${selected.size} as lead${selected.size === 1 ? "" : "s"}`}
                      </Button>
                    </div>
                  </div>
                  {ranWith && ranWith !== selectedProvider ? (
                    <p
                      role="note"
                      className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-[12px] text-amber-900"
                    >
                      This search ran with {providerLabel(ranWith)}, your workspace&apos;s active
                      search provider. To use {providerLabel(selectedProvider)}, activate it in
                      Settings → Providers.
                    </p>
                  ) : null}
                  {saved ? (
                    <div
                      role="status"
                      className="flex flex-col gap-2 border-b border-emerald-200 bg-emerald-50 px-4 py-3 text-[13px] text-emerald-900 sm:flex-row sm:items-center"
                    >
                      <CheckCircle2 className="size-4 shrink-0" aria-hidden />
                      <p className="flex-1">
                        Saved {saved.created} new lead{saved.created === 1 ? "" : "s"}
                        {saved.skipped ? `, ${saved.skipped} skipped (already saved)` : ""}. Enrich
                        their companies to look for email addresses.
                      </p>
                      <div className="flex gap-3">
                        <Link
                          href={`/leads?niche_id=${nicheId}`}
                          className="font-medium underline"
                        >
                          View leads
                        </Link>
                        <Link href="/companies" className="font-medium underline">
                          Enrich companies
                        </Link>
                      </div>
                    </div>
                  ) : null}
                  <SearchResultsTable
                    results={rows}
                    selected={selected}
                    onToggle={(url) =>
                      setSelected((current) => {
                        const next = new Set(current);
                        if (next.has(url)) next.delete(url);
                        else next.add(url);
                        return next;
                      })
                    }
                    onToggleAll={() =>
                      setSelected((current) =>
                        rows.every((row) => current.has(row.url))
                          ? new Set()
                          : new Set(rows.map((row) => row.url)),
                      )
                    }
                  />
                </>
              )}
            </section>
          </div>
        </div>
      )}
    </div>
  );
}
