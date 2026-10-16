import type { MetadataRoute } from "next";
import { LEGAL_DOCUMENTS } from "@/content/legal";
import { SITE } from "@/lib/marketing";

const PAGES = ["", "/features", "/use-cases", "/pricing", "/about", "/contact", "/docs/api", "/subprocessors"];

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  return [
    ...PAGES.map((path) => ({
      url: `${SITE.url}${path}`,
      lastModified: now,
      changeFrequency: "weekly" as const,
      priority: path === "" ? 1 : 0.7,
    })),
    ...LEGAL_DOCUMENTS.map((doc) => ({
      url: `${SITE.url}/legal/${doc.slug}`,
      lastModified: new Date(doc.updated),
      changeFrequency: "yearly" as const,
      priority: 0.3,
    })),
  ];
}
