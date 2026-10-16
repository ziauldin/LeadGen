"use client";

import { AlertTriangle } from "lucide-react";
import { GenerationBadge } from "@/components/emails/email-parts";
import type { ApprovalItem } from "@/lib/api/types";
import { cn } from "@/lib/utils";

export function approvalItemDomId(id: number) {
  return `approval-item-${id}`;
}

export function ApprovalList({
  items,
  selectedId,
  onSelect,
  checked,
  onToggle,
  onToggleAll,
}: {
  items: ApprovalItem[];
  selectedId: number | null;
  onSelect: (item: ApprovalItem) => void;
  checked: Set<number>;
  onToggle: (id: number) => void;
  onToggleAll: (checked: boolean) => void;
}) {
  const checkedOnPage = items.filter((item) => checked.has(item.id)).length;
  const allChecked = items.length > 0 && checkedOnPage === items.length;

  return (
    <div className="flex min-h-0 flex-col">
      <div className="flex items-center gap-3 border-b border-[var(--outline-variant)] px-3 py-2 text-xs text-[var(--on-surface-variant)]">
        <input
          type="checkbox"
          aria-label="Select all drafts on this page"
          className="size-4 cursor-pointer accent-[var(--primary)]"
          checked={allChecked}
          ref={(el) => {
            if (el) el.indeterminate = checkedOnPage > 0 && !allChecked;
          }}
          onChange={(event) => onToggleAll(event.target.checked)}
        />
        <span>{checkedOnPage ? `${checkedOnPage} selected` : "Select all on this page"}</span>
      </div>
      <ul aria-label="Drafts waiting for review" className="divide-y divide-[var(--outline-variant)]">
        {items.map((item) => {
          const selected = item.id === selectedId;
          const blocked = item.problems.length > 0;
          const leadLine = [item.lead?.full_name, item.lead?.company_name]
            .filter(Boolean)
            .join(" · ");
          return (
            <li
              key={item.id}
              id={approvalItemDomId(item.id)}
              className={cn(
                "relative flex items-start gap-3 px-3 py-3 transition-colors",
                selected
                  ? "bg-[var(--surface-container-low)] before:absolute before:inset-y-0 before:left-0 before:w-[3px] before:bg-[var(--primary)]"
                  : "hover:bg-[var(--surface-container-low)]/60",
              )}
            >
              <input
                type="checkbox"
                aria-label={`Select draft to ${item.recipient_email}`}
                className="mt-0.5 size-4 shrink-0 cursor-pointer accent-[var(--primary)]"
                checked={checked.has(item.id)}
                onChange={() => onToggle(item.id)}
              />
              <button
                type="button"
                onClick={() => onSelect(item)}
                aria-current={selected ? "true" : undefined}
                className="min-w-0 flex-1 rounded text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)] focus-visible:ring-offset-2"
              >
                <span className="flex items-center gap-2">
                  <span className="min-w-0 flex-1 truncate text-[13px] font-semibold text-[var(--on-surface)]">
                    {leadLine || item.recipient_email}
                  </span>
                  {blocked ? (
                    <AlertTriangle
                      className="size-4 shrink-0 text-[var(--error)]"
                      aria-label={`${item.problems.length} problem${item.problems.length === 1 ? "" : "s"}`}
                      role="img"
                    />
                  ) : null}
                </span>
                <span className="mt-0.5 block truncate text-[13px] text-[var(--on-surface)]">
                  {item.subject}
                </span>
                <span className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-[var(--on-surface-variant)]">
                  <span className="truncate">{item.recipient_email}</span>
                  {item.campaign_name ? (
                    <>
                      <span aria-hidden>·</span>
                      <span className="truncate">
                        {item.campaign_name}
                        {item.step_number ? ` · Step ${item.step_number}` : ""}
                      </span>
                    </>
                  ) : (
                    <>
                      <span aria-hidden>·</span>
                      <span>One-off</span>
                    </>
                  )}
                  <GenerationBadge mode={item.generation_mode} className="ml-auto" />
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
