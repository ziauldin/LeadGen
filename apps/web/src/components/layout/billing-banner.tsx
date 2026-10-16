"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Clock } from "lucide-react";
import { daysUntil } from "@/components/settings/billing-panel";
import { useAuth } from "@/hooks/use-auth";
import { billingApi } from "@/lib/api/endpoints";

/** Overdue payments everywhere; trials only in their last three days. */
export function BillingBanner() {
  const { user } = useAuth();
  const billing = useQuery({
    queryKey: ["billing"],
    queryFn: billingApi.summary,
    enabled: Boolean(user),
    staleTime: 5 * 60_000,
  });
  const data = billing.data;
  if (!data?.billing_enabled) return null;

  if (data.subscription?.status === "past_due") {
    return (
      <div role="alert" className="mb-4 flex items-start gap-2 rounded-lg border border-[var(--error)] bg-[var(--error-container)] px-4 py-3 text-[13px] text-[var(--on-error-container)]">
        <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
        <p>
          {data.sending_paused_for_payment ? "Sending is paused: your last payment failed." : "Your last payment failed."}{" "}
          <Link href="/settings/usage" className="font-semibold underline">
            Update your payment method
          </Link>
        </p>
      </div>
    );
  }
  const days = daysUntil(data.trial_ends_at);
  if (days !== null && days <= 3) {
    return (
      <div role="status" className="mb-4 flex items-start gap-2 rounded-lg border border-[var(--outline-variant)] bg-[var(--surface-container-low)] px-4 py-3 text-[13px]">
        <Clock className="mt-0.5 size-4 shrink-0" aria-hidden />
        <p>
          Your free trial ends {days === 0 ? "today" : `in ${days} ${days === 1 ? "day" : "days"}`}.{" "}
          <Link href="/settings/usage" className="font-semibold text-[var(--primary)] underline">
            Choose a plan
          </Link>{" "}
          to keep your limits.
        </p>
      </div>
    );
  }
  return null;
}
