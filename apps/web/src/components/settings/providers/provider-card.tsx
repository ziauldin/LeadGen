"use client";

import { useState } from "react";
import { CheckCircle2, ChevronDown, ChevronUp, Trash2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ProviderStatusBadge } from "@/components/settings/providers/provider-status-badge";
import { WebhookUrls } from "@/components/settings/providers/webhook-urls";
import { WarmupForm } from "@/components/settings/providers/warmup-form";
import type { ProviderDefinition } from "@/components/settings/providers/provider-catalog";
import type { ProviderCredential, ProviderType } from "@/lib/api/types";
import { cn } from "@/lib/utils";

function formatWhen(value: string | null): string {
  if (!value) return "";
  return new Date(value).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export type ProviderCardActions = {
  onConfigure: () => void;
  onTest: () => void;
  onActivate: () => void;
  onDelete: () => void;
  busy: "test" | "activate" | null;
};

export function ProviderCard({
  providerType,
  definition,
  credential,
  canEdit,
  actions,
}: {
  providerType: ProviderType;
  definition: ProviderDefinition;
  credential: ProviderCredential | undefined;
  canEdit: boolean;
  actions: ProviderCardActions;
}) {
  const isActive = credential?.is_active ?? false;
  const isEmailAccount = providerType === "email" && definition.name !== "mock" && credential;
  const [showSending, setShowSending] = useState(false);
  const webhookCount = Object.keys(credential?.webhook_urls ?? {}).length;
  const headingId = `provider-${providerType}-${definition.name}`;

  return (
    <article
      aria-labelledby={headingId}
      className={cn(
        "flex flex-col rounded-lg border bg-white p-4 shadow-sm",
        isActive ? "border-[var(--primary)] ring-1 ring-[var(--primary)]/20" : "border-[var(--outline-variant)]",
      )}
    >
      <div className="mb-1 flex items-start justify-between gap-3">
        <h3 id={headingId} className="text-[14px] font-semibold text-[var(--on-surface)]">
          {definition.label}
        </h3>
        <ProviderStatusBadge credential={credential} />
      </div>
      <p className="mb-3 text-[13px] text-[var(--on-surface-variant)]">{definition.description}</p>

      {credential?.masked_summary ? (
        <p className="mb-3 break-words rounded-md bg-[var(--surface-container-low)] px-2.5 py-1.5 font-mono text-[11px] text-[var(--on-surface)]">
          {credential.masked_summary}
        </p>
      ) : null}

      {credential?.last_tested_at ? (
        <p
          className={cn(
            "mb-3 flex items-start gap-1.5 text-[12px]",
            credential.last_test_status === "success" ? "text-[var(--secondary)]" : "text-[var(--error)]",
          )}
          role="status"
        >
          {credential.last_test_status === "success" ? (
            <CheckCircle2 className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          ) : (
            <XCircle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          )}
          <span>
            {credential.last_test_message ||
              (credential.last_test_status === "success" ? "Connection works" : "Test failed")}
            <span className="text-[var(--on-surface-variant)]"> · {formatWhen(credential.last_tested_at)}</span>
          </span>
        </p>
      ) : null}

      {isEmailAccount ? (
        <div className="mb-3 rounded-md border border-[var(--outline-variant)]">
          <button
            type="button"
            onClick={() => setShowSending((value) => !value)}
            aria-expanded={showSending}
            className="flex w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-[12px] font-medium text-[var(--on-surface)] hover:bg-[var(--surface-container-low)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)]"
          >
            <span>
              {webhookCount ? "Webhooks & warm-up" : "Warm-up"}
              {credential.warmup_enabled ? (
                <span className="ml-2 rounded bg-[var(--tertiary-fixed)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--on-tertiary-fixed)]">
                  Warming up
                </span>
              ) : null}
            </span>
            {showSending ? <ChevronUp className="size-4" aria-hidden /> : <ChevronDown className="size-4" aria-hidden />}
          </button>
          {showSending ? (
            <div className="space-y-4 border-t border-[var(--outline-variant)] p-3">
              <WebhookUrls urls={credential.webhook_urls} help={definition.webhookHelp} />
              <WarmupForm credential={credential} canEdit={canEdit} />
            </div>
          ) : null}
        </div>
      ) : null}

      {canEdit ? (
        <div className="mt-auto flex flex-wrap items-center gap-2 border-t border-[var(--outline-variant)] pt-3">
          <Button size="sm" variant="outline" onClick={actions.onConfigure}>
            {credential ? "Update" : "Set up"}
          </Button>
          {credential ? (
            <Button
              size="sm"
              variant="outline"
              onClick={actions.onTest}
              disabled={actions.busy !== null}
            >
              {actions.busy === "test" ? "Testing…" : "Test"}
            </Button>
          ) : null}
          {credential && !isActive ? (
            <Button size="sm" onClick={actions.onActivate} disabled={actions.busy !== null}>
              {actions.busy === "activate" ? "Activating…" : "Activate"}
            </Button>
          ) : null}
          {credential && definition.name !== "mock" ? (
            <Button
              size="icon-sm"
              variant="ghost"
              className="ml-auto text-[var(--on-surface-variant)] hover:text-[var(--error)]"
              onClick={actions.onDelete}
              aria-label={`Delete ${definition.label} credentials`}
            >
              <Trash2 aria-hidden />
            </Button>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}
