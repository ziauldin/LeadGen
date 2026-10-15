"use client";

import { ExternalLink } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { components } from "@/lib/api/schema";

export type SearchResultRow = components["schemas"]["SearchResultItem"];

/** Normalises the API's loosely typed result list into the documented SearchResultItem shape. */
export function toResultRows(results: unknown[] | undefined, fallbackProvider: string): SearchResultRow[] {
  return (results ?? [])
    .map((raw) => {
      const item = (raw ?? {}) as Record<string, unknown>;
      const text = (key: string) => (typeof item[key] === "string" ? (item[key] as string) : "");
      return {
        title: text("title") || text("url") || "Untitled result",
        url: text("url"),
        snippet: text("snippet"),
        provider: text("provider") || fallbackProvider,
      };
    })
    .filter((row) => row.url);
}

function hostname(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function SearchResultsTable({
  results,
  selected,
  onToggle,
  onToggleAll,
}: {
  results: SearchResultRow[];
  selected: Set<string>;
  onToggle: (url: string) => void;
  onToggleAll: () => void;
}) {
  const allSelected = results.length > 0 && results.every((row) => selected.has(row.url));
  const someSelected = !allSelected && results.some((row) => selected.has(row.url));

  return (
    <div className="overflow-x-auto">
      <Table>
        <caption className="sr-only">Search results</caption>
        <TableHeader>
          <TableRow>
            <TableHead className="w-10">
              <input
                type="checkbox"
                aria-label="Select all results"
                className="size-4 cursor-pointer accent-[var(--primary)]"
                checked={allSelected}
                ref={(el) => {
                  if (el) el.indeterminate = someSelected;
                }}
                onChange={onToggleAll}
              />
            </TableHead>
            <TableHead>Result</TableHead>
            <TableHead className="hidden md:table-cell">Snippet</TableHead>
            <TableHead>Provider</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {results.map((row, index) => {
            const checked = selected.has(row.url);
            const checkboxId = `search-result-${index}`;
            return (
              <TableRow key={row.url} data-state={checked ? "selected" : undefined}>
                <TableCell className="align-top">
                  <input
                    id={checkboxId}
                    type="checkbox"
                    className="mt-0.5 size-4 cursor-pointer accent-[var(--primary)]"
                    checked={checked}
                    onChange={() => onToggle(row.url)}
                  />
                </TableCell>
                <TableCell className="max-w-[340px] min-w-[220px] align-top whitespace-normal">
                  <label
                    htmlFor={checkboxId}
                    className="block cursor-pointer text-[13px] font-medium text-[var(--on-surface)]"
                  >
                    {row.title}
                  </label>
                  <a
                    href={row.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-0.5 inline-flex max-w-full items-center gap-1 text-[12px] text-[var(--primary)] hover:underline"
                  >
                    <span className="truncate">{hostname(row.url)}</span>
                    <ExternalLink className="size-3 shrink-0" aria-hidden />
                    <span className="sr-only">(opens in a new tab)</span>
                  </a>
                  {row.snippet ? (
                    <p className="mt-1 line-clamp-2 text-[12px] text-[var(--on-surface-variant)] md:hidden">
                      {row.snippet}
                    </p>
                  ) : null}
                </TableCell>
                <TableCell className="hidden max-w-[420px] align-top text-[12px] whitespace-normal text-[var(--on-surface-variant)] md:table-cell">
                  <p className="line-clamp-3">{row.snippet || "—"}</p>
                </TableCell>
                <TableCell className="align-top">
                  <span className="rounded-full border border-[var(--outline-variant)] bg-white px-2 py-0.5 text-[11px] text-[var(--on-surface-variant)]">
                    {row.provider}
                  </span>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
