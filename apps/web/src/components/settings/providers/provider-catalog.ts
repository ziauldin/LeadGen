/**
 * What each provider needs. Required fields mirror the API's `_required_fields`; webhook
 * verification fields mirror `WEBHOOK_SECRET_FIELDS` (services/provider_credentials/service.py).
 */
import { BadgeCheck, Bot, Inbox, Mail, Search, UserSearch, type LucideIcon } from "lucide-react";
import type { ProviderName, ProviderType } from "@/lib/api/types";

export type FieldKind = "text" | "secret" | "number" | "email" | "url" | "checkbox";

export type ProviderField = {
  name: string;
  label: string;
  kind: FieldKind;
  required?: boolean;
  placeholder?: string;
  hint?: string;
  defaultValue?: string | boolean;
  /** Half-width on larger screens. */
  half?: boolean;
};

export type ProviderDefinition = {
  name: ProviderName;
  label: string;
  description: string;
  fields: ProviderField[];
  /** Short note on what to do in the provider's own dashboard for webhooks. */
  webhookHelp?: string;
};

export type ProviderTypeDefinition = {
  type: ProviderType;
  label: string;
  description: string;
  icon: LucideIcon;
  providers: ProviderDefinition[];
};

const apiKey = (hint?: string): ProviderField => ({
  name: "api_key",
  label: "API key",
  kind: "secret",
  required: true,
  hint,
});
const fromEmail: ProviderField = {
  name: "from_email",
  label: "From email",
  kind: "email",
  required: true,
  placeholder: "jane@yourcompany.com",
  hint: "Must be on a domain you've verified with this provider.",
  half: true,
};
const fromName: ProviderField = {
  name: "from_name",
  label: "From name",
  kind: "text",
  placeholder: "Jane Doe",
  half: true,
};
const model = (placeholder: string): ProviderField => ({
  name: "model",
  label: "Model",
  kind: "text",
  placeholder,
  hint: `Optional. Leave empty to use ${placeholder}.`,
});

