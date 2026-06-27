"use client";

import { X } from "lucide-react";

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  onConfirm,
  loading = false,
  destructive = false,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  loading?: boolean;
  destructive?: boolean;
}) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-in fade-in duration-200">
      <div
        className="bg-white border rounded-xl w-full max-w-[440px] shadow-lg overflow-hidden flex flex-col"
        style={{ borderColor: "var(--outline-variant)" }}
      >
        {/* Header */}
        <div
          className="px-6 py-4 border-b flex items-center justify-between"
          style={{ borderColor: "var(--outline-variant)" }}
        >
          <h3 className="text-[16px] font-bold" style={{ color: "var(--on-surface)" }}>
            {title}
          </h3>
          <button
            onClick={() => onOpenChange(false)}
            className="text-slate-400 hover:text-slate-600 transition-colors"
            disabled={loading}
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        {description && (
          <div className="px-6 py-4">
            <p className="text-[13px] leading-[20px]" style={{ color: "var(--on-surface-variant)" }}>
              {description}
            </p>
          </div>
        )}

        {/* Footer */}
        <div
          className="px-6 py-4 border-t flex items-center justify-end gap-3"
          style={{ borderColor: "var(--outline-variant)", background: "var(--surface)" }}
        >
          <button
            onClick={() => onOpenChange(false)}
            disabled={loading}
            className="px-4 py-2 border rounded text-[13px] font-semibold bg-white transition-colors"
            style={{ borderColor: "var(--outline-variant)", color: "var(--on-surface)" }}
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className="px-4 py-2 rounded text-[13px] font-semibold text-white transition-opacity disabled:opacity-60"
            style={{
              background: destructive ? "var(--error)" : "var(--primary)",
            }}
          >
            {loading ? "Processing…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
