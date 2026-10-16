"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { settingsApi } from "@/lib/api/endpoints";

export type SuppressionKind = "email" | "domain";

const KIND_LABELS: Record<SuppressionKind, string> = {
  email: "Email address",
  domain: "Whole domain",
};

/** Shared mailbox providers: blocking one as a domain would block everyone who uses it. */
export const FREEMAIL_DOMAINS = new Set([
  "gmail.com",
  "googlemail.com",
  "outlook.com",
  "hotmail.com",
  "hotmail.co.uk",
  "live.com",
  "live.co.uk",
  "msn.com",
  "yahoo.com",
  "yahoo.co.uk",
  "ymail.com",
  "icloud.com",
  "me.com",
  "mac.com",
  "aol.com",
  "proton.me",
  "protonmail.com",
  "gmx.com",
  "gmx.de",
  "mail.com",
  "zoho.com",
  "yandex.com",
  "btinternet.com",
  "sky.com",
  "virginmedia.com",
]);

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const DOMAIN_RE = /^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/;

/** Returns an error message, or null when the value is fine for the chosen type. */
export function validateSuppression(kind: SuppressionKind, raw: string): string | null {
  const value = raw.trim().toLowerCase();
  if (!value) return kind === "email" ? "Enter an email address." : "Enter a domain.";
  if (kind === "email") {
    if (!value.includes("@") && DOMAIN_RE.test(value)) {
      return "That looks like a domain. Choose \"Whole domain\" to block everyone at it.";
    }
    if (!EMAIL_RE.test(value)) return "Enter a valid email address, e.g. name@company.com.";
    return null;
  }
  const domain = value.replace(/^@/, "");
  if (domain.includes("@")) {
    return "Enter just the domain (e.g. company.com), or choose \"Email address\" to block one person.";
  }
  if (!DOMAIN_RE.test(domain)) return "Enter a valid domain, e.g. company.com.";
  if (FREEMAIL_DOMAINS.has(domain)) {
    return `${domain} is a shared email provider, so it can't be blocked as a whole. Block individual addresses instead.`;
  }
  return null;
}

export function SuppressionAddForm({ disabled = false }: { disabled?: boolean }) {
  const queryClient = useQueryClient();
  const [kind, setKind] = useState<SuppressionKind>("email");
  const [value, setValue] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const add = useMutation({
    mutationFn: () => {
      const cleaned = value.trim().toLowerCase();
      return settingsApi.createSuppression({
        ...(kind === "email" ? { email: cleaned } : { domain: cleaned.replace(/^@/, "") }),
        reason: reason.trim() || undefined,
      });
    },
    meta: { silent: true },
    onSuccess: (suppression) => {
      void queryClient.invalidateQueries({ queryKey: ["suppressions"] });
      toast.success(`${suppression.email ?? suppression.domain} won't be emailed`);
      setValue("");
      setReason("");
      setError(null);
    },
    onError: (err) => setError(err.message),
  });

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const problem = validateSuppression(kind, value);
    setError(problem);
    if (!problem) add.mutate();
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-3" aria-label="Add a suppression">
      <div className="grid gap-3 sm:grid-cols-[170px_minmax(0,1fr)]">
        <div className="space-y-1.5">
          <label htmlFor="suppression-kind" className="block text-[13px] font-medium text-[var(--on-surface)]">
            Type
          </label>
          <Select
            value={kind}
            items={KIND_LABELS}
            onValueChange={(next) => {
              if (!next) return;
              setKind(next as SuppressionKind);
              setError(null);
            }}
            disabled={disabled}
          >
            <SelectTrigger id="suppression-kind" className="h-9 w-full bg-white">
              <SelectValue />
            </SelectTrigger>
            <SelectContent alignItemWithTrigger={false}>
              <SelectItem value="email">{KIND_LABELS.email}</SelectItem>
              <SelectItem value="domain">{KIND_LABELS.domain}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <label htmlFor="suppression-value" className="block text-[13px] font-medium text-[var(--on-surface)]">
            {kind === "email" ? "Email address" : "Domain"}
          </label>
          <Input
            id="suppression-value"
            type={kind === "email" ? "email" : "text"}
            value={value}
            onChange={(event) => {
              setValue(event.target.value);
              if (error) setError(null);
            }}
            placeholder={kind === "email" ? "name@company.com" : "company.com"}
            autoComplete="off"
            spellCheck={false}
            className="h-9 bg-white"
            disabled={disabled}
            aria-invalid={Boolean(error)}
            aria-describedby={error ? "suppression-error" : "suppression-hint"}
          />
        </div>
      </div>
      <div className="space-y-1.5">
        <label htmlFor="suppression-reason" className="block text-[13px] font-medium text-[var(--on-surface)]">
          Reason <span className="font-normal text-[var(--on-surface-variant)]">(optional)</span>
        </label>
        <Input
          id="suppression-reason"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          placeholder="e.g. Asked by phone not to be contacted"
          maxLength={255}
          className="h-9 bg-white"
          disabled={disabled}
        />
      </div>

      {error ? (
        <p id="suppression-error" role="alert" className="text-[13px] text-[var(--error)]">
          {error}
        </p>
      ) : (
        <p id="suppression-hint" className="text-[12px] leading-[18px] text-[var(--on-surface-variant)]">
          {kind === "email"
            ? "Blocks this one address in every campaign, now and in future."
            : "Blocks everyone at this company's domain. Shared providers like gmail.com or outlook.com can't be blocked as a whole, because that would block everyone who uses them."}
        </p>
      )}

      <Button type="submit" disabled={disabled || add.isPending}>
        <Plus aria-hidden />
        {add.isPending ? "Adding…" : "Add to suppression list"}
      </Button>
    </form>
  );
}
