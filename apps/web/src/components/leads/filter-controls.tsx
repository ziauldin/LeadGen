"use client";

import { useEffect, useId, useRef, useState } from "react";
import { Search, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

export type Option = { value: string; label: string };

/** A labelled select built on the base-ui Select, showing option labels (not raw values). */
export function SelectField({
  label,
  value,
  onChange,
  options,
  placeholder,
  hideLabel = false,
  disabled = false,
  className,
  triggerClassName,
  id,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Option[];
  placeholder?: string;
  hideLabel?: boolean;
  disabled?: boolean;
  className?: string;
  triggerClassName?: string;
  id?: string;
}) {
  const generatedId = useId();
  const fieldId = id ?? generatedId;
  const labelId = `${fieldId}-label`;
  return (
    <div className={cn("flex min-w-0 flex-col gap-1.5", className)}>
      <span
        id={labelId}
        className={cn(
          "text-[12px] font-medium text-[var(--on-surface-variant)]",
          hideLabel && "sr-only",
        )}
      >
        {label}
      </span>
      <Select
        items={options}
        value={value}
        onValueChange={(next) => onChange((next as string | null) ?? "")}
        disabled={disabled}
      >
        <SelectTrigger
          id={fieldId}
          aria-labelledby={labelId}
          className={cn("h-9 w-full bg-white text-[13px]", triggerClassName)}
        >
          <SelectValue placeholder={placeholder} />
        </SelectTrigger>
        <SelectContent alignItemWithTrigger={false}>
          {options.map((option) => (
            <SelectItem key={option.value} value={option.value} className="text-[13px]">
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

/** Search box that reports its value after the user pauses typing. */
export function DebouncedSearchInput({
  value,
  onChange,
  placeholder = "Search…",
  label = "Search",
  delay = 350,
  className,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  label?: string;
  delay?: number;
  className?: string;
}) {
  const id = useId();
  const [text, setText] = useState(value);
  const onChangeRef = useRef(onChange);
  const lastSent = useRef(value);

  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  // Follow outside changes (e.g. "Clear filters" or back/forward navigation).
  useEffect(() => {
    if (value !== lastSent.current) {
      lastSent.current = value;
      setText(value);
    }
  }, [value]);

  useEffect(() => {
    const next = text.trim();
    if (next === lastSent.current) return;
    const timer = window.setTimeout(() => {
      lastSent.current = next;
      onChangeRef.current(next);
    }, delay);
    return () => window.clearTimeout(timer);
  }, [text, delay]);

  return (
    <div className={cn("flex min-w-0 flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-[12px] font-medium text-[var(--on-surface-variant)]">
        {label}
      </label>
      <div className="relative">
        <Search
          className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-[var(--on-surface-variant)]"
          aria-hidden
        />
        <Input
          id={id}
          type="search"
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder={placeholder}
          className="h-9 bg-white pr-8 pl-8 text-[13px]"
        />
        {text ? (
          <button
            type="button"
            aria-label="Clear search"
            onClick={() => setText("")}
            className="absolute top-1/2 right-2 -translate-y-1/2 rounded p-0.5 text-[var(--on-surface-variant)] hover:text-[var(--on-surface)] focus-visible:ring-2 focus-visible:ring-[var(--primary)] focus-visible:outline-none"
          >
            <X className="size-3.5" aria-hidden />
          </button>
        ) : null}
      </div>
    </div>
  );
}

/** Card-style wrapper for a row of filters that wraps on small screens. */
export function FilterBar({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-4 grid grid-cols-1 gap-3 rounded-lg border border-[var(--outline-variant)] bg-white p-4 shadow-sm sm:grid-cols-2 lg:flex lg:flex-wrap lg:items-end">
      {children}
    </div>
  );
}
