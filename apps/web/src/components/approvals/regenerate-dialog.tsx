"use client";

import { useState } from "react";
import { AlertTriangle, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { TemplateSelect } from "@/components/templates/template-select";
import type { DraftOptions } from "@/lib/api/endpoints";
import type { GenerationMode } from "@/lib/api/types";

/**
 * Rewrite a draft from a template, or have AI write it (the template is the fallback and
 * the base for tone). The draft stays in the queue for review either way.
 */
export function RegenerateDialog({
  mode,
  onOpenChange,
  defaultTemplateId,
  onConfirm,
  loading,
  error,
}: {
  /** The dialog is open while a mode is set. */
  mode: GenerationMode | null;
  onOpenChange: (open: boolean) => void;
  defaultTemplateId?: string | null;
  onConfirm: (options: DraftOptions) => void;
  loading?: boolean;
  error?: string | null;
}) {
  return (
    <Dialog open={mode !== null} onOpenChange={(next) => !loading && onOpenChange(next)}>
      <DialogContent className="sm:max-w-[480px]">
        {mode ? (
          <RegenerateForm
            key={mode}
            mode={mode}
            defaultTemplateId={defaultTemplateId}
            onCancel={() => onOpenChange(false)}
            onConfirm={onConfirm}
            loading={loading}
            error={error}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function RegenerateForm({
  mode,
  defaultTemplateId,
  onCancel,
  onConfirm,
  loading,
  error,
}: {
  mode: GenerationMode;
  defaultTemplateId?: string | null;
  onCancel: () => void;
  onConfirm: (options: DraftOptions) => void;
  loading?: boolean;
  error?: string | null;
}) {
  const [templateId, setTemplateId] = useState(defaultTemplateId || "system:intro");
  const [instructions, setInstructions] = useState("");
  const ai = mode === "ai";

  return (
    <form
      className="grid gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        onConfirm({ mode, templateId, instructions: ai ? instructions.trim() : undefined });
      }}
    >
      <DialogHeader>
        <DialogTitle>{ai ? "Write with AI" : "Rewrite from template"}</DialogTitle>
        <DialogDescription>
          {ai
            ? "AI writes a fresh draft for this lead, using the template for structure. It replaces the current subject and body."
            : "Replaces the current subject and body with the chosen template, filled in for this lead."}
        </DialogDescription>
      </DialogHeader>

      <div className="grid gap-1.5">
        <label htmlFor="regenerate-template" className="text-[13px] font-medium">
          Template
        </label>
        <TemplateSelect id="regenerate-template" value={templateId} onChange={setTemplateId} />
      </div>

      {ai ? (
        <div className="grid gap-1.5">
          <label htmlFor="regenerate-instructions" className="text-[13px] font-medium">
            Instructions <span className="font-normal text-muted-foreground">(optional)</span>
          </label>
          <Textarea
            id="regenerate-instructions"
            rows={4}
            maxLength={2000}
            value={instructions}
            placeholder="e.g. Keep it under 80 words and mention their recent expansion"
            onChange={(event) => setInstructions(event.target.value)}
          />
          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Sparkles className="size-3.5" aria-hidden />
            The new draft still waits here for a person to review it.
          </p>
        </div>
      ) : null}

      {error ? (
        <p
          role="alert"
          className="flex gap-2 rounded-md border border-[var(--error)]/30 bg-[var(--error-container)]/60 px-3 py-2 text-[13px] text-[var(--on-error-container)]"
        >
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
          {error}
        </p>
      ) : null}

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel} disabled={loading}>
          Cancel
        </Button>
        <Button type="submit" disabled={loading}>
          {loading ? "Writing…" : ai ? "Write new draft" : "Rewrite draft"}
        </Button>
      </DialogFooter>
    </form>
  );
}
