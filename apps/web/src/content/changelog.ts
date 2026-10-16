/** Product changelog. Newest first. Shown at /changelog and in the app's "What's new". */
export type ChangelogEntry = { id: string; date: string; title: string; items: string[] };

export const CHANGELOG: ChangelogEntry[] = [
  {
    id: "2026-10-billing",
    date: "2026-10-20",
    title: "Plans, billing and a public site",
    items: [
      "Choose a plan and pay securely with Stripe, with monthly or yearly billing",
      "Manage your card, invoices and cancellation from the billing portal",
      "New public pages: features, pricing, help center, blog and legal",
    ],
  },
  {
    id: "2026-10-api",
    date: "2026-10-19",
    title: "API keys and webhooks",
    items: [
      "Create scoped API keys and use the new REST API",
      "Get signed webhooks for new leads, sends, bounces, replies and finished sequences",
      "See every delivery and replay failed ones",
    ],
  },
  {
    id: "2026-10-privacy",
    date: "2026-10-18",
    title: "Privacy tools",
    items: [
      "Record a lawful basis and legitimate-interest note on every lead",
      "Export or erase a person's data from Settings → Privacy",
      "Set retention rules for uncontacted leads and old replies",
    ],
  },
  {
    id: "2026-10-roles",
    date: "2026-10-17",
    title: "Roles, audit log and single sign-on",
    items: [
      "Custom roles on Enterprise, with exactly the permissions people need",
      "Searchable, exportable audit log",
      "Sign in with Google, Microsoft or your company's identity provider",
      "Two-factor authentication, active sessions and account deletion",
    ],
  },
];
