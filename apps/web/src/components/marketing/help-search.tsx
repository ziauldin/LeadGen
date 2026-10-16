"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";

type Article = { slug: string; title: string; summary: string; category: string };

export function HelpSearch({ articles }: { articles: Article[] }) {
  const [query, setQuery] = useState("");
  const results = useMemo(() => {
    const words = query.toLowerCase().split(/\s+/).filter(Boolean);
    if (!words.length) return articles;
    return articles.filter((a) => {
      const text = `${a.title} ${a.summary} ${a.category}`.toLowerCase();
      return words.every((word) => text.includes(word));
    });
  }, [articles, query]);
  const groups = useMemo(() => {
    const map = new Map<string, Article[]>();
    for (const article of results) map.set(article.category, [...(map.get(article.category) ?? []), article]);
    return [...map.entries()];
  }, [results]);

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      <div className="relative mx-auto max-w-xl">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[var(--on-surface-variant)]" aria-hidden />
        <label htmlFor="help-search" className="sr-only">
          Search help articles
        </label>
        <Input
          id="help-search"
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search, e.g. DKIM, unsubscribe, invoices"
          className="h-11 bg-white pl-9 text-[15px]"
        />
      </div>
      <p className="sr-only" aria-live="polite">
        {results.length} {results.length === 1 ? "article" : "articles"} found
      </p>
      {groups.length ? (
        groups.map(([category, items]) => (
          <section key={category} aria-labelledby={`cat-${category}`}>
            <h2 id={`cat-${category}`} className="text-[18px] font-semibold">
              {category}
            </h2>
            <ul className="mt-3 grid gap-3 sm:grid-cols-2">
              {items.map((article) => (
                <li key={article.slug}>
                  <Link
                    href={`/help/${article.slug}`}
                    className="block h-full rounded-xl border border-[var(--outline-variant)] bg-white p-5 hover:border-[var(--primary)]"
                  >
                    <span className="text-[15px] font-semibold">{article.title}</span>
                    <span className="mt-1 block text-[14px] text-[var(--on-surface-variant)]">{article.summary}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ))
      ) : (
        <p className="text-center text-[15px] text-[var(--on-surface-variant)]">
          No articles match. <Link href="/contact" className="text-[var(--primary)] underline">Ask us instead</Link>.
        </p>
      )}
    </div>
  );
}
