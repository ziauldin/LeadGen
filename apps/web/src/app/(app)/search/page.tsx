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
  Trash2,
} from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { nichesApi, searchesApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";

type RawResult = { title?: string; url?: string; snippet?: string; provider?: string };

// Lightweight parser for frontend display
function parseResult(row: RawResult, index: number, fallbackProvider: string) {
  let leadName = "Unknown";
  let roleTitle = "-";
  let company = "-";
  
  if (row.title) {
    if (row.title.includes(" at ")) {
      const parts = row.title.split(" at ");
      leadName = parts[0].trim();
      const rest = parts[1].split("—")[0].split("-")[0].trim();
      company = rest; // Usually company comes after "at"
    } else if (row.title.includes(" - ")) {
      const parts = row.title.split(" - ");
      leadName = parts[0].trim();
      roleTitle = parts[1] ? parts[1].trim() : "-";
    } else {
      leadName = row.title.trim();
    }
  }

  return {
    index,
    title: row.title ?? "Untitled",
    url: row.url ?? "",
    snippet: row.snippet,
    leadName,
    company,
    roleTitle,
    provider: row.provider || fallbackProvider || "mock",
    confidence: (0.75 + Math.random() * 0.2).toFixed(2), // Visual placeholder
    saveStatus: "not_saved"
  };
}

export default function SearchPage() {
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const initialNicheId = searchParams.get("niche_id");
  
  const [nicheId, setNicheId] = useState(initialNicheId ?? "");
  const [queries, setQueries] = useState<string[]>([]);
  const [showAllQueries, setShowAllQueries] = useState(false);
  const [selectedQuery, setSelectedQuery] = useState("");
  const [selectedProvider, setSelectedProvider] = useState("mock");
  const [searchId, setSearchId] = useState<number | null>(null);
  const [rawResults, setRawResults] = useState<RawResult[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [hasRunSearch, setHasRunSearch] = useState(false);

  const { data: niches } = useQuery({
    queryKey: ["niches"],
    queryFn: nichesApi.list,
  });

  const tableRows = useMemo(
    () => rawResults.map((row, index) => parseResult(row, index, selectedProvider)),
    [rawResults, selectedProvider]
  );

  const generateMutation = useMutation({
    mutationFn: () => searchesApi.generateQueries(Number(nicheId)),
    onSuccess: (data) => {
      setQueries(data.queries);
      setSelectedQuery("");
      setHasRunSearch(false);
      setRawResults([]);
      setShowAllQueries(false);
      toast.success(`Generated ${data.queries.length} queries`);
    },
    onError: () => toast.error("Failed to generate queries"),
  });

  const runMutation = useMutation({
    mutationFn: () => searchesApi.run(Number(nicheId), selectedQuery),
    onSuccess: (search) => {
      setHasRunSearch(true);
      setSearchId(search.id);
      const results = (search.results as RawResult[]) ?? [];
      setRawResults(results);
      setSelected(new Set(results.map((_, i) => i)));
      if (results.length > 0) {
        toast.success(`Found ${results.length} results`);
      } else {
        toast.info("Search completed with zero results");
      }
    },
    onError: (error: unknown) => {
      setHasRunSearch(true);
      setRawResults([]);
      
      let detailErrors: Array<{ type: string; loc: string[]; msg: string }> = [];
      let message = "Search failed. Please check the provider configuration and request payload.";

      if (error instanceof ApiError && error.detail && typeof error.detail === "object") {
        const detailObj = error.detail as { detail?: unknown };
        if (Array.isArray(detailObj.detail)) {
          detailErrors = detailObj.detail;
          message = detailErrors[0]?.msg || message;
        }
      } else if (error instanceof Error) {
        message = error.message;
      }

      const isQueryError = detailErrors.some(
        (err) => err.type === "missing" && err.loc?.includes("query")
      );

      if (isQueryError) {
        toast.error('Search failed: Backend requires "query" field. Frontend sent "query_text".');
      } else {
        toast.error(message);
      }
    },
  });

  const saveMutation = useMutation({
    mutationFn: () => searchesApi.saveResults(searchId!, Array.from(selected)),
    onSuccess: (data) => {
      toast.success(`Saved ${data.created} leads. Run Enrichment on these companies to find public emails.`);
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      // Clear selected after successful save
      setSelected(new Set());
    },
    onError: () => toast.error("Failed to save results"),
  });

  const visibleQueries = showAllQueries ? queries : queries.slice(0, 20);

  return (
    <div>
      <PageHeader
        title="Search"
        description="Generate compliant search queries, preview results, and save leads to your pipeline. Note: Search APIs only discover URLs. Use Enrichment on saved companies to discover emails."
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
          such as Google CSE, Bing, SerpAPI, or mock. Direct Google SERP HTML scraping and LinkedIn
          scraping are disabled.
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
                  setHasRunSearch(false);
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

          {/* Query list */}
          {queries.length > 0 && (
            <div
              className="bg-white border rounded-lg p-5 shadow-sm"
              style={{ borderColor: "var(--outline-variant)" }}
            >
              <h3
                className="text-[14px] font-semibold mb-1"
                style={{ color: "var(--on-surface)" }}
              >
                2. Select Query
              </h3>
              <p className="text-[12px] mb-3" style={{ color: "var(--on-surface-variant)" }}>
                {queries.length} queries generated
              </p>
              
              <div className="flex flex-col gap-2 max-h-64 overflow-y-auto pr-1">
                {visibleQueries.map((q) => (
                  <button
                    key={q}
                    onClick={() => {
                      setSelectedQuery(q);
                      setHasRunSearch(false);
                      setRawResults([]);
                    }}
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

              {!showAllQueries && queries.length > 20 && (
                <button
                  onClick={() => setShowAllQueries(true)}
                  className="mt-3 text-[12px] font-medium hover:underline"
                  style={{ color: "var(--primary)" }}
                >
                  Show more queries ({queries.length - 20} hidden)
                </button>
              )}

              <div className="mt-4 pt-4 border-t" style={{ borderColor: "var(--outline-variant)" }}>
                <div className="relative flex-1">
                  <input
                    type="text"
                    value={selectedQuery}
                    onChange={(e) => {
                      setSelectedQuery(e.target.value);
                      setHasRunSearch(false);
                    }}
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
                      onClick={() => {
                        setSelectedQuery("");
                        setHasRunSearch(false);
                      }}
                      className="absolute right-2 top-1/2 -translate-y-1/2"
                      style={{ color: "var(--on-surface-variant)" }}
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right: Action Area & Results table */}
        <div className="flex flex-col gap-4">
          
          {/* Action Area (Visible only when query is selected) */}
          {selectedQuery && (
            <div 
              className="bg-white border rounded-lg p-5 shadow-sm flex flex-col sm:flex-row sm:items-end gap-4"
              style={{ borderColor: "var(--outline-variant)" }}
            >
              <div className="flex-1">
                <label className="block text-[12px] font-medium mb-1" style={{ color: "var(--on-surface-variant)" }}>
                  Search Provider
                </label>
                <div className="relative">
                  <select
                    value={selectedProvider}
                    onChange={(e) => setSelectedProvider(e.target.value)}
                    className="w-full px-3 py-2 border rounded text-[13px] outline-none appearance-none pr-8"
                    style={{
                      borderColor: "var(--outline-variant)",
                      color: "var(--on-surface)",
                      background: "var(--surface-container-lowest)",
                    }}
                  >
                    <option value="mock">Mock</option>
                    <option value="google_cse">Google CSE</option>
                    <option value="bing">Bing</option>
                    <option value="serpapi">SerpAPI</option>
                  </select>
                  <ChevronDown
                    className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 pointer-events-none"
                    style={{ color: "var(--on-surface-variant)" }}
                  />
                </div>
              </div>

              <div className="flex gap-3 shrink-0">
                <button
                  onClick={() => runMutation.mutate()}
                  disabled={!selectedQuery || !nicheId || runMutation.isPending}
                  className="flex items-center justify-center gap-2 px-6 py-2 rounded text-[13px] font-medium text-white transition-colors disabled:opacity-50"
                  style={{ background: "var(--primary)" }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.background = "var(--surface-tint)")
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.background = "var(--primary)")
                  }
                >
                  <Play className="w-4 h-4" />
                  {runMutation.isPending ? "Running..." : "Run Selected Query"}
                </button>
              </div>
            </div>
          )}

          {/* Results Table */}
          <div
            className="bg-white border rounded-lg shadow-sm overflow-hidden flex flex-col flex-1"
            style={{ borderColor: "var(--outline-variant)", minHeight: 400 }}
          >
            {!nicheId ? (
              <div className="flex flex-col items-center justify-center h-full p-16 text-center flex-1">
                <Search className="w-12 h-12 mb-4" style={{ color: "var(--outline)" }} />
                <p className="text-[16px] font-semibold mb-2" style={{ color: "var(--on-surface)" }}>
                  Select a niche to start
                </p>
                <p className="text-[13px]" style={{ color: "var(--on-surface-variant)" }}>
                  Choose a niche, generate queries, then run a search to preview results.
                </p>
              </div>
            ) : queries.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full p-16 text-center flex-1">
                <Sparkles className="w-12 h-12 mb-4" style={{ color: "var(--outline)" }} />
                <p className="text-[16px] font-semibold mb-2" style={{ color: "var(--on-surface)" }}>
                  Queries not generated
                </p>
                <p className="text-[13px]" style={{ color: "var(--on-surface-variant)" }}>
                  Click &quot;Generate Queries&quot; to get started.
                </p>
              </div>
            ) : !selectedQuery ? (
              <div className="flex flex-col items-center justify-center h-full p-16 text-center flex-1">
                <Search className="w-12 h-12 mb-4" style={{ color: "var(--outline)" }} />
                <p className="text-[16px] font-semibold mb-2" style={{ color: "var(--on-surface)" }}>
                  Select a query
                </p>
                <p className="text-[13px]" style={{ color: "var(--on-surface-variant)" }}>
                  Choose a query from the list to prepare a search.
                </p>
              </div>
            ) : !hasRunSearch ? (
              <div className="flex flex-col items-center justify-center h-full p-16 text-center flex-1">
                <Play className="w-12 h-12 mb-4" style={{ color: "var(--primary)" }} />
                <p className="text-[16px] font-semibold mb-2" style={{ color: "var(--on-surface)" }}>
                  Ready to search
                </p>
                <p className="text-[13px]" style={{ color: "var(--on-surface-variant)" }}>
                  Click &quot;Run Selected Query&quot; to fetch results.
                </p>
              </div>
            ) : runMutation.isPending ? (
              <div className="flex flex-col items-center justify-center h-full p-16 text-center flex-1">
                <div className="w-12 h-12 mb-4 rounded-full border-4 border-t-transparent animate-spin mx-auto" style={{ borderColor: "var(--primary) transparent var(--primary) var(--primary)" }}></div>
                <p className="text-[16px] font-semibold mb-2" style={{ color: "var(--on-surface)" }}>
                  Searching...
                </p>
                <p className="text-[13px]" style={{ color: "var(--on-surface-variant)" }}>
                  Fetching results from {selectedProvider}...
                </p>
              </div>
            ) : runMutation.isError ? (
              <div className="flex flex-col items-center justify-center h-full p-16 text-center flex-1">
                <AlertTriangle className="w-12 h-12 mb-4 text-red-500" />
                <p className="text-[16px] font-semibold mb-2 text-red-600">
                  Search failed
                </p>
                <p className="text-[13px]" style={{ color: "var(--on-surface-variant)" }}>
                  An error occurred while communicating with the provider.
                </p>
              </div>
            ) : tableRows.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full p-16 text-center flex-1">
                <AlertTriangle className="w-12 h-12 mb-4" style={{ color: "var(--outline)" }} />
                <p className="text-[16px] font-semibold mb-2" style={{ color: "var(--on-surface)" }}>
                  No results found
                </p>
                <p className="text-[13px]" style={{ color: "var(--on-surface-variant)" }}>
                  The search provider returned 0 results for this query.
                </p>
              </div>
            ) : (
              <div className="flex flex-col h-full">
                {/* Table Header & Actions */}
                <div
                  className="flex items-center justify-between px-5 py-3 border-b shrink-0 flex-wrap gap-4"
                  style={{ background: "var(--surface)", borderColor: "var(--outline-variant)" }}
                >
                  <div className="flex items-center gap-3">
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

                  <div className="flex gap-2">
                    <button
                      onClick={() => {
                        setHasRunSearch(false);
                        setRawResults([]);
                        setSelected(new Set());
                      }}
                      className="flex items-center gap-1.5 px-3 py-1.5 border rounded text-[12px] font-medium hover:bg-gray-50 transition-colors"
                      style={{ borderColor: "var(--outline-variant)", color: "var(--on-surface)" }}
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      Clear Results
                    </button>
                    
                    <button
                      onClick={() => saveMutation.mutate()}
                      disabled={saveMutation.isPending || selected.size === 0}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[12px] font-medium text-white transition-colors disabled:opacity-50"
                      style={{ background: "var(--primary)" }}
                    >
                      <Save className="w-3.5 h-3.5" />
                      {saveMutation.isPending ? "Saving..." : "Save Selected as Leads"}
                    </button>
                  </div>
                </div>

                {/* Table Content */}
                <div className="overflow-x-auto overflow-y-auto" style={{ maxHeight: "70vh" }}>
                  <table className="w-full text-left border-collapse min-w-[900px]">
                    <thead>
                      <tr className="border-b bg-gray-50/50" style={{ borderColor: "var(--outline-variant)" }}>
                        <th className="px-4 py-3 w-10"></th>
                        <th className="px-4 py-3 text-[12px] font-semibold" style={{ color: "var(--on-surface-variant)" }}>Result Title</th>
                        <th className="px-4 py-3 text-[12px] font-semibold" style={{ color: "var(--on-surface-variant)" }}>Lead Name</th>
                        <th className="px-4 py-3 text-[12px] font-semibold" style={{ color: "var(--on-surface-variant)" }}>Role/Title</th>
                        <th className="px-4 py-3 text-[12px] font-semibold" style={{ color: "var(--on-surface-variant)" }}>Company</th>
                        <th className="px-4 py-3 text-[12px] font-semibold" style={{ color: "var(--on-surface-variant)" }}>Provider</th>
                        <th className="px-4 py-3 text-[12px] font-semibold" style={{ color: "var(--on-surface-variant)" }}>Confidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {tableRows.map((row) => (
                        <tr
                          key={row.index}
                          className="border-b transition-colors hover:bg-gray-50/50 cursor-pointer"
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
                          <td className="px-4 py-3">
                            <input
                              type="checkbox"
                              checked={selected.has(row.index)}
                              onChange={() => {}}
                              className="rounded shrink-0"
                            />
                          </td>
                          <td className="px-4 py-3 min-w-[200px] max-w-[300px]">
                            <p className="text-[13px] font-medium truncate mb-1" style={{ color: "var(--on-surface)" }} title={row.title}>
                              {row.title}
                            </p>
                            <a href={row.url} target="_blank" rel="noopener noreferrer" className="text-[11px] truncate block hover:underline" style={{ color: "var(--primary)" }} onClick={e => e.stopPropagation()}>
                              {row.url}
                            </a>
                          </td>
                          <td className="px-4 py-3 text-[13px] whitespace-nowrap" style={{ color: "var(--on-surface)" }}>{row.leadName}</td>
                          <td className="px-4 py-3 text-[13px] max-w-[150px] truncate" style={{ color: "var(--on-surface)" }} title={row.roleTitle}>{row.roleTitle}</td>
                          <td className="px-4 py-3 text-[13px] max-w-[150px] truncate" style={{ color: "var(--on-surface)" }} title={row.company}>{row.company}</td>
                          <td className="px-4 py-3 text-[13px]" style={{ color: "var(--on-surface-variant)" }}>
                            <span className="px-2 py-0.5 rounded-full border bg-white" style={{ borderColor: "var(--outline-variant)", fontSize: "11px" }}>
                              {row.provider}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-[13px]" style={{ color: "var(--on-surface-variant)" }}>
                            <div className="flex items-center gap-1.5">
                              <div className="w-16 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                                <div className="h-full rounded-full" style={{ width: `${Number(row.confidence) * 100}%`, background: "var(--primary)" }}></div>
                              </div>
                              <span className="text-[11px]">{Number(row.confidence) * 100}%</span>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
