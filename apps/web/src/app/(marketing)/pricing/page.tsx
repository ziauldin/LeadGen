import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Check, Coins, KeyRound, Minus, Zap } from "lucide-react";
import { COMMON_FAQ, Faq, type FaqItem } from "@/components/marketing/faq";
import { PricingPlans } from "@/components/marketing/pricing-plans";
import { PageIntro, SectionHeading } from "@/components/marketing/site-chrome";
import { compactNumber, fetchCreditPacks, fetchPlans, formatPrice } from "@/lib/marketing";

export const metadata: Metadata = {
  title: "Pricing · LeadsGen",
  description: "Simple plans that grow with your team. Start free, bring your own keys or use credits, and upgrade when it works for you.",
  alternates: { canonical: "/pricing" },
};

export const revalidate = 600;

const LIMIT_ROWS: [string, string][] = [
  ["monthly_sends", "Emails a month"],
  ["monthly_leads", "New leads a month"],
  ["seats", "Team seats"],
  ["max_mailboxes", "Connected mailboxes"],
  ["max_campaigns", "Campaigns"],
  ["monthly_verifications", "Verifications included a month"],
  ["monthly_llm_tokens", "AI tokens included a month"],
];
const FEATURE_ROWS: [string, string][] = [
  ["api_access", "API and webhooks"],
  ["integrations", "HubSpot and Pipedrive sync"],
  ["sso", "Single sign-on (OIDC)"],
  ["saml", "SAML 2.0"],
  ["custom_roles", "Custom roles"],
  ["audit_log_retention_days", "Audit log history"],
];

const PRICING_FAQ: FaqItem[] = [
  COMMON_FAQ[0],
  COMMON_FAQ[1],
  COMMON_FAQ[2],
  {
    question: "What happens if I go over my plan?",
    answer:
      "Sending, leads and seats stop at the plan limit so you're never billed by surprise. For services we provide, like verification and AI writing, credits take over once the included allowance is used.",
  },
  {
    question: "Can I change plans later?",
    answer: "Yes. Upgrade or downgrade from Settings at any time. Changes are prorated by Stripe, and you keep your data on every plan.",
  },
  COMMON_FAQ[5],
];

function cell(value: boolean | number | undefined, key: string) {
  if (typeof value === "boolean" || value === undefined) {
    return value ? (
      <Check className="mx-auto size-5 text-[var(--mk-green)]" aria-label="Included" />
    ) : (
      <Minus className="mx-auto size-5 text-[var(--mk-muted)]" aria-label="Not included" />
    );
  }
  if (key === "audit_log_retention_days") return `${value} days`;
  if (key === "monthly_llm_tokens") return compactNumber(value);
  return value.toLocaleString("en");
}

