"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlertTriangle, CheckCircle2, Mail } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SettingsCard } from "@/components/settings/settings-card";
import { useWorkspace } from "@/hooks/use-workspace";
import { mailboxesApi } from "@/lib/api/endpoints";
import type { components } from "@/lib/api/schema";

type Account = components["schemas"]["SenderAccount"];

function LimitEditor({ account, disabled }: { account: Account; disabled: boolean }) {
  const queryClient = useQueryClient();
  const [value, setValue] = useState(account.daily_limit ? String(account.daily_limit) : "");
  const save = useMutation({
    mutationFn: () => mailboxesApi.updateAccount(account.id, { daily_limit: value ? Number(value) : null }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["sending-accounts"] });
      toast.success("Daily limit saved");
    },
  });
  return (
    <form
      className="flex items-end gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        save.mutate();
      }}
    >
      <div className="grid gap-1">
        <label htmlFor={`limit-${account.id}`} className="text-[12px] text-[var(--on-surface-variant)]">
          Daily limit
        </label>
        <Input
          id={`limit-${account.id}`}
          type="number"
          min={1}
          max={2000}
          className="h-8 w-24 bg-white"
          value={value}
          placeholder="None"
          disabled={disabled}
          onChange={(event) => setValue(event.target.value)}
        />
      </div>
      <Button type="submit" size="sm" variant="outline" disabled={disabled || save.isPending}>
        Save
      </Button>
    </form>
  );
}

export function MailboxesCard() {
  const queryClient = useQueryClient();
  const { can } = useWorkspace();
  const canEdit = can("providers.manage");
  const providers = useQuery({ queryKey: ["mailbox-providers"], queryFn: mailboxesApi.providers, staleTime: Infinity });
  const accounts = useQuery({ queryKey: ["sending-accounts"], queryFn: mailboxesApi.accounts });

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const result = params.get("mailbox");
    if (result === "connected") toast.success("Mailbox connected. It starts slowly while it warms up.");
    if (result === "error") toast.error(params.get("detail") || "We couldn't connect that mailbox. Please try again.");
    if (result === "cancelled") toast("Mailbox connection cancelled.");
  }, []);

  const connect = useMutation({
    mutationFn: (provider: string) => mailboxesApi.connect(provider),
    onSuccess: (result) => window.location.assign(result.url),
  });
  const resume = useMutation({
    mutationFn: (id: number) => mailboxesApi.updateAccount(id, { resume: true }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["sending-accounts"] }),
  });

  const available = (providers.data ?? []).filter((p) => p.available);
  const mailboxes = (accounts.data ?? []).filter((a) => a.is_mailbox);

  if (!available.length && !mailboxes.length) return null;

  return (
    <SettingsCard
      id="mailboxes"
      title="Mailboxes"
      description="Send from your own Gmail or Microsoft 365 inboxes. Replies sync automatically, and campaigns can rotate between several mailboxes."
      actions={
        canEdit
          ? available.map((provider) => (
              <Button
                key={provider.key}
                size="sm"
                variant="outline"
                disabled={connect.isPending}
                onClick={() => connect.mutate(provider.key)}
              >
                <Mail aria-hidden /> Connect {provider.key === "gmail" ? "Gmail" : "Microsoft 365"}
              </Button>
            ))
          : null
      }
    >
      {mailboxes.length ? (
        <ul aria-label="Connected mailboxes" className="divide-y divide-[var(--outline-variant)]">
          {mailboxes.map((account) => (
            <li key={account.id} className="flex flex-col gap-3 py-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <p className="flex items-center gap-2 text-[14px] font-medium">
                  {account.healthy ? (
                    <CheckCircle2 className="size-4 text-[var(--primary)]" aria-label="Healthy" />
                  ) : (
                    <AlertTriangle className="size-4 text-[var(--error)]" aria-label="Needs attention" />
                  )}
                  {account.email ?? account.label}
                </p>
                <p className="text-[12px] text-[var(--on-surface-variant)]">
                  {account.provider === "gmail" ? "Gmail" : "Microsoft 365"}
                  {account.cap_today !== null ? ` · up to ${account.cap_today} emails today` : ""}
                </p>
                {account.problem ? <p className="text-[12px] text-[var(--error)]">{account.problem}</p> : null}
              </div>
              <div className="flex flex-wrap items-end gap-2">
                <LimitEditor account={account} disabled={!canEdit} />
                {!account.healthy && canEdit ? (
                  account.problem?.startsWith("Reconnect") ? (
                    <Button size="sm" onClick={() => connect.mutate(account.provider)}>
                      Reconnect
                    </Button>
                  ) : (
                    <Button size="sm" variant="outline" disabled={resume.isPending} onClick={() => resume.mutate(account.id)}>
                      Resume
                    </Button>
                  )
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-[13px] text-[var(--on-surface-variant)]">No mailboxes connected yet.</p>
      )}
    </SettingsCard>
  );
}
