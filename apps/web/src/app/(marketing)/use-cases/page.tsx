import type { Metadata } from "next";
import { PageIntro } from "@/components/marketing/site-chrome";

export const metadata: Metadata = {
  title: "Use cases · LeadsGen",
  description: "How agencies, B2B SaaS teams, consultants and service businesses use LeadsGen for compliant outbound.",
  alternates: { canonical: "/use-cases" },
};

const CASES: { title: string; who: string; how: string[] }[] = [
  {
    title: "Agencies running outreach for clients",
    who: "One workspace per client keeps data, sending accounts and reports separate.",
    how: [
      "Invite client stakeholders as members with a read-only custom role",
      "Use each client's own sending domain and provider keys",
      "Hand over a full data export when an engagement ends",
    ],
  },
  {
    title: "B2B SaaS founders and sales teams",
    who: "Reach the right companies without buying lists or burning your domain.",
    how: [
      "Search niches by industry and region, then enrich and score",
      "Let AI draft the first email from your product notes, then approve in bulk",
      "Push interested replies to your CRM over webhooks",
    ],
  },
  {
    title: "Consultants and professional services",
    who: "Personal, low-volume outreach where every message matters.",
    how: [
      "Keep a legitimate-interest note for every person you contact",
      "Send a handful of carefully written emails a day within sending windows",
      "Answer data requests from your own account in minutes",
    ],
  },
  {
    title: "Local and trade businesses",
    who: "Find nearby businesses that could use what you offer.",
    how: [
      "Search public listings by town and category",
      "Use templates with the business name and location filled in",
      "Track replies and book calls from one inbox",
    ],
  },
];

export default function UseCasesPage() {
  return (
    <div className="space-y-12">
      <PageIntro eyebrow="Use cases" title="Built for teams who care how their outreach lands" />
      <div className="grid gap-6 md:grid-cols-2">
        {CASES.map((item) => (
          <section key={item.title} className="rounded-xl border border-[var(--outline-variant)] bg-white p-6">
            <h2 className="text-[19px] font-semibold">{item.title}</h2>
            <p className="mt-2 text-[14px] text-[var(--on-surface-variant)]">{item.who}</p>
            <ul className="mt-4 list-disc space-y-1.5 pl-5 text-[14px]">
              {item.how.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}
