import type { Metadata } from "next";
import Link from "next/link";
import { Check, Minus } from "lucide-react";
import { PageIntro } from "@/components/marketing/site-chrome";
import { fetchPlans, formatPrice, type PublicPlan } from "@/lib/marketing";

export const metadata: Metadata = {
  title: "Pricing · LeadsGen",
  description: "Simple plans that grow with your team. Start free, upgrade when it works for you.",
  alternates: { canonical: "/pricing" },
};

export const revalidate = 600;

const LIMIT_ROWS: [string, string][] = [
  ["monthly_sends", "Emails a month"],
  ["monthly_leads", "New leads a month"],
  ["seats", "Team seats"],
  ["max_campaigns", "Campaigns"],
  ["monthly_llm_tokens", "AI writing tokens a month"],
  ["daily_enrichments", "Company enrichments a day"],
];
const FEATURE_ROWS: [string, string][] = [
  ["api_access", "API and webhooks"],
  ["sso", "Single sign-on (OIDC)"],
  ["saml", "SAML 2.0"],
  ["custom_roles", "Custom roles"],
  ["audit_log_retention_days", "Audit log history"],
];
const BLURBS: Record<string, string> = {
  free: "Try the full workflow with a small team.",
  starter: "For founders and small teams running steady outreach.",
  pro: "For sales teams that need volume, SSO and the API.",
  enterprise: "For larger organisations with security and compliance needs.",
};

function Price({ plan }: { plan: PublicPlan }) {
  const monthly = formatPrice(plan.prices?.month, plan.currency);
  const yearly = plan.prices?.year ? formatPrice(plan.prices.year, plan.currency) : null;
  if (plan.name === "enterprise" && !monthly) return <p className="text-[28px] font-bold">Let&apos;s talk</p>;
  if (!monthly) return <p className="text-[28px] font-bold">Contact us</p>;
  return (
    <div>
      <p className="text-[32px] font-bold">
        {monthly}
        {monthly !== "Free" ? <span className="text-[14px] font-normal text-[var(--on-surface-variant)]"> / month</span> : null}
      </p>
      {yearly ? <p className="text-[13px] text-[var(--on-surface-variant)]">or {yearly} billed yearly</p> : null}
    </div>
  );
}

function cell(value: boolean | number | undefined, key: string) {
  if (typeof value === "boolean" || value === undefined) {
    return value ? (
      <Check className="mx-auto size-4 text-[var(--primary)]" aria-label="Included" />
    ) : (
      <Minus className="mx-auto size-4 text-[var(--on-surface-variant)]" aria-label="Not included" />
    );
  }
  if (key === "audit_log_retention_days") return `${value} days`;
  return value.toLocaleString("en");
}

export default async function PricingPage() {
  const plans = await fetchPlans();
  return (
    <div className="space-y-14">
      <PageIntro eyebrow="Pricing" title="Simple plans that grow with you">
        Every plan includes the approval queue, compliance checks, suppression lists and data requests.
      </PageIntro>

      <ul className="grid gap-5 md:grid-cols-2 lg:grid-cols-4">
        {plans.map((plan) => (
          <li
            key={plan.name}
            className={`flex flex-col rounded-xl border bg-white p-6 ${plan.name === "pro" ? "border-[var(--primary)] ring-1 ring-[var(--primary)]" : "border-[var(--outline-variant)]"}`}
          >
            <h2 className="text-[18px] font-semibold capitalize">{plan.name}</h2>
            <p className="mt-1 min-h-[40px] text-[13px] text-[var(--on-surface-variant)]">{BLURBS[plan.name] ?? ""}</p>
            <div className="mt-4">
              <Price plan={plan} />
            </div>
            <ul className="mt-5 flex-1 space-y-2 text-[14px]">
              {LIMIT_ROWS.slice(0, 4).map(([key, label]) => (
                <li key={key} className="flex items-center gap-2">
                  <Check className="size-4 text-[var(--primary)]" aria-hidden />
                  {plan.limits[key]?.toLocaleString("en")} {label.toLowerCase()}
                </li>
              ))}
            </ul>
            <Link
              href={plan.name === "enterprise" ? "/contact" : "/register"}
              className={`mt-6 rounded-lg px-4 py-2.5 text-center text-[14px] font-semibold ${plan.name === "pro" ? "bg-[var(--primary)] text-white hover:opacity-90" : "border border-[var(--outline-variant)] hover:bg-[var(--surface-container-low)]"}`}
            >
              {plan.name === "enterprise" ? "Contact sales" : plan.name === "free" ? "Start free" : `Start with ${plan.name}`}
            </Link>
          </li>
        ))}
      </ul>

      <section aria-labelledby="compare-heading">
        <h2 id="compare-heading" className="text-[22px] font-bold">Compare plans</h2>
        <div className="mt-5 overflow-x-auto rounded-xl border border-[var(--outline-variant)] bg-white" tabIndex={0}>
          <table className="w-full min-w-[640px] text-[14px]">
            <caption className="sr-only">Plan comparison</caption>
            <thead className="bg-[var(--surface-container-low)]">
              <tr>
                <th scope="col" className="px-4 py-3 text-left font-medium">Plan</th>
                {plans.map((plan) => (
                  <th key={plan.name} scope="col" className="px-4 py-3 text-center font-semibold capitalize">
                    {plan.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--outline-variant)]">
              {LIMIT_ROWS.map(([key, label]) => (
                <tr key={key}>
                  <th scope="row" className="px-4 py-3 text-left font-normal">{label}</th>
                  {plans.map((plan) => (
                    <td key={plan.name} className="px-4 py-3 text-center">{cell(plan.limits[key], key)}</td>
                  ))}
                </tr>
              ))}
              {FEATURE_ROWS.map(([key, label]) => (
                <tr key={key}>
                  <th scope="row" className="px-4 py-3 text-left font-normal">{label}</th>
                  {plans.map((plan) => (
                    <td key={plan.name} className="px-4 py-3 text-center">{cell(plan.features[key], key)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-[13px] text-[var(--on-surface-variant)]">
          Prices exclude taxes where applicable. You bring your own email provider and, optionally, your own AI key.
        </p>
      </section>
    </div>
  );
}
