import type { Metadata } from "next";
import { PageIntro } from "@/components/marketing/site-chrome";
import { CHANGELOG } from "@/content/changelog";

export const metadata: Metadata = {
  title: "Changelog · LeadsGen",
  description: "New features and improvements in LeadsGen.",
  alternates: { canonical: "/changelog" },
};

export default function ChangelogPage() {
  return (
    <div className="space-y-10">
      <PageIntro eyebrow="Changelog" title="What's new" />
      <ol className="mx-auto max-w-3xl space-y-8">
        {CHANGELOG.map((entry) => (
          <li key={entry.id} id={entry.id} className="border-l-2 border-[var(--primary)] pl-5">
            <p className="text-[13px] text-[var(--on-surface-variant)]">
              {new Date(entry.date).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })}
            </p>
            <h2 className="mt-1 text-[20px] font-semibold">{entry.title}</h2>
            <ul className="mt-3 list-disc space-y-1.5 pl-5 text-[15px]">
              {entry.items.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </li>
        ))}
      </ol>
    </div>
  );
}
