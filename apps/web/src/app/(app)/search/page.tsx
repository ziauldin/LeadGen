"use client";

import { useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  AlertTriangle,
  ChevronDown,
  Info,
  Play,
  Save,
  Search,
  Sparkles,
  X,
} from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { nichesApi, searchesApi } from "@/lib/api/endpoints";

type RawResult = { title?: string; url?: string; snippet?: string };

export default function SearchPage() {
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const initialNicheId = searchParams.get("niche_id");
  const [nicheId, setNicheId] = useState(initialNicheId ?? "");
  const [queries, setQueries] = useState<string[]>([]);
  const [selectedQuery, setSelectedQuery] = useState("");
  const [searchId, setSearchId] = useState<number | null>(null);
  const [rawResults, setRawResults] = useState<RawResult[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const { data: niches } = useQuery({
    queryKey: ["niches"],
    queryFn: nichesApi.list,
  });

  const tableRows = useMemo(
    () =>
      rawResults.map((row, index) => ({
        index,
        title: row.title ?? "Untitled",
        url: row.url ?? "",
        snippet: row.snippet,
      })),
    [rawResults],
  );

  const generateMutation = useMutation({
    mutationFn: () => searchesApi.generateQueries(Number(nicheId)),
    onSuccess: (data) => {
      setQueries(data.queries);
      setSelectedQuery(data.queries[0] ?? "");
      toast.success(`Generated ${data.queries.length} queries`);
    },
    onError: () => toast.error("Failed to generate queries"),
  });

  const runMutation = useMutation({
    mutationFn: () => searchesApi.run(Number(nicheId), selectedQuery),
    onSuccess: (search) => {
      setSearchId(search.id);
      const results = (search.results as RawResult[]) ?? [];
      setRawResults(results);
      setSelected(new Set(results.map((_, i) => i)));
      toast.success(`Found ${results.length} results`);
    },
    onError: () => toast.error("Search failed"),
  });

  const saveMutation = useMutation({
    mutationFn: () => searchesApi.saveResults(searchId!, Array.from(selected)),
    onSuccess: (data) => {
      toast.success(`Saved ${data.created} leads to pipeline`);
      queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
    onError: () => toast.error("Failed to save results"),
  });

  return (
    <div>
      <PageHeader
        title="Search"
        description="Generate compliant search queries, preview results, and save leads to your pipeline."
      />

      {/* Compliance notice */}
      <div
        className="flex items-start gap-3 p-4 rounded-lg border mb-6"
        style={{
          background: "var(--primary-fixed)",
          borderColor: "var(--primary)",
          color: "var(--on-primary-fixed)",
        }}
      >
        <Info className="w-4 h-4 mt-0.5 shrink-0" style={{ color: "var(--primary)" }} />
        <p className="text-[13px]">
          <strong>Approved providers only.</strong> This tool uses configured search API providers
          (Google CSE, Bing, SerpAPI, or mock). Direct Google SERP HTML scraping and LinkedIn
          scraping are permanently disabled.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
        {/* Left: Query builder */}
        <div className="flex flex-col gap-4">
          {/* Niche selector */}
          <div
            className="bg-white border rounded-lg p-5 shadow-sm"
            style={{ borderColor: "var(--outline-variant)" }}
          >
            <h3
              className="text-[14px] font-semibold mb-3"
              style={{ color: "var(--on-surface)" }}
            >
              1. Select Niche
            </h3>
            <div className="relative">
              <select
                value={nicheId}
                onChange={(e) => {
                  setNicheId(e.target.value);
                  setQueries([]);
                  setSelectedQuery("");
                  setRawResults([]);
                  setSearchId(null);
                }}
                className="w-full px-3 py-2.5 border rounded text-[13px] outline-none appearance-none pr-8"
                style={{
                  borderColor: "var(--outline-variant)",
                  color: "var(--on-surface)",
                  background: "var(--surface-container-lowest)",
                }}
              >
                <option value="">Choose a niche…</option>
                {(niches?.items ?? []).map((n) => (
                  <option key={n.id} value={String(n.id)}>
                    {n.name} — {n.industry}
                  </option>
                ))}
              </select>
              <ChevronDown
                className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 pointer-events-none"
                style={{ color: "var(--on-surface-variant)" }}
              />
            </div>

            <button
              onClick={() => generateMutation.mutate()}
              disabled={!nicheId || generateMutation.isPending}
              className="mt-3 w-full flex items-center justify-center gap-2 px-4 py-2 border rounded text-[13px] font-medium transition-colors disabled:opacity-50"
              style={{
                borderColor: "var(--primary)",
                color: "var(--primary)",
                background: "var(--surface-container-lowest)",
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.background = "var(--primary-fixed)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = "var(--surface-container-lowest)")
              }
            >
              <Sparkles className="w-4 h-4" />
              {generateMutation.isPending ? "Generating…" : "Generate Queries"}
            </button>
          </div>

          {/* Query chips */}
          {queries.length > 0 && (
            <div
              className="bg-white border rounded-lg p-5 shadow-sm"
              style={{ borderColor: "var(--outline-variant)" }}
            >
              <h3
                className="text-[14px] font-semibold mb-3"
                style={{ color: "var(--on-surface)" }}
              >
                2. Select Query
              </h3>
              <div className="flex flex-col gap-2">
                {queries.map((q) => (
                  <button
                    key={q}
                    onClick={() => setSelectedQuery(q)}
                    className="flex items-start gap-2 px-3 py-2 rounded border text-[12px] text-left transition-all"
                    style={{
                      background:
                        selectedQuery === q ? "var(--primary-fixed)" : "var(--surface)",
                      borderColor:
                        selectedQuery === q ? "var(--primary)" : "var(--outline-variant)",
                      color: selectedQuery === q ? "var(--on-primary-fixed)" : "var(--on-surface)",
                    }}
                  >
                    <Search className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                    {q}
                  </button>
                ))}
              </div>

              <div className="mt-3 flex items-center gap-2">
                <div className="relative flex-1">
                  <input
                    type="text"
                    value={selectedQuery}
                    onChange={(e) => setSelectedQuery(e.target.value)}
                    className="w-full px-3 py-2 border rounded text-[12px] outline-none"
                    placeholder="Or type a custom query…"
                    style={{
                      borderColor: "var(--outline-variant)",
                      color: "var(--on-surface)",
                    }}
                    onFocus={(e) => {
                      e.target.style.borderColor = "var(--primary)";
                    }}
                    onBlur={(e) => {
                      e.target.style.borderColor = "var(--outline-variant)";
                    }}
                  />
                  {selectedQuery && (
                    <button
                      onClick={() => setSelectedQuery("")}
                      className="absolute right-2 top-1/2 -translate-y-1/2"
                      style={{ color: "var(--on-surface-variant)" }}
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>

              <button
                onClick={() => runMutation.mutate()}
                disabled={!selectedQuery || !nicheId || runMutation.isPending}
                className="mt-3 w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded text-[13px] font-medium text-white transition-colors disabled:opacity-50"
                style={{ background: "var(--primary)" }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.background = "var(--surface-tint)")
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.background = "var(--primary)")
                }
              >
                <Play className="w-4 h-4" />
                {runMutation.isPending ? "Running…" : "Run Search"}
              </button>
            </div>
          )}

          {/* Save button */}
          {searchId && tableRows.length > 0 && (
            <button
              onClick={() => saveMutation.mutate()}
              disabled={saveMutation.isPending || selected.size === 0}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 border rounded text-[13px] font-medium transition-colors disabled:opacity-50"
              style={{
                background: "var(--secondary-container)",
                borderColor: "var(--secondary)",
                color: "var(--on-secondary-container)",
              }}
            >
              <Save className="w-4 h-4" />
              {saveMutation.isPending
                ? "Saving…"
                : `Save ${selected.size} selected lead${selected.size !== 1 ? "s" : ""}`}
            </button>
          )}
        </div>

        {/* Right: Results table */}
        <div
          className="bg-white border rounded-lg shadow-sm overflow-hidden"
          style={{ borderColor: "var(--outline-variant)", minHeight: 400 }}
        >
          {!nicheId ? (
            <div className="flex flex-col items-center justify-center h-full p-16 text-center">
              <Search className="w-12 h-12 mb-4" style={{ color: "var(--outline)" }} />
              <p className="text-[16px] font-semibold mb-2" style={{ color: "var(--on-surface)" }}>
                Select a niche to start
              </p>
              <p className="text-[13px]" style={{ color: "var(--on-surface-variant)" }}>
                Choose a niche, generate queries, then run a search to preview results.
              </p>
            </div>
          ) : tableRows.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full p-16 text-center">
              <AlertTriangle className="w-12 h-12 mb-4" style={{ color: "var(--outline)" }} />
              <p className="text-[16px] font-semibold mb-2" style={{ color: "var(--on-surface)" }}>
                {runMutation.isPending ? "Searching…" : "No results yet"}
              </p>
              <p className="text-[13px]" style={{ color: "var(--on-surface-variant)" }}>
                {runMutation.isPending
                  ? "Fetching results from the search provider…"
                  : "Generate queries and run a search to see results here."}
              </p>
            </div>
          ) : (
            <>
              <div
                className="flex items-center justify-between px-5 py-3 border-b"
                style={{ background: "var(--surface)", borderColor: "var(--outline-variant)" }}
              >
                <p className="text-[13px]" style={{ color: "var(--on-surface-variant)" }}>
                  {tableRows.length} results —{" "}
                  <span className="font-medium" style={{ color: "var(--on-surface)" }}>
                    {selected.size} selected
                  </span>
                </p>
                <button
                  onClick={() =>
                    setSelected(
                      selected.size === tableRows.length
                        ? new Set()
                        : new Set(tableRows.map((r) => r.index)),
                    )
                  }
                  className="text-[12px] font-medium"
                  style={{ color: "var(--primary)" }}
                >
                  {selected.size === tableRows.length ? "Deselect all" : "Select all"}
                </button>
              </div>

              <div className="overflow-y-auto" style={{ maxHeight: "70vh" }}>
                {tableRows.map((row) => (
                  <div
                    key={row.index}
                    className="flex items-start gap-4 px-5 py-4 border-b transition-colors cursor-pointer"
                    style={{
                      borderColor: "var(--outline-variant)",
                      background: selected.has(row.index) ? "var(--primary-fixed)" : "transparent",
                    }}
                    onClick={() =>
                      setSelected((current) => {
                        const next = new Set(current);
                        if (next.has(row.index)) next.delete(row.index);
                        else next.add(row.index);
                        return next;
                      })
                    }
                  >
                    <input
                      type="checkbox"
                      checked={selected.has(row.index)}
                      onChange={() => {}}
                      className="mt-1 rounded shrink-0"
                    />
                    <div className="min-w-0">
                      <p
                        className="text-[14px] font-semibold mb-0.5 truncate"
                        style={{ color: "var(--on-surface)" }}
                      >
                        {row.title}
                      </p>
                      <p
                        className="text-[12px] mb-1 truncate"
                        style={{ color: "var(--primary)" }}
                      >
                        {row.url}
                      </p>
                      {row.snippet && (
                        <p className="text-[12px]" style={{ color: "var(--on-surface-variant)" }}>
                          {row.snippet}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
