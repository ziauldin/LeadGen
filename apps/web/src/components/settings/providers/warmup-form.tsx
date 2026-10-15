"use client";

import { useEffect, useId, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Flame } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { providerSettingsApi } from "@/lib/api/endpoints";
import type { ProviderCredential } from "@/lib/api/types";

/** Today's warm-up cap, as the dispatcher works it out: start + increment per day, up to max. */
export function warmupCapToday(credential: ProviderCredential): number | null {
  if (!credential.warmup_enabled || !credential.warmup_started_at) return null;
  // Whole UTC calendar days since warm-up started, like the API.
  const utcDay = (time: number) => Math.floor(time / 86_400_000);
  const days = Math.max(
    0,
    utcDay(Date.now()) - utcDay(new Date(credential.warmup_started_at).getTime()),
  );
  const cap = credential.warmup_start_volume + credential.warmup_daily_increment * days;
  return credential.warmup_max ? Math.min(cap, credential.warmup_max) : cap;
}

type Draft = { enabled: boolean; start: string; increment: string; maximum: string };

function fromCredential(credential: ProviderCredential): Draft {
  return {
    enabled: credential.warmup_enabled,
    start: String(credential.warmup_start_volume || 10),
    increment: String(credential.warmup_daily_increment ?? 5),
    maximum: credential.warmup_max ? String(credential.warmup_max) : "",
  };
}

export function WarmupForm({
  credential,
  canEdit,
}: {
  credential: ProviderCredential;
  canEdit: boolean;
}) {
  const queryClient = useQueryClient();
  const baseId = useId();
  const [draft, setDraft] = useState<Draft>(() => fromCredential(credential));
  const [error, setError] = useState<string | null>(null);
  useEffect(() => setDraft(fromCredential(credential)), [credential]);

  const save = useMutation({
    mutationFn: () =>
      providerSettingsApi.warmup(credential.id, {
        enabled: draft.enabled,
        start_volume: Number(draft.start),
        daily_increment: Number(draft.increment),
        maximum: draft.maximum ? Number(draft.maximum) : undefined,
      }),
    onSuccess: (updated) => {
      void queryClient.invalidateQueries({ queryKey: ["provider-settings"] });
      toast.success(updated.warmup_enabled ? "Warm-up schedule saved" : "Warm-up turned off");
    },
  });

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const start = Number(draft.start);
    const increment = Number(draft.increment);
    const maximum = draft.maximum ? Number(draft.maximum) : null;
    if (!Number.isInteger(start) || start < 1 || start > 1000) {
      return setError("Starting volume must be a whole number from 1 to 1,000.");
    }
    if (!Number.isInteger(increment) || increment < 0 || increment > 1000) {
      return setError("Daily increase must be a whole number from 0 to 1,000.");
    }
    if (maximum !== null && (!Number.isInteger(maximum) || maximum < 1 || maximum > 100_000)) {
      return setError("Maximum must be a whole number from 1 to 100,000, or empty for no cap.");
    }
    if (maximum !== null && maximum < start) {
      return setError("Maximum can't be lower than the starting volume.");
    }
    setError(null);
    save.mutate();
  }

  const today = warmupCapToday(credential);
  const changed =
    JSON.stringify(draft) !== JSON.stringify(fromCredential(credential));

  return (
    <form onSubmit={submit} className="space-y-3" noValidate>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="flex items-center gap-1.5 text-[12px] font-semibold text-[var(--on-surface)]">
            <Flame className="size-3.5 text-[var(--tertiary)]" aria-hidden />
            Warm-up
          </p>
          <p className="text-[12px] leading-[18px] text-[var(--on-surface-variant)]">
            New domains and mailboxes should start slowly. Warm-up limits how many emails this
            account sends per day and raises the limit gradually.
          </p>
        </div>
        <label className="flex shrink-0 items-center gap-2 text-[12px] font-medium text-[var(--on-surface)]">
          <input
            type="checkbox"
            role="switch"
            aria-checked={draft.enabled}
            className="size-4 accent-[var(--primary)]"
            checked={draft.enabled}
            disabled={!canEdit}
            onChange={(event) => setDraft((value) => ({ ...value, enabled: event.target.checked }))}
          />
          {draft.enabled ? "On" : "Off"}
        </label>
      </div>

      {draft.enabled ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {(
            [
              ["start", "Start at (per day)", "10"],
              ["increment", "Add each day", "5"],
              ["maximum", "Stop at (optional)", "No cap"],
            ] as const
          ).map(([key, label, placeholder]) => (
            <div key={key} className="space-y-1">
              <label htmlFor={`${baseId}-${key}`} className="block text-[12px] text-[var(--on-surface-variant)]">
                {label}
              </label>
              <Input
                id={`${baseId}-${key}`}
                type="number"
                inputMode="numeric"
                min={key === "increment" ? 0 : 1}
                placeholder={placeholder}
                className="h-8 bg-white"
                value={draft[key]}
                disabled={!canEdit}
                onChange={(event) => setDraft((value) => ({ ...value, [key]: event.target.value }))}
              />
            </div>
          ))}
        </div>
      ) : null}

      {today !== null ? (
        <p className="text-[12px] text-[var(--on-surface-variant)]">
          Today&apos;s limit: <span className="font-semibold text-[var(--on-surface)]">{today}</span>{" "}
          emails. Campaign daily limits still apply on top.
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="text-[12px] text-[var(--error)]">
          {error}
        </p>
      ) : null}
      {canEdit ? (
        <Button type="submit" size="sm" variant="outline" disabled={!changed || save.isPending}>
          {save.isPending ? "Saving…" : "Save warm-up"}
        </Button>
      ) : null}
    </form>
  );
}
