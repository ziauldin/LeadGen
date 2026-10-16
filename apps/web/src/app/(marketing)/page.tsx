import type { Metadata } from "next";
import Link from "next/link";
import {
  CheckCircle2,
  FileSearch,
  Inbox,
  MailCheck,
  PenLine,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";
import { SITE } from "@/lib/marketing";

export const metadata: Metadata = {
  title: `${SITE.name}: ${SITE.tagline}`,
  description: SITE.description,
  alternates: { canonical: "/" },
};

const STEPS: { icon: LucideIcon; title: string; text: string }[] = [
  {
    icon: FileSearch,
    title: "Find the right businesses",
    text: "Search public listings for your niche, import a CSV, or add leads by API. Every lead keeps its source and the lawful basis for contacting them.",
  },
  {
    icon: PenLine,
    title: "Write emails people want to read",
    text: "Start from proven templates or let AI draft a first version from what you know about the lead. Nothing is sent until a person approves it.",
  },
  {
    icon: MailCheck,
    title: "Send safely from your own mailboxes",
    text: "Sending windows, daily caps, warm-up and per-domain limits protect your reputation. Bounces, complaints and unsubscribes stop sequences automatically.",
  },
  {
    icon: Inbox,
    title: "Handle replies in one place",
    text: "Replies are matched to the right lead and labelled: interested, not now, unsubscribe. Follow up from the app and keep the whole history together.",
  },
];

const TRUST = [
  "Suppression list checked before every send",
  "One-click unsubscribe and physical address in every email",
  "Data requests: export or erase a person in minutes",
  "Row-level tenant isolation and an audit log of every change",
  "Two-factor authentication and single sign-on",
  "Your data stays yours: full workspace export at any time",
];

export default function LandingPage() {
  return (
    <div className="space-y-24">
      <section className="mx-auto max-w-3xl text-center">
        <p className="text-[13px] font-semibold uppercase tracking-wide text-[var(--primary)]">{SITE.tagline}</p>
        <h1 className="mt-3 text-[36px] font-bold leading-tight tracking-tight sm:text-[52px]">
          Outbound that respects the people you email
        </h1>
        <p className="mt-5 text-[17px] leading-8 text-[var(--on-surface-variant)]">{SITE.description}</p>
        <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
          <Link href="/register" className="rounded-lg bg-[var(--primary)] px-5 py-3 text-[15px] font-semibold text-white hover:opacity-90">
            Start free, no card needed
          </Link>
          <Link href="/pricing" className="rounded-lg border border-[var(--outline-variant)] bg-white px-5 py-3 text-[15px] font-semibold hover:bg-[var(--surface-container-low)]">
            See pricing
          </Link>
        </div>
      </section>

      <section aria-labelledby="how-heading">
        <h2 id="how-heading" className="text-center text-[28px] font-bold">
          From list to conversation in four steps
        </h2>
        <ol className="mt-10 grid gap-6 sm:grid-cols-2">
          {STEPS.map((step, index) => (
            <li key={step.title} className="rounded-xl border border-[var(--outline-variant)] bg-white p-6">
              <step.icon className="size-6 text-[var(--primary)]" aria-hidden />
              <h3 className="mt-3 text-[17px] font-semibold">
                <span className="sr-only">Step {index + 1}: </span>
                {step.title}
              </h3>
              <p className="mt-2 text-[14px] leading-6 text-[var(--on-surface-variant)]">{step.text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="trust-heading" className="rounded-2xl bg-white p-8 shadow-sm ring-1 ring-[var(--outline-variant)] sm:p-12">
        <div className="grid gap-10 md:grid-cols-2">
          <div>
            <ShieldCheck className="size-8 text-[var(--primary)]" aria-hidden />
            <h2 id="trust-heading" className="mt-3 text-[28px] font-bold">
              Compliance is the default, not an add-on
            </h2>
            <p className="mt-3 text-[15px] leading-7 text-[var(--on-surface-variant)]">
              Cold outreach only works long term if recipients are treated fairly. LeadsGen builds the
              rules of GDPR, PECR and CAN-SPAM into every step, so doing the right thing is also the
              easy thing.
            </p>
            <Link href="/features" className="mt-5 inline-block text-[15px] font-semibold text-[var(--primary)] hover:underline">
              Explore every feature →
            </Link>
          </div>
          <ul className="space-y-3">
            {TRUST.map((item) => (
              <li key={item} className="flex items-start gap-2 text-[15px]">
                <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-[var(--primary)]" aria-hidden />
                {item}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="text-center">
        <h2 className="text-[28px] font-bold">Try it with your next campaign</h2>
        <p className="mx-auto mt-3 max-w-xl text-[15px] text-[var(--on-surface-variant)]">
          The free plan includes 500 emails a month and two seats. Upgrade when it works for you.
        </p>
        <Link href="/register" className="mt-6 inline-block rounded-lg bg-[var(--primary)] px-5 py-3 text-[15px] font-semibold text-white hover:opacity-90">
          Create your workspace
        </Link>
      </section>
    </div>
  );
}
