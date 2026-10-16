"use client";

import { useEffect, useRef } from "react";

export type ShortcutHandlers = {
  next: () => void;
  previous: () => void;
  approve: () => void;
  reject: () => void;
  edit: () => void;
  help: () => void;
};

export const SHORTCUTS: Array<{ keys: string[]; label: string }> = [
  { keys: ["j"], label: "Next draft" },
  { keys: ["k"], label: "Previous draft" },
  { keys: ["a"], label: "Approve and move to the next draft" },
  { keys: ["r"], label: "Reject (asks for an optional reason)" },
  { keys: ["e"], label: "Edit subject and body" },
  { keys: ["?"], label: "Show these shortcuts" },
];

/** True when the key press belongs to something the user is typing in or a popup that's open. */
export function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  const tag = target.tagName;
  if (tag === "TEXTAREA" || tag === "SELECT") return true;
  if (tag === "INPUT") {
    const type = (target as HTMLInputElement).type;
    return !["checkbox", "radio", "button", "submit", "reset"].includes(type);
  }
  return Boolean(target.closest("[role='combobox'], [role='listbox'], [role='menu']"));
}

function popupOpen(): boolean {
  return Boolean(
    document.querySelector(
      "[role='dialog'], [role='alertdialog'], [role='menu'], [role='listbox']",
    ),
  );
}

/**
 * Single-key shortcuts for the review queue. They never fire while typing, while a dialog or
 * menu is open, with modifier keys held, or when `enabled` is false (e.g. while editing).
 */
export function useApprovalShortcuts(handlers: ShortcutHandlers, enabled: boolean) {
  const ref = useRef(handlers);
  useEffect(() => {
    ref.current = handlers;
  });

  useEffect(() => {
    if (!enabled) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.defaultPrevented || event.repeat) return;
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (isTypingTarget(event.target) || popupOpen()) return;
      const actions: Record<string, (() => void) | undefined> = {
        j: ref.current.next,
        k: ref.current.previous,
        a: ref.current.approve,
        r: ref.current.reject,
        e: ref.current.edit,
        "?": ref.current.help,
      };
      const key = event.key === "?" ? "?" : event.key.toLowerCase();
      if (event.shiftKey && key !== "?") return;
      const action = actions[key];
      if (!action) return;
      event.preventDefault();
      action();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [enabled]);
}
