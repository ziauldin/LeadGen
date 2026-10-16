"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { templatesApi } from "@/lib/api/endpoints";
import type { EmailTemplate } from "@/lib/api/types";
import { cn } from "@/lib/utils";

export const templatesQueryKey = (includeArchived = false) =>
  ["templates", { includeArchived }] as const;

/** Active templates, system ones first. Shared by the studio, regenerate dialog and library. */
export function useTemplates() {
  return useQuery({
    queryKey: templatesQueryKey(false),
    queryFn: () => templatesApi.list(false),
    staleTime: 60_000,
  });
}

export function splitTemplates(templates: EmailTemplate[] | undefined) {
  const list = templates ?? [];
  return {
    system: list.filter((template) => template.is_system),
    workspace: list.filter((template) => !template.is_system),
  };
}

export function TemplateSelect({
  id,
  value,
  onChange,
  disabled,
  className,
  "aria-describedby": describedBy,
}: {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  className?: string;
  "aria-describedby"?: string;
}) {
  const { data, isLoading } = useTemplates();
  const { system, workspace } = useMemo(() => splitTemplates(data), [data]);
  const items = useMemo(() => {
    const labels: Record<string, string> = {};
    for (const template of data ?? []) {
      labels[template.id] = template.is_system ? `${template.name} (System)` : template.name;
    }
    return labels;
  }, [data]);

  return (
    <Select
      value={value}
      items={items}
      onValueChange={(next) => next && onChange(String(next))}
      disabled={disabled || isLoading}
    >
      <SelectTrigger
        id={id}
        aria-describedby={describedBy}
        className={cn("w-full bg-white", className)}
      >
        <SelectValue placeholder={isLoading ? "Loading templates…" : "Choose a template"} />
      </SelectTrigger>
      <SelectContent alignItemWithTrigger={false}>
        {system.length ? (
          <SelectGroup>
            <SelectLabel>System templates</SelectLabel>
            {system.map((template) => (
              <SelectItem key={template.id} value={template.id}>
                {template.name}
                <span className="text-xs text-muted-foreground">System</span>
              </SelectItem>
            ))}
          </SelectGroup>
        ) : null}
        {system.length && workspace.length ? <SelectSeparator /> : null}
        {workspace.length ? (
          <SelectGroup>
            <SelectLabel>Your templates</SelectLabel>
            {workspace.map((template) => (
              <SelectItem key={template.id} value={template.id}>
                {template.name}
              </SelectItem>
            ))}
          </SelectGroup>
        ) : null}
      </SelectContent>
    </Select>
  );
}
