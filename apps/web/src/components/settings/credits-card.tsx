"use client";

import { useEffect } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Coins } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SettingsCard, formatDate } from "@/components/settings/settings-card";
import { useWorkspace } from "@/hooks/use-workspace";
import { billingApi } from "@/lib/api/endpoints";
import type { components } from "@/lib/api/schema";

type Credits = components["schemas"]["CreditsInfo"];

const METRIC_LABELS: Record<string, string> = {
  monthly_verifications: "email verification",
  daily_hunter_lookups: "email lookup",
  monthly_llm_tokens: "AI tokens",
};

function unitText(metric: string, units: number) {
  const label = METRIC_LABELS[metric] ?? metric.replace(/_/g, " ");
  return units === 1 ? `1 ${label}` : `${units.toLocaleString()} ${label}`;
}

/** Prepaid credits: the balance, what one buys, packs to buy and recent activity. */
export function CreditsCard({ credits, currency = "USD" }: { credits: Credits; currency?: string }) {
  const { can } = useWorkspace();
  const canManage = can("billing.manage");
  const history = useQuery({ queryKey: ["credit-history"], queryFn: billingApi.creditHistory });
  const buy = useMutation({
    mutationFn: (amount: number) => billingApi.buyCredits(amount),
    onSuccess: (result) => window.location.assign(result.url),
  });

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("credits") === "success") toast.success("Thanks! Your credits appear as soon as payment is confirmed.");
    if (params.get("credits") === "cancelled") toast("Purchase cancelled. Nothing was charged.");
  }, []);

  const money = (amount: number | null | undefined) =>
    amount == null ? null : new Intl.NumberFormat(undefined, { style: "currency", currency, maximumFractionDigits: 0 }).format(amount);

  return (
    <SettingsCard
      id="credits"
      title="Credits"
      description="Credits pay for services LeadsGen provides once your plan's allowance is used up. Usage on your own API keys never uses credits."
    >
      <div className="flex flex-wrap items-center gap-4">
        <span className="flex size-12 items-center justify-center rounded-xl bg-[var(--primary-fixed)] text-[var(--on-primary-fixed)]" aria-hidden>
          <Coins className="size-6" />
        </span>
        <div>
          <p className="text-[28px] font-bold leading-none tabular-nums">{credits.balance.toLocaleString()}</p>
          <p className="mt-1 text-[13px] text-[var(--on-surface-variant)]">credits available · purchased credits don&apos;t expire</p>
        </div>
      </div>
      <p className="mt-4 text-[13px] text-[var(--on-surface-variant)]">
        One credit buys{" "}
        {Object.entries(credits.units)
          .map(([metric, units]) => unitText(metric, units))
          .join(", ")}
        .
      </p>

      {credits.packs.length ? (
        <ul className="mt-5 grid gap-3 sm:grid-cols-3" aria-label="Credit packs">
          {credits.packs.map((pack) => (
            <li key={pack.credits} className="rounded-lg border border-[var(--outline-variant)] p-4">
              <p className="text-[18px] font-semibold tabular-nums">{pack.credits.toLocaleString()} credits</p>
              {money(pack.amount) ? <p className="text-[13px] text-[var(--on-surface-variant)]">{money(pack.amount)}</p> : null}
              {canManage ? (
                <Button
                  size="sm"
                  className="mt-3 w-full"
                  variant="outline"
                  disabled={!pack.purchasable || buy.isPending}
                  onClick={() => buy.mutate(pack.credits)}
                >
                  {pack.purchasable ? `Buy ${pack.credits.toLocaleString()}` : "Not available online"}
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
      {!canManage ? (
        <p className="mt-3 text-[12px] text-[var(--on-surface-variant)]">Only people who manage billing can buy credits.</p>
      ) : null}

      {history.data?.length ? (
        <div className="mt-6">
          <h3 className="text-[13px] font-semibold">Recent activity</h3>
          <ul className="mt-2 divide-y divide-[var(--outline-variant)] text-[13px]">
            {history.data.slice(0, 8).map((row) => (
              <li key={row.id} className="flex items-center justify-between gap-3 py-2">
                <span>
                  {row.kind === "usage"
                    ? `Used for ${METRIC_LABELS[row.metric ?? ""] ?? "platform services"}`
                    : row.kind === "purchase"
                      ? "Credit pack"
                      : row.note || "Added by support"}
                  <span className="ml-2 text-[var(--on-surface-variant)]">{formatDate(row.created_at)}</span>
                </span>
                <span className={`tabular-nums font-medium ${row.amount < 0 ? "text-[var(--on-surface-variant)]" : "text-[var(--secondary)]"}`}>
                  {row.amount > 0 ? "+" : ""}
                  {row.amount.toLocaleString()}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </SettingsCard>
  );
}
