/** Server-only: Markdown content (help articles, blog posts) read at build time. */
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { parseFrontmatter } from "@/lib/markdown";

export type ContentEntry = {
  slug: string;
  title: string;
  summary: string;
  body: string;
  category?: string;
  order: number;
  date?: string;
  author?: string;
};

const ROOT = join(process.cwd(), "src", "content");

function load(folder: "help" | "blog"): ContentEntry[] {
  const directory = join(ROOT, folder);
  return readdirSync(directory)
    .filter((file) => file.endsWith(".md"))
    .map((file) => {
      const { data, body } = parseFrontmatter(readFileSync(join(directory, file), "utf-8"));
      return {
        slug: file.replace(/\.md$/, ""),
        title: data.title ?? file,
        summary: data.summary ?? "",
        body,
        category: data.category,
        order: Number(data.order ?? 999),
        date: data.date,
        author: data.author,
      };
    });
}

export function helpArticles(): ContentEntry[] {
  return load("help").sort((a, b) => a.order - b.order || a.title.localeCompare(b.title));
}

export function blogPosts(): ContentEntry[] {
  return load("blog").sort((a, b) => (b.date ?? "").localeCompare(a.date ?? ""));
}
