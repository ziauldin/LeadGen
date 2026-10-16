/** Public site configuration. Operators set the NEXT_PUBLIC_* values for their deployment. */

export const SITE = {
  name: "LeadsGen",
  tagline: "Compliant B2B prospecting and outreach",
  description:
    "Find the right businesses, write personal emails with a human in the loop, and send from your own mailboxes, with consent, suppression and audit built in.",
  url: (process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000").replace(/\/$/, ""),
  legalEntity: process.env.NEXT_PUBLIC_LEGAL_ENTITY ?? "LeadsGen",
  legalAddress: process.env.NEXT_PUBLIC_LEGAL_ADDRESS ?? "Registered address available on request",
  contactEmail: process.env.NEXT_PUBLIC_CONTACT_EMAIL ?? "hello@example.com",
  privacyEmail: process.env.NEXT_PUBLIC_PRIVACY_EMAIL ?? "privacy@example.com",
  statusUrl: process.env.NEXT_PUBLIC_STATUS_URL ?? "",
};

export const MARKETING_NAV = [
  { href: "/features", label: "Features" },
  { href: "/use-cases", label: "Use cases" },
  { href: "/pricing", label: "Pricing" },
  { href: "/help", label: "Help" },
];

export const FOOTER_LINKS: { heading: string; links: { href: string; label: string }[] }[] = [
  {
    heading: "Product",
    links: [
      { href: "/features", label: "Features" },
      { href: "/pricing", label: "Pricing" },
      { href: "/use-cases", label: "Use cases" },
      { href: "/docs/api", label: "API" },
      { href: "/changelog", label: "Changelog" },
    ],
  },
  {
    heading: "Resources",
    links: [
      { href: "/help", label: "Help center" },
      { href: "/blog", label: "Blog" },
    ],
  },
  {
    heading: "Company",
    links: [
      { href: "/about", label: "About" },
      { href: "/contact", label: "Contact" },
    ],
  },
  {
    heading: "Legal",
    links: [
      { href: "/legal/terms", label: "Terms of Service" },
      { href: "/legal/privacy", label: "Privacy Policy" },
      { href: "/legal/dpa", label: "Data Processing Agreement" },
      { href: "/legal/acceptable-use", label: "Acceptable Use" },
      { href: "/legal/cookies", label: "Cookie Policy" },
      { href: "/subprocessors", label: "Subprocessors" },
    ],
  },
];

export type PublicPlan = {
  name: string;
  limits: Record<string, number>;
  features: Record<string, boolean | number>;
  prices: { month?: number | null; year?: number | null } | null;
  currency: string;
};

/** Used when the API can't be reached (e.g. during a build). Mirrors services/billing/plans.py. */
export const FALLBACK_PLANS: PublicPlan[] = [
  {
    name: "free",
    limits: { monthly_sends: 500, monthly_leads: 1000, seats: 2, max_campaigns: 3, max_mailboxes: 1, monthly_verifications: 100, monthly_llm_tokens: 200000 },
    features: { sso: false, api_access: false, integrations: false, audit_log_retention_days: 30 },
    prices: { month: 0, year: 0 },
    currency: "USD",
  },
  {
    name: "starter",
    limits: { monthly_sends: 5000, monthly_leads: 10000, seats: 5, max_campaigns: 20, max_mailboxes: 5, monthly_verifications: 2000, monthly_llm_tokens: 2000000 },
    features: { sso: false, api_access: true, integrations: false, audit_log_retention_days: 90 },
    prices: { month: 39, year: 390 },
    currency: "USD",
  },
  {
    name: "pro",
    limits: { monthly_sends: 50000, monthly_leads: 100000, seats: 20, max_campaigns: 100, max_mailboxes: 25, monthly_verifications: 20000, monthly_llm_tokens: 10000000 },
    features: { sso: true, api_access: true, integrations: true, audit_log_retention_days: 365 },
    prices: { month: 99, year: 990 },
    currency: "USD",
  },
  {
    name: "enterprise",
    limits: { monthly_sends: 250000, monthly_leads: 1000000, seats: 200, max_campaigns: 1000, max_mailboxes: 200, monthly_verifications: 100000, monthly_llm_tokens: 50000000 },
    features: { sso: true, saml: true, custom_roles: true, api_access: true, integrations: true, audit_log_retention_days: 730 },
    prices: null,
    currency: "USD",
  },
];

export type CreditPacks = {
  packs: { credits: number; amount: number | null; currency: string }[];
  units: Record<string, number>;
};

export const FALLBACK_CREDITS: CreditPacks = {
  packs: [
    { credits: 1000, amount: 10, currency: "USD" },
    { credits: 5000, amount: 40, currency: "USD" },
    { credits: 20000, amount: 120, currency: "USD" },
  ],
  units: { monthly_verifications: 1, daily_hunter_lookups: 1, monthly_llm_tokens: 1000 },
};

const API = (process.env.API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

/** Server-side: the public plan list, refreshed every 10 minutes, with a built-in fallback. */
export async function fetchPlans(): Promise<PublicPlan[]> {
  try {
    const response = await fetch(`${API}/billing/plans`, { next: { revalidate: 600 } });
    if (!response.ok) return FALLBACK_PLANS;
    const plans = (await response.json()) as PublicPlan[];
    return plans.length ? plans : FALLBACK_PLANS;
  } catch {
    return FALLBACK_PLANS;
  }
}

/** Server-side: credit packs for the pricing page, with a built-in fallback. */
export async function fetchCreditPacks(): Promise<CreditPacks> {
  try {
    const response = await fetch(`${API}/billing/credit-packs`, { next: { revalidate: 600 } });
    if (!response.ok) return FALLBACK_CREDITS;
    const data = (await response.json()) as CreditPacks;
    return data.packs?.length ? data : FALLBACK_CREDITS;
  } catch {
    return FALLBACK_CREDITS;
  }
}

/** 1500000 → "1.5M", 200000 → "200k" (for token counts). */
export function compactNumber(value: number): string {
  if (value >= 1_000_000) return `${Number((value / 1_000_000).toFixed(1))}M`;
  if (value >= 1_000) return `${Math.round(value / 1_000)}k`;
  return value.toLocaleString("en");
}

export function formatPrice(amount: number | null | undefined, currency: string): string | null {
  if (amount === null || amount === undefined) return null;
  if (amount === 0) return "Free";
  // Whole prices without decimals ($39); others keep cents ($32.50 a month billed yearly).
  const digits = Number.isInteger(amount) ? 0 : 2;
  return new Intl.NumberFormat("en", { style: "currency", currency, minimumFractionDigits: digits, maximumFractionDigits: digits }).format(amount);
}
