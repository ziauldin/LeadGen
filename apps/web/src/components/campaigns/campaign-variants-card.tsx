"use client";

import { useQuery } from "@tanstack/react-query";
import { Trophy } from "lucide-react";
import { formatRate } from "@/components/campaigns/format";
import { analyticsApi } from "@/lib/api/endpoints";

/** A/B results per step. Only shown once a step with more than one version has sent emails. */
export function CampaignVariantsCard({ campaignId }: { campaignId: number }) {
  const results = useQuery({ queryKey: ["campaign-variants", campaignId], queryFn: () => analyticsApi.variants(campaignId) });
  const tested = (results.data ?? []).filter((step) => step.variants.length > 1);
  if (!tested.length) return null;

  return (
    <section aria-labelledby="variants-title" className="mt-6 rounded-lg border border-[var(--outline-variant)] bg-white p-4 shadow-sm">
      <h3 id="variants-title" className="text-[14px] font-semibold text-[var(--on-surface)]">
        A/B test results
      </h3>
      <p className="mb-3 text-[12px] text-[var(--on-surface-variant)]">
        A winner is suggested once every version has at least {tested[0].min_sends} sends and the difference in reply rate is
        statistically significant (p &lt; 0.05).
      </p>
      <div className="space-y-4">
        {tested.map((step) => (
          <div key={step.step_number}>
            <h4 className="mb-1 flex flex-wrap items-center gap-2 text-[13px] font-semibold text-[var(--on-surface)]">
              Step {step.step_number}
              {step.winner ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-[var(--secondary-container,#dcfce7)] px-2 py-0.5 text-[12px] font-medium text-[var(--on-secondary-container,#14532d)]">
                  <Trophy className="size-3.5" aria-hidden />
                  Version {step.winner.variant} is winning (p = {step.winner.p_value})
                </span>
              ) : (
                <span className="text-[12px] font-normal text-[var(--on-surface-variant)]">No clear winner yet</span>
              )}
            </h4>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-[13px]">
                <caption className="sr-only">Results for each version of step {step.step_number}</caption>
                <thead className="text-[12px] text-[var(--on-surface-variant)]">
                  <tr>
                    <th scope="col" className="py-1.5 pr-3 font-medium">Version</th>
                    <th scope="col" className="py-1.5 pr-3 text-right font-medium">Sent</th>
                    <th scope="col" className="py-1.5 pr-3 text-right font-medium">Reply rate</th>
                    <th scope="col" className="py-1.5 pr-3 text-right font-medium">Interested rate</th>
                    <th scope="col" className="py-1.5 text-right font-medium">Bounce rate</th>
                  </tr>
                </thead>
                <tbody>
                  {step.variants.map((variant) => (
                    <tr key={variant.variant} className="border-t border-[var(--outline-variant)]">
                      <th scope="row" className="py-1.5 pr-3 font-medium">{variant.variant}</th>
                      <td className="py-1.5 pr-3 text-right tabular-nums">{variant.sent.toLocaleString()}</td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">{formatRate(variant.reply_rate)}</td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">{formatRate(variant.positive_rate)}</td>
                      <td className="py-1.5 text-right tabular-nums">{formatRate(variant.bounce_rate)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
