"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlertTriangle, Check, CreditCard, ExternalLink, Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/components/settings/settings-card";
import { useWorkspace } from "@/hooks/use-workspace";
import { billingApi } from "@/lib/api/endpoints";
import type { BillingSummary } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const PLAN_ORDER = ["free", "starter", "pro", "enterprise"];
const HIGHLIGHTS: [string, string][] = [
  ["monthly_sends", "emails a month"],
  ["monthly_leads", "leads a month"],
  ["seats", "team seats"],
  ["max_campaigns", "campaigns"],
];
const STATUS_TEXT: Record<string, string> = {
  active: "Active",
  trialing: "Trial",
  past_due: "Payment overdue",
  canceled: "Cancelled",
  unpaid: "Unpaid",
  incomplete: "Waiting for payment",
};

export function daysUntil(value: string | null | undefined): number | null {
  if (!value) return null;
  return Math.max(0, Math.ceil((new Date(value).getTime() - Date.now()) / 86_400_000));
}

function PlanStatus({ data }: { data: BillingSummary }) {
  const sub = data.subscription;
  const trialDays = daysUntil(data.trial_ends_at);
  return (
    <div>
      <p className="text-[12px] uppercase tracking-wide text-[var(--on-surface-variant)]">Current plan</p>
      <p className="text-[22px] font-bold capitalize text-[var(--on-surface)]">{data.plan}</p>
      <p className="text-[13px] text-[var(--on-surface-variant)]">
        {trialDays !== null
          ? `Free trial: ${trialDays} ${trialDays === 1 ? "day" : "days"} left`
          : sub?.status
            ? [
                STATUS_TEXT[sub.status] ?? sub.status,
                sub.interval ? `billed ${sub.interval}ly` : null,
                sub.current_period_end
                  ? `${sub.cancel_at_period_end ? "ends" : "renews"} ${formatDate(sub.current_period_end)}`
                  : null,
              ]
                .filter(Boolean)
                .join(" · ")
            : null}
      </p>
    </div>
  );
}

