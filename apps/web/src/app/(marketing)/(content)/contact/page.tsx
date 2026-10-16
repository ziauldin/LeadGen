import type { Metadata } from "next";
import { ContactForm } from "@/components/marketing/contact-form";
import { PageIntro } from "@/components/marketing/site-chrome";
import { SITE } from "@/lib/marketing";

export const metadata: Metadata = {
  title: "Contact · LeadsGen",
  description: "Talk to the LeadsGen team about demos, plans, support or privacy.",
  alternates: { canonical: "/contact" },
};

export default function ContactPage() {
  return (
    <div className="space-y-10">
      <PageIntro eyebrow="Contact" title="Talk to us">
        Questions about plans, a demo for your team, or help with your account. For privacy requests you
        can also email <a className="underline" href={`mailto:${SITE.privacyEmail}`}>{SITE.privacyEmail}</a>.
      </PageIntro>
      <div className="mx-auto max-w-2xl rounded-xl border border-[var(--outline-variant)] bg-[var(--surface-container-lowest)] p-6 sm:p-8">
        <ContactForm />
      </div>
    </div>
  );
}
