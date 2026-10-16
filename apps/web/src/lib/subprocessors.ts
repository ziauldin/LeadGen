/** Third parties that may process personal data for LeadsGen. Keep in sync with docs/SUBPROCESSORS.md. */
export type Subprocessor = { name: string; purpose: string; data: string; location: string; when: string };

export const PLATFORM_SUBPROCESSORS: Subprocessor[] = [
  {
    name: "Railway",
    purpose: "Application hosting, database and queues",
    data: "All workspace data",
    location: "United States / European Union",
    when: "Always",
  },
  {
    name: "Amazon Web Services (S3) or Cloudflare (R2)",
    purpose: "File storage for exports and attachments",
    data: "Export files",
    location: "Region chosen by the operator",
    when: "When object storage is configured",
  },
  {
    name: "Sentry",
    purpose: "Error monitoring",
    data: "Error details, user and workspace IDs",
    location: "United States",
    when: "When error monitoring is on",
  },
  {
    name: "Cloudflare (Turnstile)",
    purpose: "Bot protection on sign-up and sign-in",
    data: "IP address, browser signals",
    location: "Global",
    when: "When CAPTCHA is on",
  },
  {
    name: "Platform email provider (SMTP)",
    purpose: "Account emails: verification, password reset, invitations",
    data: "Account holder name and email",
    location: "Depends on the provider",
    when: "Always",
  },
];

export const WORKSPACE_SUBPROCESSORS: Subprocessor[] = [
  {
    name: "Resend, SendGrid, Mailgun or your SMTP server",
    purpose: "Sending outreach emails",
    data: "Recipient email, name, email content",
    location: "Depends on the provider",
    when: "The sending provider you connect",
  },
  {
    name: "OpenAI, Google (Gemini) or Groq",
    purpose: "Optional AI drafting and reply classification",
    data: "Lead profile fields, reply text",
    location: "United States",
    when: "Only if you turn AI on and add a key",
  },
  {
    name: "Hunter",
    purpose: "Finding and checking business email addresses",
    data: "Name, company domain",
    location: "European Union",
    when: "Only if you connect it",
  },
  {
    name: "Google Programmable Search, Bing or SerpAPI",
    purpose: "Finding public business listings",
    data: "Search queries (no personal data sent)",
    location: "United States",
    when: "Only if you connect it",
  },
];