export const PROVIDER_TYPES: ProviderTypeDefinition[] = [
  {
    type: "email",
    label: "Sending",
    description:
      "The account your approved emails are sent from. Only one sending account is active at a time.",
    icon: Mail,
    providers: [
      {
        name: "mock",
        label: "Test mode",
        description: "Pretends to send, so you can try campaigns safely. Nothing leaves the app.",
        fields: [],
      },
      {
        name: "smtp",
        label: "SMTP",
        description: "Send through any mailbox or email server (Google Workspace, Microsoft 365, …).",
        fields: [
          { name: "host", label: "SMTP host", kind: "text", required: true, placeholder: "smtp.gmail.com", half: true },
          { name: "port", label: "Port", kind: "number", required: true, placeholder: "587", defaultValue: "587", half: true },
          { name: "username", label: "Username", kind: "text", required: true, placeholder: "jane@yourcompany.com", half: true },
          {
            name: "password",
            label: "Password",
            kind: "secret",
            required: true,
            hint: "For Google or Microsoft accounts, use an app password.",
            half: true,
          },
          fromEmail,
          fromName,
          { name: "use_tls", label: "Use TLS (STARTTLS)", kind: "checkbox", defaultValue: true },
        ],
      },
      {
        name: "resend",
        label: "Resend",
        description: "Developer-friendly email API with delivery and reply webhooks.",
        fields: [
          apiKey(),
          fromEmail,
          fromName,
          {
            name: "webhook_secret",
            label: "Webhook signing secret",
            kind: "secret",
            placeholder: "whsec_…",
            hint: "From the webhook you create in Resend. Lets us verify bounces and replies really came from Resend.",
          },
        ],
        webhookHelp:
          "In Resend, open Webhooks → Add endpoint, paste this URL and select the delivery, bounce and complaint events. Then copy the endpoint's signing secret into Configure → Webhook signing secret.",
      },
      {
        name: "sendgrid",
        label: "SendGrid",
        description: "Twilio SendGrid email API with event and inbound-parse webhooks.",
        fields: [
          apiKey(),
          fromEmail,
          fromName,
          {
            name: "event_public_key",
            label: "Event webhook verification key",
            kind: "secret",
            hint: "Turn on Signed Event Webhook in SendGrid and paste the verification key here.",
          },
        ],
        webhookHelp:
          "In SendGrid, go to Settings → Mail Settings → Event Webhook and paste the events URL, then enable signing and copy the verification key into Configure. For replies, add the inbound URL under Settings → Inbound Parse.",
      },
      {
        name: "mailgun",
        label: "Mailgun",
        description: "Mailgun email API with webhooks and inbound routes.",
        fields: [
          apiKey(),
          { name: "domain", label: "Sending domain", kind: "text", required: true, placeholder: "mg.yourcompany.com" },
          fromEmail,
          fromName,
          {
            name: "webhook_signing_key",
            label: "HTTP webhook signing key",
            kind: "secret",
            hint: "Found in Mailgun under Sending → Webhooks. Lets us verify events came from Mailgun.",
          },
        ],
        webhookHelp:
          "In Mailgun, open Sending → Webhooks and add the events URL for failures, complaints and unsubscribes. For replies, create a Route that forwards to the inbound URL. Copy your HTTP webhook signing key into Configure.",
      },
    ],
  },
  {
    type: "inbox",
    label: "Reply inbox",
    description:
      "Connect the mailbox replies arrive in. We check it regularly and file replies under the right lead.",
    icon: Inbox,
    providers: [
      {
        name: "imap",
        label: "IMAP mailbox",
        description: "Works with most mailboxes, including Google Workspace and Microsoft 365.",
        fields: [
          { name: "host", label: "IMAP host", kind: "text", required: true, placeholder: "imap.gmail.com", half: true },
          { name: "port", label: "Port", kind: "number", placeholder: "993", defaultValue: "993", half: true },
          { name: "username", label: "Username", kind: "text", required: true, placeholder: "jane@yourcompany.com", half: true },
          {
            name: "password",
            label: "Password",
            kind: "secret",
            required: true,
            hint: "Use an app password if your provider requires one.",
            half: true,
          },
          {
            name: "folder",
            label: "Folder",
            kind: "text",
            placeholder: "INBOX",
            defaultValue: "INBOX",
            hint: "The folder replies land in. Usually INBOX.",
          },
          { name: "use_ssl", label: "Use SSL", kind: "checkbox", defaultValue: true },
        ],
      },
    ],
  },
  {
    type: "search",
    label: "Search",
    description: "Used to find companies for your niches. Only official search APIs are supported.",
    icon: Search,
    providers: [
      {
        name: "mock",
        label: "Sample data",
        description: "Realistic sample results so you can explore without an API key.",
        fields: [],
      },
      {
        name: "google_cse",
        label: "Google Programmable Search",
        description: "Google's official Custom Search JSON API.",
        fields: [
          apiKey(),
          {
            name: "search_engine_id",
            label: "Search engine ID (cx)",
            kind: "secret",
            required: true,
          },
        ],
      },
      {
        name: "bing",
        label: "Bing Web Search",
        description: "Microsoft Bing Web Search API.",
        fields: [
          apiKey(),
          {
            name: "endpoint",
            label: "Endpoint",
            kind: "url",
            placeholder: "https://api.bing.microsoft.com/v7.0/search",
            hint: "Optional. Leave empty for the default endpoint.",
          },
        ],
      },
      {
        name: "serpapi",
        label: "SerpAPI",
        description: "Search results through SerpAPI.",
        fields: [apiKey()],
      },
    ],
  },
  {
    type: "email_discovery",
    label: "Email finding",
    description: "Finds published work email addresses for the people at your target companies.",
    icon: UserSearch,
    providers: [
      {
        name: "hunter",
        label: "Hunter.io",
        description: "Domain search for professional email addresses, with confidence scores.",
        fields: [apiKey()],
      },
    ],
  },
  {
    type: "email_verification",
    label: "Email verification",
    description:
      "Checks addresses before you email them. New contacts are verified automatically, invalid ones are never sent to, and each check uses your plan's verification credits.",
    icon: BadgeCheck,
    providers: [
      {
        name: "zerobounce",
        label: "ZeroBounce",
        description: "Validates mailboxes and flags catch-all, spam-trap and abuse addresses.",
        fields: [apiKey()],
      },
      {
        name: "neverbounce",
        label: "NeverBounce",
        description: "Real-time verification with catch-all and disposable detection.",
        fields: [apiKey()],
      },
      {
        name: "mock",
        label: "Test verifier",
        description: "Marks addresses starting with invalid/bounce as invalid and risky/catchall as risky.",
        fields: [],
      },
    ],
  },
  {
    type: "llm",
    label: "AI model",
    description:
      "Use your own AI key for drafts and reply labelling. Without one, AI features use the platform's model and count toward your plan's AI token quota.",
    icon: Bot,
    providers: [
      {
        name: "groq",
        label: "Groq",
        description: "Fast open models served by Groq.",
        fields: [apiKey(), model("llama-3.3-70b-versatile")],
      },
      {
        name: "openai",
        label: "OpenAI",
        description: "OpenAI's GPT models.",
        fields: [apiKey(), model("gpt-4.1-mini")],
      },
      {
        name: "gemini",
        label: "Google Gemini",
        description: "Google's Gemini models.",
        fields: [apiKey(), model("gemini-2.5-flash")],
      },
      {
        name: "mock",
        label: "Test model",
        description: "Returns canned text so you can try AI features without a key.",
        fields: [],
      },
    ],
  },
];

export const WEBHOOK_LABELS: Record<string, { label: string; hint: string }> = {
  events_and_inbound: {
    label: "Events and replies",
    hint: "Deliveries, bounces, complaints and inbound replies.",
  },
  events: { label: "Delivery events", hint: "Deliveries, bounces, complaints and unsubscribes." },
  inbound: { label: "Inbound replies", hint: "Replies to your emails." },
};
