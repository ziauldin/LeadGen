"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Check, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { WEBHOOK_LABELS } from "@/components/settings/providers/provider-catalog";

function CopyButton({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      variant="outline"
      size="icon-sm"
      aria-label={`Copy ${label} URL`}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value);
          setCopied(true);
          toast.success(`${label} URL copied`);
          window.setTimeout(() => setCopied(false), 2000);
        } catch {
          toast.error("Couldn't copy. Select the URL and copy it by hand.");
        }
      }}
    >
      {copied ? <Check aria-hidden /> : <Copy aria-hidden />}
    </Button>
  );
}

/** URLs to paste into the email provider's dashboard so bounces and replies reach us. */
export function WebhookUrls({ urls, help }: { urls: Record<string, string>; help?: string }) {
  const entries = Object.entries(urls);
  if (entries.length === 0) return null;
  return (
    <div className="space-y-2">
      <p className="text-[12px] font-semibold text-[var(--on-surface)]">Webhook URLs</p>
      {help ? (
        <p className="text-[12px] leading-[18px] text-[var(--on-surface-variant)]">{help}</p>
      ) : null}
      <ul className="space-y-2">
        {entries.map(([key, url]) => {
          const meta = WEBHOOK_LABELS[key] ?? { label: key.replaceAll("_", " "), hint: "" };
          return (
            <li key={key}>
              <p className="text-[12px] text-[var(--on-surface-variant)]">
                <span className="font-medium text-[var(--on-surface)]">{meta.label}</span>
                {meta.hint ? ` — ${meta.hint}` : ""}
              </p>
              <div className="mt-1 flex items-center gap-2">
                <code className="min-w-0 flex-1 truncate rounded-md border border-[var(--outline-variant)] bg-[var(--surface-container-low)] px-2 py-1.5 font-mono text-[12px] text-[var(--on-surface)]" title={url}>
                  {url}
                </code>
                <CopyButton value={url} label={meta.label} />
              </div>
            </li>
          );
        })}
      </ul>
      <p className="text-[11px] text-[var(--on-surface-variant)]">
        Keep these private: each contains a token unique to this account.
      </p>
    </div>
  );
}
