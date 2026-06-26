"use client";

import { useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SearchQueryBuilder } from "@/components/search/search-query-builder";
import { SearchResultsTable } from "@/components/search/search-results-table";
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
    },
  });

  const runMutation = useMutation({
    mutationFn: () => searchesApi.run(Number(nicheId), selectedQuery),
    onSuccess: (search) => {
      setSearchId(search.id);
      const results = (search.results as RawResult[]) ?? [];
      setRawResults(results);
      setSelected(new Set(results.map((_, i) => i)));
    },
  });

  const saveMutation = useMutation({
    mutationFn: () => searchesApi.saveResults(searchId!, Array.from(selected)),
    onSuccess: (data) => {
      toast.success(`Saved ${data.created} leads`);
      queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });

  return (
    <div>
      <PageHeader title="Search" description="Generate queries and preview mock search results." />
      <Card className="max-w-4xl">
        <CardHeader>
          <CardTitle>Search builder</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <SearchQueryBuilder
            niches={niches?.items ?? []}
            nicheId={nicheId}
            onNicheChange={setNicheId}
            queries={queries}
            selectedQuery={selectedQuery}
            onQueryChange={setSelectedQuery}
            onGenerate={() => generateMutation.mutate()}
            onRun={() => runMutation.mutate()}
            generating={generateMutation.isPending}
            running={runMutation.isPending}
          />
          {searchId ? (
            <Button
              variant="secondary"
              onClick={() => saveMutation.mutate()}
              disabled={saveMutation.isPending || selected.size === 0}
            >
              Save {selected.size} selected
            </Button>
          ) : null}
          {tableRows.length > 0 ? (
            <SearchResultsTable
              results={tableRows}
              selected={selected}
              onToggle={(index) => {
                setSelected((current) => {
                  const next = new Set(current);
                  if (next.has(index)) next.delete(index);
                  else next.add(index);
                  return next;
                });
              }}
              onToggleAll={() => {
                setSelected((current) =>
                  current.size === tableRows.length
                    ? new Set()
                    : new Set(tableRows.map((r) => r.index)),
                );
              }}
            />
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
