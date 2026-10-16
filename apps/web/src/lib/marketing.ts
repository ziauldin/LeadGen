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
    limits: { monthly_sends: 500, monthly_leads: 1000, seats: 2, max_campaigns: 3 },
    features: { sso: false, api_access: false, audit_log_retention_days: 30 },
    prices: { month: 0, year: 0 },
    currency: "USD",
  },
  {
    name: "starter",
    limits: { monthly_sends: 5000, monthly_leads: 10000, seats: 5, max_campaigns: 20 },
    features: { sso: false, api_access: true, audit_log_retention_days: 90 },
    prices: null,
    currency: "USD",
  },
  {
    name: "pro",
    limits: { monthly_sends: 50000, monthly_leads: 100000, seats: 20, max_campaigns: 100 },
    features: { sso: true, api_access: true, audit_log_retention_days: 365 },
    prices: null,
    currency: "USD",
  },
  {
    name: "enterprise",
    limits: { monthly_sends: 250000, monthly_leads: 1000000, seats: 200, max_campaigns: 1000 },
    features: { sso: true, saml: true, custom_roles: true, api_access: true, audit_log_retention_days: 730 },
    prices: null,
    currency: "USD",
  },
];

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

export function formatPrice(amount: number | null | undefined, currency: string): string | null {
  if (amount === null || amount === undefined) return null;
  if (amount === 0) return "Free";
  return new Intl.NumberFormat("en", { style: "currency", currency, maximumFractionDigits: 0 }).format(amount);
}
