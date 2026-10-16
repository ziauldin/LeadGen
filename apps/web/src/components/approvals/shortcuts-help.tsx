"use client";

import type { ReactNode } from "react";
import { Keyboard } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { SHORTCUTS } from "@/components/approvals/use-approval-shortcuts";
import { cn } from "@/lib/utils";

export function Kbd({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <kbd
      className={cn(
        "inline-flex h-5 min-w-5 items-center justify-center rounded border border-[var(--outline-variant)] bg-white px-1 font-mono text-[11px] font-medium text-[var(--on-surface)] shadow-[0_1px_0_var(--outline-variant)]",
        className,
      )}
    >
      {children}
    </kbd>
  );
}

/** One line of the most useful shortcuts, shown under the queue on larger screens. */
export function ShortcutHint({ onShowAll }: { onShowAll: () => void }) {
  const items: Array<[string, string]> = [
    ["j", "next"],
    ["k", "previous"],
    ["a", "approve"],
    ["r", "reject"],
    ["e", "edit"],
  ];
  return (
    <div className="hidden flex-wrap items-center gap-x-4 gap-y-1 text-xs text-[var(--on-surface-variant)] md:flex">
      <Keyboard className="size-3.5" aria-hidden />
      {items.map(([key, label]) => (
        <span key={key} className="inline-flex items-center gap-1.5">
          <Kbd>{key}</Kbd>
          {label}
        </span>
      ))}
      <button
        type="button"
        onClick={onShowAll}
        className="inline-flex items-center gap-1.5 rounded hover:text-[var(--primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)]"
      >
        <Kbd>?</Kbd>
        all shortcuts
      </button>
    </div>
  );
}

export function ShortcutsDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[400px]">
        <DialogHeader>
          <DialogTitle>Keyboard shortcuts</DialogTitle>
          <DialogDescription>
            Work through the queue without the mouse. Shortcuts pause while you type or a dialog is
            open.
          </DialogDescription>
        </DialogHeader>
        <dl className="grid gap-2 text-[13px]">
          {SHORTCUTS.map((shortcut) => (
            <div key={shortcut.label} className="flex items-center justify-between gap-4">
              <dt className="text-[var(--on-surface-variant)]">{shortcut.label}</dt>
              <dd className="flex gap-1">
                {shortcut.keys.map((key) => (
                  <Kbd key={key}>{key}</Kbd>
                ))}
              </dd>
            </div>
          ))}
          <div className="flex items-center justify-between gap-4">
            <dt className="text-[var(--on-surface-variant)]">Save while editing</dt>
            <dd className="flex gap-1">
              <Kbd>Ctrl</Kbd>
              <Kbd>Enter</Kbd>
            </dd>
          </div>
          <div className="flex items-center justify-between gap-4">
            <dt className="text-[var(--on-surface-variant)]">Cancel editing</dt>
            <dd>
              <Kbd>Esc</Kbd>
            </dd>
          </div>
        </dl>
      </DialogContent>
    </Dialog>
  );
}
