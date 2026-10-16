import type { Metadata } from "next";
import Link from "next/link";
import { PageIntro } from "@/components/marketing/site-chrome";
import { SITE } from "@/lib/marketing";

export const metadata: Metadata = {
  title: "About · LeadsGen",
  description: "Why we built LeadsGen and the principles behind it.",
  alternates: { canonical: "/about" },
};

const PRINCIPLES: [string, string][] = [
  ["People first", "Every email reaches a real person. We make it easy to be relevant, honest and easy to say no to."],
  ["A human in the loop", "AI can draft, but people decide what gets sent. Approval is built into the workflow, not bolted on."],
  ["Your data, your rules", "You own your leads and can export or delete them at any time. We never sell or share them."],
  ["Secure by default", "Tenant isolation at the database level, encrypted credentials, two-factor and SSO for every team."],
];

export default function AboutPage() {
  return (
    <div className="space-y-12">
      <PageIntro eyebrow="About" title="Outbound, done properly">
        {SITE.name} started from a simple frustration: most prospecting tools make it easy to send a lot of
        email and hard to send the right email. We think the teams that win long term are the ones whose
        outreach people are glad to receive.
      </PageIntro>
      <dl className="mx-auto grid max-w-4xl gap-5 sm:grid-cols-2">
        {PRINCIPLES.map(([title, text]) => (
          <div key={title} className="rounded-xl border border-[var(--outline-variant)] bg-white p-6">
            <dt className="text-[16px] font-semibold">{title}</dt>
            <dd className="mt-2 text-[14px] leading-6 text-[var(--on-surface-variant)]">{text}</dd>
          </div>
        ))}
      </dl>
      <p className="text-center text-[15px]">
        Questions? <Link href="/contact" className="font-semibold text-[var(--primary)] hover:underline">Get in touch</Link>.
      </p>
    </div>
  );
}
