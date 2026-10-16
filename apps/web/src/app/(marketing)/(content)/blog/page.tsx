import type { Metadata } from "next";
import Link from "next/link";
import { PageIntro } from "@/components/marketing/site-chrome";
import { blogPosts } from "@/lib/content";

export const metadata: Metadata = {
  title: "Blog · LeadsGen",
  description: "Practical writing on compliant outbound, deliverability and sales that respects people.",
  alternates: { canonical: "/blog" },
};

function formatPostDate(date?: string) {
  return date ? new Date(date).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" }) : "";
}

export default function BlogIndexPage() {
  const posts = blogPosts();
  return (
    <div className="space-y-10">
      <PageIntro eyebrow="Blog" title="Notes on better outbound" />
      <ul className="mx-auto grid max-w-3xl gap-5">
        {posts.map((post) => (
          <li key={post.slug} className="rounded-xl border border-[var(--outline-variant)] bg-[var(--surface-container-lowest)] p-6">
            <p className="text-[13px] text-[var(--on-surface-variant)]">{formatPostDate(post.date)}</p>
            <h2 className="mt-1 text-[20px] font-semibold">
              <Link href={`/blog/${post.slug}`} className="hover:text-[var(--primary)]">
                {post.title}
              </Link>
            </h2>
            <p className="mt-2 text-[15px] text-[var(--on-surface-variant)]">{post.summary}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
