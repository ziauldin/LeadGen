"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, HelpCircle, ShieldCheck, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ErrorState } from "@/components/shared/loading-error";
import { SettingsCard } from "@/components/settings/settings-card";
import { settingsApi } from "@/lib/api/endpoints";
import type { DeliverabilityReport } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type Status = "pass" | "warn" | "fail" | "unknown";

const STATUS: Record<Status, { label: string; icon: typeof CheckCircle2; className: string }> = {
  pass: { label: "Pass", icon: CheckCircle2, className: "text-[var(--secondary)]" },
  warn: { label: "Warning", icon: AlertTriangle, className: "text-[var(--tertiary)]" },
  fail: { label: "Fail", icon: XCircle, className: "text-[var(--error)]" },
  unknown: { label: "Couldn't check", icon: HelpCircle, className: "text-[var(--on-surface-variant)]" },
};

const OVERALL: Record<DeliverabilityReport["overall"], { title: string; text: string; className: string }> = {
  pass: {
    title: "Looks good",
    text: "This domain has the records mailbox providers expect from bulk senders.",
    className: "border-[var(--secondary)]/30 bg-[var(--secondary-fixed)]/40",
  },
  warn: {
    title: "Mostly fine, with warnings",
    text: "Emails should be delivered, but fixing the warnings below will help keep you out of spam.",
    className: "border-[var(--tertiary-fixed-dim)] bg-[var(--tertiary-fixed)]/40",
  },
  fail: {
    title: "Needs fixing before you send",
    text: "Gmail, Yahoo and others are likely to reject or spam-folder these emails until the failing checks are fixed.",
    className: "border-[var(--error)]/30 bg-[var(--error-container)]/50",
  },
};

/** What each DNS check is for, in plain words. */
const CHECK_ABOUT: Record<string, string> = {
  spf: "Lists the servers allowed to send email for your domain.",
  dkim: "A signature on each email that proves it came from you and wasn't changed.",
  dmarc: "Tells mailbox providers what to do with emails that fail SPF or DKIM.",
  mx: "Mail servers for your domain, so replies can reach you.",
};

function checkAbout(name: string) {
  return CHECK_ABOUT[name.toLowerCase()] ?? (name.toLowerCase().includes("mx") ? CHECK_ABOUT.mx : "");
}

export function DeliverabilityCheck() {
  const [domain, setDomain] = useState("");
  const check = useMutation({
    mutationFn: (value: string) => settingsApi.deliverability(value.trim() || undefined),
    meta: { silent: true },
  });

  const report = check.data;
  return (
    <div className="space-y-6">
      <SettingsCard
        id="deliverability"
        title="Deliverability check"
        description={
          <>
            Since 2024, Gmail and Yahoo require bulk senders to authenticate their domain with SPF,
            DKIM and DMARC, and to offer one-click unsubscribe. Without these, emails are rejected
            or sent to spam. Run this after setting up a sending account or changing DNS.
          </>
        }
      >
        <form
          onSubmit={(event) => {
            event.preventDefault();
            check.mutate(domain);
          }}
          className="flex flex-col gap-3 sm:flex-row sm:items-end"
        >
          <div className="flex-1 space-y-1.5">
            <label htmlFor="deliverability-domain" className="block text-[13px] font-medium text-[var(--on-surface)]">
              Domain
            </label>
            <Input
              id="deliverability-domain"
              value={domain}
              onChange={(event) => setDomain(event.target.value)}
              placeholder="yourcompany.com"
              autoComplete="off"
              spellCheck={false}
              className="h-9 bg-white"
              aria-describedby="deliverability-domain-hint"
            />
          </div>
          <Button type="submit" className="h-9" disabled={check.isPending}>
            <ShieldCheck aria-hidden />
            {check.isPending ? "Checking…" : "Run check"}
          </Button>
        </form>
        <p id="deliverability-domain-hint" className="mt-1.5 text-[12px] text-[var(--on-surface-variant)]">
          Leave empty to check the domain of your active sending account&apos;s from address.
        </p>
        {check.error ? (
          <div className="mt-4">
            <ErrorState error={check.error} onRetry={() => check.mutate(domain)} />
          </div>
        ) : null}
      </SettingsCard>

      {report ? (
        <section aria-labelledby="report-heading" aria-live="polite" className="space-y-4">
          <div className={cn("rounded-lg border p-4", OVERALL[report.overall].className)}>
            <h2 id="report-heading" className="text-[15px] font-semibold text-[var(--on-surface)]">
              {report.domain}: {OVERALL[report.overall].title}
            </h2>
            <p className="mt-1 text-[13px] text-[var(--on-surface-variant)]">
              {OVERALL[report.overall].text}
              {report.provider ? ` Checked against your ${report.provider} sending account.` : ""}
            </p>
          </div>

          <ul className="space-y-3">
            {report.checks.map((item, checkIndex) => {
              const status = STATUS[item.status as Status] ?? STATUS.unknown;
              const Icon = status.icon;
              return (
                <li
                  key={`${item.name}-${checkIndex}`}
                  className="rounded-lg border border-[var(--outline-variant)] bg-white p-4 shadow-sm"
                >
                  <div className="flex items-start gap-3">
                    <Icon className={cn("mt-0.5 size-5 shrink-0", status.className)} aria-hidden />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-[14px] font-semibold text-[var(--on-surface)]">
                          {item.name}
                        </h3>
                        <span className={cn("text-[12px] font-semibold", status.className)}>
                          {status.label}
                        </span>
                      </div>
                      {checkAbout(item.name) ? (
                        <p className="text-[12px] text-[var(--on-surface-variant)]">{checkAbout(item.name)}</p>
                      ) : null}
                      <p className="mt-1 text-[13px] leading-[20px] text-[var(--on-surface)]">
                        {item.detail}
                      </p>
                      {item.records.length > 0 ? (
                        <div className="mt-3">
                          <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-[var(--on-surface-variant)]">
                            Records found
                          </p>
                          <ul className="space-y-1">
                            {item.records.map((record, index) => (
                              <li
                                key={`${item.name}-${index}`}
                                className="overflow-x-auto rounded-md bg-[var(--surface-container-low)] px-2.5 py-1.5 font-mono text-[12px] text-[var(--on-surface)]"
                              >
                                <code className="whitespace-pre-wrap break-all">{record}</code>
                              </li>
                            ))}
                          </ul>
                        </div>
                      ) : (
                        <p className="mt-2 text-[12px] italic text-[var(--on-surface-variant)]">No records found.</p>
                      )}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
