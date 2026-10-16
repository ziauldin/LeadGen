import type { Metadata } from "next";
import { HelpSearch } from "@/components/marketing/help-search";
import { PageIntro } from "@/components/marketing/site-chrome";
import { helpArticles } from "@/lib/content";

export const metadata: Metadata = {
  title: "Help center · LeadsGen",
  description: "Guides for setting up sending, writing campaigns, handling replies, privacy requests and more.",
  alternates: { canonical: "/help" },
};

export default function HelpCenterPage() {
  const articles = helpArticles().map(({ slug, title, summary, category }) => ({
    slug,
    title,
    summary,
    category: category ?? "General",
  }));
  return (
    <div className="space-y-10">
      <PageIntro eyebrow="Help center" title="How can we help?" />
      <HelpSearch articles={articles} />
    </div>
  );
}