export function BillingPanel({ data }: { data: BillingSummary }) {
  const { can } = useWorkspace();
  const canManage = can("billing.manage");
  const [interval, setInterval] = useState<"month" | "year">("month");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("checkout") === "success") toast.success("Thanks! Your plan updates as soon as payment is confirmed.");
    if (params.get("checkout") === "cancelled") toast("Checkout cancelled. Nothing was charged.");
  }, []);

  const checkout = useMutation({
    mutationFn: ({ plan }: { plan: string }) => billingApi.checkout(plan, interval),
    onSuccess: (result) => window.location.assign(result.url),
  });
  const portal = useMutation({
    mutationFn: billingApi.portal,
    onSuccess: (result) => window.location.assign(result.url),
  });
  const invoices = useQuery({
    queryKey: ["billing", "invoices"],
    queryFn: billingApi.invoices,
    enabled: data.billing_enabled && canManage && Boolean(data.subscription?.has_billing_account),
  });

  const offers = useMemo(() => {
    const byPlan = new Map<string, Set<string>>();
    for (const key of data.purchasable) {
      const [plan, cadence] = key.split(":");
      byPlan.set(plan, (byPlan.get(plan) ?? new Set()).add(cadence));
    }
    return [...byPlan.entries()].sort(([a], [b]) => PLAN_ORDER.indexOf(a) - PLAN_ORDER.indexOf(b));
  }, [data.purchasable]);
  const hasYearly = offers.some(([, cadences]) => cadences.has("year"));
  const sub = data.subscription;

  if (!data.billing_enabled) {
    return (
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <PlanStatus data={data} />
        <p className="flex max-w-md items-start gap-2 rounded-md bg-[var(--surface-container-low)] px-3 py-2 text-[12px] text-[var(--on-surface-variant)]">
          <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          Online upgrades aren&apos;t available here yet. If you need higher limits, contact support.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {sub?.status === "past_due" ? (
        <p role="alert" className="flex items-start gap-2 rounded-md bg-[var(--error-container)] px-3 py-2 text-[13px] text-[var(--on-error-container)]">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
          {data.sending_paused_for_payment
            ? "Sending is paused because a payment failed. Update your card to resume."
            : `Your last payment failed. Update your card by ${formatDate(sub.grace_ends_at)} to keep sending.`}
        </p>
      ) : null}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <PlanStatus data={data} />
        {canManage && sub?.has_billing_account ? (
          <Button variant="outline" disabled={portal.isPending} onClick={() => portal.mutate()}>
            <CreditCard aria-hidden /> Manage billing
          </Button>
        ) : null}
      </div>

      {canManage && offers.length ? (
        <div className="space-y-3">
          {hasYearly ? (
            <div role="radiogroup" aria-label="Billing period" className="inline-flex rounded-lg border border-[var(--outline-variant)] p-0.5">
              {(["month", "year"] as const).map((value) => (
                <button
                  key={value}
                  type="button"
                  role="radio"
                  aria-checked={interval === value}
                  onClick={() => setInterval(value)}
                  className={cn(
                    "rounded-md px-3 py-1 text-[13px] font-medium",
                    interval === value ? "bg-[var(--primary)] text-white" : "text-[var(--on-surface-variant)]",
                  )}
                >
                  {value === "month" ? "Monthly" : "Yearly"}
                </button>
              ))}
            </div>
          ) : null}
          <ul className="grid gap-3 md:grid-cols-3">
            {offers.map(([plan, cadences]) => {
              const current = data.plan === plan && sub?.status && sub.status !== "canceled";
              const available = cadences.has(interval);
              const limits = data.plan_limits[plan] ?? {};
              return (
                <li key={plan} className={cn("flex flex-col rounded-lg border p-4", current ? "border-[var(--primary)]" : "border-[var(--outline-variant)]")}>
                  <p className="text-[16px] font-semibold capitalize">{plan}</p>
                  <ul className="mt-2 flex-1 space-y-1 text-[13px] text-[var(--on-surface-variant)]">
                    {HIGHLIGHTS.map(([key, label]) =>
                      limits[key] != null ? (
                        <li key={key} className="flex items-center gap-1.5">
                          <Check className="size-3.5 text-[var(--primary)]" aria-hidden />
                          {limits[key].toLocaleString()} {label}
                        </li>
                      ) : null,
                    )}
                  </ul>
                  <Button
                    className="mt-3"
                    variant={current ? "outline" : "default"}
                    disabled={Boolean(current) || !available || checkout.isPending}
                    onClick={() => checkout.mutate({ plan })}
                  >
                    {current ? "Current plan" : available ? `Choose ${plan}` : `Not available ${interval}ly`}
                  </Button>
                </li>
              );
            })}
          </ul>
          <p className="text-[12px] text-[var(--on-surface-variant)]">
            Payments are handled by Stripe. Change or cancel any time from Manage billing.
          </p>
        </div>
      ) : !canManage ? (
        <p className="text-[12px] text-[var(--on-surface-variant)]">Only workspace owners can change the plan.</p>
      ) : null}

      {invoices.data?.length ? (
        <div>
          <p className="mb-2 text-[13px] font-medium">Invoices</p>
          <ul className="divide-y divide-[var(--outline-variant)] text-[13px]">
            {invoices.data.map((invoice) => (
              <li key={invoice.id ?? invoice.number} className="flex items-center justify-between py-2">
                <span>
                  {invoice.number ?? invoice.id} · {formatDate(invoice.created)} ·{" "}
                  {(invoice.amount_paid / 100).toLocaleString(undefined, { style: "currency", currency: invoice.currency.toUpperCase() })}{" "}
                  · <span className="capitalize">{invoice.status}</span>
                </span>
                {invoice.hosted_invoice_url ? (
                  <a className="inline-flex items-center gap-1 text-[var(--primary)] hover:underline" href={invoice.hosted_invoice_url} target="_blank" rel="noreferrer">
                    View <ExternalLink className="size-3.5" aria-hidden />
                  </a>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