export default async function PricingPage() {
  const [plans, credits] = await Promise.all([fetchPlans(), fetchCreditPacks()]);
  return (
    <>
      <div className="relative overflow-hidden">
        <div className="mk-grid-bg" aria-hidden />
        <div className="mk-aurora opacity-80" aria-hidden />
        <div className="relative mx-auto max-w-6xl px-4 pb-24 pt-16 sm:pt-24">
          <PageIntro eyebrow="Pricing" title="Pricing that pays for itself">
            Start free. Pay for the product, not the plumbing: bring your own keys at no extra cost, or use credits and skip
            the setup.
          </PageIntro>
          <div className="mt-12">
            <PricingPlans plans={plans} />
          </div>
          <p className="mt-6 text-center text-[13px] text-[var(--mk-muted)]">
            Prices in {plans[0]?.currency ?? "USD"}, excluding taxes where applicable.
          </p>
        </div>
      </div>

      {/* ── BYOK vs credits ─────────────────────────────────────── */}
      <section className="mx-auto max-w-6xl px-4 py-20 sm:py-24">
        <SectionHeading eyebrow="How usage works" title="Bring your own keys, or use ours">
          Your plan covers the product. Data and AI services are paid for whichever way suits you.
        </SectionHeading>
        <div className="mt-14 grid gap-5 lg:grid-cols-3">
          <article className="mk-card p-7">
            <KeyRound className="size-7 text-[#a9e9ff]" aria-hidden />
            <h3 className="mt-5 text-[19px] font-semibold text-white">Your own keys: no markup</h3>
            <p className="mt-2 text-[15px] leading-7 text-[var(--mk-muted)]">
              Connect Gmail or Microsoft 365, your AI model, ZeroBounce or NeverBounce and Hunter. You pay them directly, and that
              usage never counts against your plan.
            </p>
          </article>
          <article className="mk-card p-7">
            <Zap className="size-7 text-[#ffc2e3]" aria-hidden />
            <h3 className="mt-5 text-[19px] font-semibold text-white">Our keys: included allowance</h3>
            <p className="mt-2 text-[15px] leading-7 text-[var(--mk-muted)]">
              Skip the setup. Every plan includes monthly verifications and AI tokens on LeadsGen&apos;s own accounts, shown on each
              plan above.
            </p>
          </article>
          <article className="mk-card p-7">
            <Coins className="size-7 text-[#ffd98a]" aria-hidden />
            <h3 className="mt-5 text-[19px] font-semibold text-white">Credits: top up any time</h3>
            <p className="mt-2 text-[15px] leading-7 text-[var(--mk-muted)]">
              Used the allowance? Credits take over: one credit is{" "}
              {credits.units.monthly_verifications === 1 ? "one verification or one email lookup" : "a verification"}, or{" "}
              {(credits.units.monthly_llm_tokens ?? 1000).toLocaleString("en")} AI tokens. Purchased credits never expire.
            </p>
          </article>
        </div>
        <ul className="mt-8 grid gap-4 sm:grid-cols-3" aria-label="Credit packs">
          {credits.packs.map((pack, index) => (
            <li key={pack.credits} className={`flex items-center justify-between rounded-2xl border p-5 ${index === 1 ? "border-[#a597ff]/50 bg-[#a597ff]/10" : "border-white/10 bg-white/[0.03]"}`}>
              <div>
                <p className="text-[18px] font-semibold text-white">{pack.credits.toLocaleString("en")} credits</p>
                {pack.amount ? (
                  <p className="text-[13px] text-[var(--mk-muted)]">
                    {formatPrice(pack.amount / (pack.credits / 1000), pack.currency)} per 1,000
                  </p>
                ) : null}
              </div>
              <p className="text-[24px] font-bold text-white">{formatPrice(pack.amount, pack.currency) ?? "—"}</p>
            </li>
          ))}
        </ul>
      </section>

      {/* ── Comparison ─────────────────────────────────────────── */}
      <section aria-labelledby="compare-heading" className="mx-auto max-w-6xl px-4 py-10 sm:py-16">
        <h2 id="compare-heading" className="text-center text-[30px] font-bold tracking-tight text-white sm:text-[38px]">
          Compare plans
        </h2>
        <div className="mk-card mt-10 overflow-x-auto" tabIndex={0}>
          <table className="w-full min-w-[720px] text-[15px]">
            <caption className="sr-only">Plan comparison</caption>
            <thead>
              <tr className="border-b border-white/10">
                <th scope="col" className="px-6 py-4 text-left text-[13px] font-semibold uppercase tracking-wider text-[var(--mk-muted)]">
                  Plan
                </th>
                {plans.map((plan) => (
                  <th key={plan.name} scope="col" className={`px-6 py-4 text-center text-[15px] font-semibold capitalize ${plan.name === "pro" ? "text-[#cfc7ff]" : "text-white"}`}>
                    {plan.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {LIMIT_ROWS.map(([key, label]) => (
                <tr key={key} className="border-b border-white/[0.06]">
                  <th scope="row" className="px-6 py-3.5 text-left font-normal text-white/90">{label}</th>
                  {plans.map((plan) => (
                    <td key={plan.name} className="px-6 py-3.5 text-center tabular-nums text-white">{cell(plan.limits[key], key)}</td>
                  ))}
                </tr>
              ))}
              {FEATURE_ROWS.map(([key, label]) => (
                <tr key={key} className="border-b border-white/[0.06] last:border-0">
                  <th scope="row" className="px-6 py-3.5 text-left font-normal text-white/90">{label}</th>
                  {plans.map((plan) => (
                    <td key={plan.name} className="px-6 py-3.5 text-center text-white">{cell(plan.features[key], key)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-4 text-center text-[13px] text-[var(--mk-muted)]">
          Every plan includes the approval queue, compliance checks, suppression lists, data requests and the unified inbox.
        </p>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-20 sm:py-24">
        <SectionHeading eyebrow="FAQ" title="Pricing questions" />
        <div className="mt-12">
          <Faq items={PRICING_FAQ} />
        </div>
        <div className="mt-14 text-center">
          <Link href="/register" className="mk-cta inline-flex items-center gap-2 rounded-xl px-7 py-3.5 text-[16px] font-semibold">
            Start free, no card needed <ArrowRight className="size-4" aria-hidden />
          </Link>
        </div>
      </section>
    </>
  );
}
