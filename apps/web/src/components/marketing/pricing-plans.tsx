"use client";

import Link from "next/link";
import { useState } from "react";
import { Check, Sparkles } from "lucide-react";
import { compactNumber, formatPrice, type PublicPlan } from "@/lib/marketing";

const BLURBS: Record<string, string> = {
  free: "Try the full workflow with a small team.",
  starter: "For founders and small teams running steady outreach.",
  pro: "For sales teams that need volume, CRM sync and SSO.",
  enterprise: "For larger organisations with security and compliance needs.",
};

const HIGHLIGHTS: Record<string, string[]> = {
  free: ["Approval queue and compliance checks", "Unified inbox", "Templates and AI drafts"],
  starter: ["Everything in Free", "API and webhooks", "A/B tests and analytics", "Deals, tasks and notes"],
  pro: ["Everything in Starter", "HubSpot and Pipedrive sync", "Single sign-on (OIDC)", "1-year audit history"],
  enterprise: ["Everything in Pro", "SAML 2.0 and custom roles", "2-year audit history", "Volume pricing and a signed DPA"],
};

const n = (value: number | undefined) => (value ?? 0).toLocaleString("en");

function limitLines(plan: PublicPlan): string[] {
  const l = plan.limits;
  const tokens = l.monthly_llm_tokens ? `${compactNumber(l.monthly_llm_tokens)} AI tokens a month` : null;
  return [
    `${n(l.monthly_sends)} emails a month`,
    `${n(l.monthly_leads)} new leads a month`,
    `${n(l.seats)} team seats`,
    l.max_mailboxes ? `${n(l.max_mailboxes)} connected mailbox${l.max_mailboxes === 1 ? "" : "es"}` : null,
    l.monthly_verifications ? `${n(l.monthly_verifications)} verifications included` : null,
    tokens,
  ].filter(Boolean) as string[];
}

/** Plan cards with a monthly / yearly switch. */
export function PricingPlans({ plans }: { plans: PublicPlan[] }) {
  const [yearly, setYearly] = useState(true);
  const saving = (() => {
    const pro = plans.find((p) => p.prices?.month && p.prices?.year);
    if (!pro?.prices?.month || !pro.prices.year) return null;
    return Math.round((1 - pro.prices.year / (pro.prices.month * 12)) * 100);
  })();

  return (
    <div>
      <div className="flex justify-center">
        <div role="radiogroup" aria-label="Billing period" className="inline-flex items-center rounded-full border border-white/15 bg-white/5 p-1">
          {[
            { value: false, label: "Monthly" },
            { value: true, label: "Yearly" },
          ].map((option) => (
            <button
              key={option.label}
              type="button"
              role="radio"
              aria-checked={yearly === option.value}
              onClick={() => setYearly(option.value)}
              className={`rounded-full px-5 py-2 text-[14px] font-semibold transition ${yearly === option.value ? "mk-cta" : "text-[var(--mk-muted)] hover:text-white"}`}
            >
              {option.label}
            </button>
          ))}
          {saving ? (
            <span className="ml-2 mr-2 rounded-full bg-emerald-400/15 px-2.5 py-1 text-[12px] font-semibold text-emerald-300">
              Save {saving}%
            </span>
          ) : null}
        </div>
      </div>

      <ul className="mt-12 grid gap-5 md:grid-cols-2 xl:grid-cols-4">
        {plans.map((plan) => {
          const popular = plan.name === "pro";
          const month = plan.prices?.month;
          const year = plan.prices?.year;
          const shown = yearly && year ? year / 12 : month;
          const price = formatPrice(shown ?? null, plan.currency);
          return (
            <li
              key={plan.name}
              className={`relative flex flex-col rounded-2xl p-7 ${popular ? "mk-glow-frame bg-gradient-to-b from-[#2a2170]/80 to-[#120f36]/90 shadow-[0_30px_80px_-30px_rgba(123,63,228,0.7)]" : "mk-card"}`}
            >
              {popular ? (
                <span className="mk-cta absolute -top-3 left-1/2 inline-flex -translate-x-1/2 items-center gap-1 rounded-full px-3 py-1 text-[12px] font-semibold">
                  <Sparkles className="size-3.5" aria-hidden /> Most popular
                </span>
              ) : null}
              <h2 className="text-[20px] font-semibold capitalize text-white">{plan.name}</h2>
              <p className="mt-1 min-h-[44px] text-[14px] leading-6 text-[var(--mk-muted)]">{BLURBS[plan.name] ?? ""}</p>
              <div className="mt-5 min-h-[76px]">
                {price ? (
                  <>
                    <p className="text-[42px] font-bold leading-none tracking-tight text-white">
                      {price}
                      {price !== "Free" ? <span className="ml-1 text-[15px] font-medium text-[var(--mk-muted)]">/ month</span> : null}
                    </p>
                    <p className="mt-2 text-[13px] text-[var(--mk-muted)]">
                      {price === "Free"
                        ? "Free forever, no card needed"
                        : yearly && year
                          ? `${formatPrice(year, plan.currency)} billed yearly`
                          : "Billed monthly, cancel any time"}
                    </p>
                  </>
                ) : (
                  <>
                    <p className="text-[36px] font-bold leading-none tracking-tight text-white">Custom</p>
                    <p className="mt-2 text-[13px] text-[var(--mk-muted)]">Volume pricing and annual contracts</p>
                  </>
                )}
              </div>
              <Link
                href={plan.name === "enterprise" ? "/contact" : "/register"}
                className={`mt-6 rounded-xl px-4 py-3 text-center text-[15px] font-semibold ${popular ? "mk-cta" : "mk-ghost"}`}
              >
                {plan.name === "enterprise" ? "Talk to sales" : plan.name === "free" ? "Start free" : `Start with ${plan.name}`}
              </Link>
              <ul className="mt-7 space-y-2.5 text-[14px]">
                {limitLines(plan).map((line) => (
                  <li key={line} className="flex items-start gap-2.5 text-white/90">
                    <Check className="mt-0.5 size-4 shrink-0 text-[var(--mk-green)]" aria-hidden />
                    {line}
                  </li>
                ))}
              </ul>
              <div className="my-6 h-px bg-white/10" aria-hidden />
              <ul className="space-y-2.5 text-[14px]">
                {(HIGHLIGHTS[plan.name] ?? []).map((line) => (
                  <li key={line} className="flex items-start gap-2.5 text-[var(--mk-muted)]">
                    <Check className="mt-0.5 size-4 shrink-0 text-[#a597ff]" aria-hidden />
                    {line}
                  </li>
                ))}
              </ul>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
