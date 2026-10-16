import type { Metadata } from "next";
import Link from "next/link";
import { PageIntro } from "@/components/marketing/site-chrome";

export const metadata: Metadata = {
  title: "Features · LeadsGen",
  description:
    "Lead discovery, enrichment, human-approved AI emails, safe sending, reply handling, team permissions, SSO, an API and full GDPR tooling.",
  alternates: { canonical: "/features" },
};

const GROUPS: { title: string; items: [string, string][] }[] = [
  {
    title: "Find and organise leads",
    items: [
      ["Niche search", "Search public business listings by industry and location with Google, Bing or SerpAPI."],
      ["CSV import", "Bring your own lists with source and consent notes preserved for every row."],
      ["Enrichment", "Fill in company websites, find business email addresses and flag role-based ones."],
      ["Scoring", "Rank leads by fit so the team works on the best ones first."],
    ],
  },
  {
    title: "Write and approve",
    items: [
      ["Templates", "Reusable steps with personalisation variables and an unsubscribe link built in."],
      ["AI drafts", "Optional AI writing from your product notes and tone guide, using your own provider key."],
      ["Approval queue", "Keyboard-first review with live compliance checks on every draft."],
      ["Sequences", "Multi-step campaigns that stop automatically when someone replies or opts out."],
    ],
  },
  {
    title: "Send and follow up",
    items: [
      ["Your own sending accounts", "Connect Resend, SendGrid, Mailgun or SMTP. Each workspace uses its own keys."],
      ["Deliverability guard rails", "Sending windows, daily and per-domain caps, warm-up and an SPF/DKIM/DMARC check."],
      ["Bounces and complaints", "Provider webhooks pause problem addresses and suppress them everywhere."],
      ["Replies", "Inbound replies are matched, labelled and linked to the lead and campaign."],
    ],
  },
  {
    title: "Teams and security",
    items: [
      ["Roles and permissions", "Owner, admin and member roles, plus custom roles on Enterprise."],
      ["Single sign-on", "Google and Microsoft sign-in, OIDC on Pro and SAML 2.0 on Enterprise."],
      ["Two-factor authentication", "Authenticator apps with recovery codes, enforceable per workspace."],
      ["Audit log", "Every change to people, settings and data, searchable and exportable."],
    ],
  },
  {
    title: "Privacy by design",
    items: [
      ["Lawful basis per lead", "Record legitimate interest, consent or contract, with an optional assessment note."],
      ["Data requests", "Export everything about a person, or erase them and keep only a hashed block."],
      ["Retention rules", "Automatically delete uncontacted leads and old replies after a period you choose."],
      ["Workspace export", "Download all your data as CSV files whenever you like."],
    ],
  },
  {
    title: "Connect your stack",
    items: [
      ["REST API", "Scoped API keys, idempotent writes and an OpenAPI schema."],
      ["Webhooks", "Signed events for new leads, sends, bounces, replies and finished sequences."],
      ["Zapier and Make", "Use webhooks and the API to connect thousands of other tools."],
      ["Status and health", "Health checks, metrics and runbooks for teams who self-host."],
    ],
  },
];

export default function FeaturesPage() {
  return (
    <div className="space-y-16">
      <PageIntro eyebrow="Features" title="Everything you need for responsible outbound">
        One workspace for finding leads, writing and approving emails, sending safely and handling replies,
        with the controls a growing team and its customers expect.
      </PageIntro>
      {GROUPS.map((group) => (
        <section key={group.title} aria-labelledby={`group-${group.title}`}>
          <h2 id={`group-${group.title}`} className="text-[22px] font-bold">
            {group.title}
          </h2>
          <dl className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {group.items.map(([name, text]) => (
              <div key={name} className="rounded-xl border border-[var(--outline-variant)] bg-white p-5">
                <dt className="text-[15px] font-semibold">{name}</dt>
                <dd className="mt-1.5 text-[14px] leading-6 text-[var(--on-surface-variant)]">{text}</dd>
              </div>
            ))}
          </dl>
        </section>
      ))}
      <p className="text-center">
        <Link href="/register" className="rounded-lg bg-[var(--primary)] px-5 py-3 text-[15px] font-semibold text-white hover:opacity-90">
          Start free
        </Link>
      </p>
    </div>
  );
}
