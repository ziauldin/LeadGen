import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { helpArticles } from "@/lib/content";
import { Markdown } from "@/lib/markdown";

export const dynamicParams = false;

export function generateStaticParams() {
  return helpArticles().map((article) => ({ slug: article.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const article = helpArticles().find((a) => a.slug === slug);
  if (!article) return {};
  return {
    title: `${article.title} · LeadsGen help`,
    description: article.summary,
    alternates: { canonical: `/help/${article.slug}` },
  };
}

export default async function HelpArticlePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const articles = helpArticles();
  const article = articles.find((a) => a.slug === slug);
  if (!article) notFound();
  const related = articles.filter((a) => a.category === article.category && a.slug !== slug).slice(0, 3);
  return (
    <div className="mx-auto grid max-w-5xl gap-10 lg:grid-cols-[minmax(0,1fr)_240px]">
      <article>
        <nav aria-label="Breadcrumb" className="text-[13px] text-[var(--on-surface-variant)]">
          <Link href="/help" className="hover:underline">
            Help center
          </Link>{" "}
          / {article.category}
        </nav>
        <h1 className="mt-2 text-[32px] font-bold">{article.title}</h1>
        <p className="mt-2 text-[16px] text-[var(--on-surface-variant)]">{article.summary}</p>
        <Markdown source={article.body} />
        <p className="mt-10 rounded-lg bg-[var(--surface-container-low)] p-4 text-[14px]">
          Still stuck?{" "}
          <Link href="/contact" className="font-semibold text-[var(--primary)] hover:underline">
            Contact us
          </Link>
          .
        </p>
      </article>
      {related.length ? (
        <aside aria-label="Related articles">
          <p className="text-[13px] font-semibold">Related</p>
          <ul className="mt-2 space-y-2 text-[14px]">
            {related.map((a) => (
              <li key={a.slug}>
                <Link href={`/help/${a.slug}`} className="text-[var(--primary)] hover:underline">
                  {a.title}
                </Link>
              </li>
            ))}
          </ul>
        </aside>
      ) : null}
    </div>
  );
}
