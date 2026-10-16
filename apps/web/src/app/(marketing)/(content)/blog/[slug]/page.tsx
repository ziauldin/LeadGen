import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { blogPosts } from "@/lib/content";
import { Markdown } from "@/lib/markdown";
import { SITE } from "@/lib/marketing";

export const dynamicParams = false;

export function generateStaticParams() {
  return blogPosts().map((post) => ({ slug: post.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const post = blogPosts().find((p) => p.slug === slug);
  if (!post) return {};
  return {
    title: `${post.title} · LeadsGen blog`,
    description: post.summary,
    alternates: { canonical: `/blog/${post.slug}` },
    openGraph: { type: "article", publishedTime: post.date, title: post.title, description: post.summary },
  };
}

export default async function BlogPostPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const post = blogPosts().find((p) => p.slug === slug);
  if (!post) notFound();
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "BlogPosting",
    headline: post.title,
    description: post.summary,
    datePublished: post.date,
    author: { "@type": "Organization", name: post.author ?? SITE.name },
    publisher: { "@type": "Organization", name: SITE.name },
  };
  return (
    <article className="mx-auto max-w-3xl">
      <script
        type="application/ld+json"
        // Structured data for search engines; built from our own content, with "<" escaped.
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd).replace(/</g, "\\u003c") }}
      />
      <Link href="/blog" className="text-[13px] text-[var(--on-surface-variant)] hover:underline">
        ← All posts
      </Link>
      <h1 className="mt-3 text-[34px] font-bold leading-tight">{post.title}</h1>
      <p className="mt-2 text-[14px] text-[var(--on-surface-variant)]">
        {post.date
          ? new Date(post.date).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })
          : ""}
        {post.author ? ` · ${post.author}` : ""}
      </p>
      <Markdown source={post.body} />
    </article>
  );
}
