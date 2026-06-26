"use client";

import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { Niche } from "@/lib/api/types";

export function SearchQueryBuilder({
  niches,
  nicheId,
  onNicheChange,
  queries,
  selectedQuery,
  onQueryChange,
  onGenerate,
  onRun,
  generating = false,
  running = false,
}: {
  niches: Niche[];
  nicheId: string;
  onNicheChange: (value: string) => void;
  queries: string[];
  selectedQuery: string;
  onQueryChange: (value: string) => void;
  onGenerate: () => void;
  onRun: () => void;
  generating?: boolean;
  running?: boolean;
}) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <label className="text-sm font-medium">Niche</label>
        <Select value={nicheId} onValueChange={(v) => onNicheChange(v ?? "")}>
          <SelectTrigger>
            <SelectValue placeholder="Select niche" />
          </SelectTrigger>
          <SelectContent>
            {niches.map((niche) => (
              <SelectItem key={niche.id} value={String(niche.id)}>
                {niche.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button onClick={onGenerate} disabled={!nicheId || generating}>
          {generating ? "Generating…" : "Generate queries"}
        </Button>
        <Button variant="outline" onClick={onRun} disabled={!nicheId || !selectedQuery || running}>
          {running ? "Running…" : "Run search"}
        </Button>
      </div>
      {queries.length > 0 ? (
        <div className="space-y-2">
          <label className="text-sm font-medium">Query</label>
          <Select value={selectedQuery} onValueChange={(v) => onQueryChange(v ?? "")}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {queries.map((query) => (
                <SelectItem key={query} value={query}>
                  {query}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      ) : null}
    </div>
  );
}
