import type { MetadataRoute } from "next";
import { LEGAL_DOCUMENTS } from "@/content/legal";
import { blogPosts, helpArticles } from "@/lib/content";
import { SITE } from "@/lib/marketing";

const PAGES = ["", "/features", "/use-cases", "/pricing", "/about", "/contact", "/docs/api", "/help", "/blog", "/changelog", "/subprocessors"];

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  return [
    ...PAGES.map((path) => ({
      url: `${SITE.url}${path}`,
      lastModified: now,
      changeFrequency: "weekly" as const,
      priority: path === "" ? 1 : 0.7,
    })),
    ...helpArticles().map((article) => ({
      url: `${SITE.url}/help/${article.slug}`,
      lastModified: now,
      changeFrequency: "monthly" as const,
      priority: 0.5,
    })),
    ...blogPosts().map((post) => ({
      url: `${SITE.url}/blog/${post.slug}`,
      lastModified: post.date ? new Date(post.date) : now,
      changeFrequency: "yearly" as const,
      priority: 0.6,
    })),
    ...LEGAL_DOCUMENTS.map((doc) => ({
      url: `${SITE.url}/legal/${doc.slug}`,
      lastModified: new Date(doc.updated),
      changeFrequency: "yearly" as const,
      priority: 0.3,
    })),
  ];
}
