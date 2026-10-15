"use client";

import { useMemo } from "react";
import { Combobox } from "@base-ui/react/combobox";
import { Check, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

function supportedTimezones(): string[] {
  let zones: string[] = [];
  try {
    zones = Intl.supportedValuesOf?.("timeZone") ?? [];
  } catch {
    zones = [];
  }
  return zones;
}

const normalize = (value: string) => value.toLowerCase().replace(/[_/]/g, " ");

/** Searchable list of IANA timezones ("Europe/London"). Typing "new york" finds America/New_York. */
export function TimezoneCombobox({
  id,
  value,
  onChange,
  invalid,
  describedBy,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  invalid?: boolean;
  describedBy?: string;
}) {
  const zones = useMemo(() => {
    const list = supportedTimezones();
    const all = new Set(list);
    all.add("UTC");
    if (value) all.add(value);
    return [...all].sort((a, b) => a.localeCompare(b));
  }, [value]);

  return (
    <Combobox.Root
      items={zones}
      value={value || null}
      onValueChange={(next) => {
        if (typeof next === "string" && next) onChange(next);
      }}
      filter={(item, query) => normalize(String(item)).includes(normalize(query.trim()))}
      autoHighlight
    >
      <Combobox.InputGroup
        className={cn(
          "relative flex h-9 w-full items-center rounded-lg border border-input bg-white transition-colors focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50",
          invalid && "border-destructive ring-3 ring-destructive/20",
        )}
      >
        <Combobox.Input
          id={id}
          placeholder="Search timezones, e.g. London"
          aria-invalid={invalid || undefined}
          aria-describedby={describedBy}
          className="h-full w-full min-w-0 rounded-lg border-0 bg-transparent pr-9 pl-2.5 text-[13px] text-[var(--on-surface)] outline-none placeholder:text-muted-foreground"
        />
        <Combobox.Trigger
          aria-label="Show timezones"
          className="absolute right-1 flex size-7 items-center justify-center rounded-md text-[var(--on-surface-variant)] outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          <ChevronDown className="size-4" aria-hidden />
        </Combobox.Trigger>
      </Combobox.InputGroup>
      <Combobox.Portal>
        <Combobox.Positioner className="isolate z-50 outline-none" sideOffset={4}>
          <Combobox.Popup className="w-(--anchor-width) max-w-(--available-width) origin-(--transform-origin) rounded-lg bg-popover text-popover-foreground shadow-md ring-1 ring-foreground/10">
            <Combobox.Empty>
              <p className="px-3 py-3 text-[13px] text-[var(--on-surface-variant)]">
                No timezone matches that search.
              </p>
            </Combobox.Empty>
            <Combobox.List className="max-h-[min(18rem,var(--available-height))] overflow-y-auto overscroll-contain p-1 outline-0 data-empty:p-0">
              {(zone: string) => (
                <Combobox.Item
                  key={zone}
                  value={zone}
                  className="relative flex cursor-default items-center gap-2 rounded-md py-1.5 pr-8 pl-2 text-[13px] outline-none select-none data-highlighted:bg-[var(--surface-container-low)] data-highlighted:text-[var(--primary)]"
                >
                  <span className="truncate">{zone.replace(/_/g, " ")}</span>
                  <Combobox.ItemIndicator className="absolute right-2 flex items-center">
                    <Check className="size-4" aria-hidden />
                  </Combobox.ItemIndicator>
                </Combobox.Item>
              )}
            </Combobox.List>
          </Combobox.Popup>
        </Combobox.Positioner>
      </Combobox.Portal>
    </Combobox.Root>
  );
}
