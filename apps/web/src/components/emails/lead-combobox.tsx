"use client";

import { useEffect, useId, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Search } from "lucide-react";
import { leadsApi } from "@/lib/api/endpoints";
import type { Lead } from "@/lib/api/types";
import { cn } from "@/lib/utils";

export function useDebouncedValue<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

/** Type to search leads by name, email or company; pick one with the mouse or arrow keys. */
export function LeadCombobox({
  id,
  onSelect,
  autoFocus,
}: {
  id?: string;
  onSelect: (lead: Lead) => void;
  autoFocus?: boolean;
}) {
  const generatedId = useId();
  const inputId = id ?? `${generatedId}-input`;
  const listId = `${generatedId}-list`;
  const [text, setText] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const search = useDebouncedValue(text.trim(), 300);

  const results = useQuery({
    queryKey: ["leads", { search, limit: 20 }],
    queryFn: () => leadsApi.list({ search: search || undefined, limit: 20 }),
    enabled: open,
    staleTime: 30_000,
  });
  const leads = results.data?.items ?? [];
  const activeIndex = Math.min(active, Math.max(0, leads.length - 1));

  function choose(lead: Lead | undefined) {
    if (!lead) return;
    onSelect(lead);
    setText("");
    setOpen(false);
  }

  return (
    <div className="relative">
      <Search
        className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-[var(--on-surface-variant)]"
        aria-hidden
      />
      <input
        id={inputId}
        type="text"
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls={listId}
        aria-activedescendant={open && leads.length ? `${listId}-${activeIndex}` : undefined}
        autoComplete="off"
        // Focus moves here on purpose when the user clicks "Change lead".
        autoFocus={autoFocus}
        placeholder="Search by name, email or company"
        value={text}
        className="h-9 w-full rounded-lg border border-input bg-white pr-8 pl-8 text-[13px] outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
        onChange={(event) => {
          setText(event.target.value);
          setActive(0);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown") {
            event.preventDefault();
            setOpen(true);
            setActive(Math.min(activeIndex + 1, leads.length - 1));
          } else if (event.key === "ArrowUp") {
            event.preventDefault();
            setActive(Math.max(activeIndex - 1, 0));
          } else if (event.key === "Enter") {
            if (open && leads.length) {
              event.preventDefault();
              choose(leads[activeIndex]);
            }
          } else if (event.key === "Escape") {
            setOpen(false);
          }
        }}
      />
      {results.isFetching ? (
        <Loader2
          className="absolute top-1/2 right-2.5 size-4 -translate-y-1/2 animate-spin text-[var(--on-surface-variant)]"
          aria-hidden
        />
      ) : null}
      {open ? (
        <ul
          id={listId}
          role="listbox"
          aria-label="Matching leads"
          className="absolute z-30 mt-1 max-h-72 w-full overflow-y-auto rounded-lg border border-[var(--outline-variant)] bg-white p-1 shadow-lg"
        >
          {results.isError ? (
            <li className="px-2 py-2 text-[13px] text-[var(--error)]">
              Couldn&apos;t load leads. Try again in a moment.
            </li>
          ) : results.isPending ? (
            <li className="px-2 py-2 text-[13px] text-muted-foreground">Searching…</li>
          ) : leads.length === 0 ? (
            <li className="px-2 py-2 text-[13px] text-muted-foreground">
              {search ? `No leads match “${search}”.` : "No leads yet. Find some from Search."}
            </li>
          ) : (
            leads.map((lead, index) => (
              <li
                key={lead.id}
                id={`${listId}-${index}`}
                role="option"
                aria-selected={index === activeIndex}
                className={cn(
                  "cursor-pointer rounded-md px-2 py-1.5",
                  index === activeIndex && "bg-[var(--surface-container-low)]",
                )}
                // Keep focus in the input so the blur doesn't close the list before the click.
                onMouseDown={(event) => event.preventDefault()}
                onMouseEnter={() => setActive(index)}
                onClick={() => choose(lead)}
              >
                <span className="block truncate text-[13px] font-medium text-[var(--on-surface)]">
                  {lead.full_name}
                  {lead.company?.name ? (
                    <span className="font-normal text-[var(--on-surface-variant)]">
                      {" "}
                      · {lead.company.name}
                    </span>
                  ) : null}
                </span>
                <span className="block truncate text-xs text-[var(--on-surface-variant)]">
                  {lead.primary_email ?? "No email address"}
                  {lead.job_title ? ` · ${lead.job_title}` : ""}
                </span>
              </li>
            ))
          )}
        </ul>
      ) : null}
    </div>
  );
}
