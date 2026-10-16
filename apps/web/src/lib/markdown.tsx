/**
 * A small, safe Markdown renderer for our own content (help, blog, changelog).
 * Supports headings, paragraphs, lists, code blocks, blockquotes, **bold**, *italic*, `code`
 * and [links](url). It builds React elements directly, so nothing is injected as raw HTML.
 */
import Link from "next/link";
import type { ReactNode } from "react";

export type Frontmatter = Record<string, string>;

export function parseFrontmatter(source: string): { data: Frontmatter; body: string } {
  const match = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?/.exec(source);
  if (!match) return { data: {}, body: source };
  const data: Frontmatter = {};
  for (const line of match[1].split(/\r?\n/)) {
    const index = line.indexOf(":");
    if (index > 0) data[line.slice(0, index).trim()] = line.slice(index + 1).trim().replace(/^"(.*)"$/, "$1");
  }
  return { data, body: source.slice(match[0].length) };
}

const INLINE = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^)\s]+\))/g;

function inline(text: string, keyPrefix: string): ReactNode[] {
  const parts = text.split(INLINE).filter(Boolean);
  return parts.map((part, index) => {
    const key = `${keyPrefix}-${index}`;
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={key}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code key={key} className="rounded bg-[var(--surface-container)] px-1 py-0.5 font-mono text-[0.9em]">
          {part.slice(1, -1)}
        </code>
      );
    }
    const link = /^\[([^\]]+)\]\(([^)\s]+)\)$/.exec(part);
    if (link) {
      const [, label, href] = link;
      if (href.startsWith("/")) {
        return (
          <Link key={key} href={href} className="text-[var(--primary)] underline underline-offset-2">
            {label}
          </Link>
        );
      }
      const safe = /^(https?:|mailto:)/.test(href) ? href : "#";
      return (
        <a key={key} href={safe} className="text-[var(--primary)] underline underline-offset-2" rel="noreferrer">
          {label}
        </a>
      );
    }
    if (part.startsWith("*") && part.endsWith("*") && part.length > 2) return <em key={key}>{part.slice(1, -1)}</em>;
    return part;
  });
}

export function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-");
}

export function Markdown({ source }: { source: string }) {
  const lines = source.replace(/\r\n/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let index = 0;
  let key = 0;

  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }
    if (line.startsWith("```")) {
      const code: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].startsWith("```")) code.push(lines[index++]);
      index += 1;
      blocks.push(
        <pre key={key++} className="my-4 overflow-x-auto rounded-lg bg-[#111827] p-4 text-[13px] text-white" tabIndex={0}>
          <code>{code.join("\n")}</code>
        </pre>,
      );
      continue;
    }
    const heading = /^(#{2,4})\s+(.*)$/.exec(line);
    if (heading) {
      const level = heading[1].length;
      const text = heading[2];
      const className = level === 2 ? "mt-8 text-[22px] font-bold" : level === 3 ? "mt-6 text-[18px] font-semibold" : "mt-4 text-[16px] font-semibold";
      const Tag = (level === 2 ? "h2" : level === 3 ? "h3" : "h4") as "h2" | "h3" | "h4";
      blocks.push(
        <Tag key={key++} id={slugify(text)} className={className}>
          {inline(text, `h${key}`)}
        </Tag>,
      );
      index += 1;
      continue;
    }
    if (/^(\s*[-*]|\s*\d+\.)\s+/.test(line)) {
      const ordered = /^\s*\d+\./.test(line);
      const items: string[] = [];
      while (index < lines.length && /^(\s*[-*]|\s*\d+\.)\s+/.test(lines[index])) {
        items.push(lines[index].replace(/^(\s*[-*]|\s*\d+\.)\s+/, ""));
        index += 1;
      }
      const List = ordered ? "ol" : "ul";
      blocks.push(
        <List key={key++} className={`my-4 space-y-1.5 pl-6 ${ordered ? "list-decimal" : "list-disc"}`}>
          {items.map((item, i) => (
            <li key={i}>{inline(item, `li${key}-${i}`)}</li>
          ))}
        </List>,
      );
      continue;
    }
    if (line.startsWith("> ")) {
      const quote: string[] = [];
      while (index < lines.length && lines[index].startsWith("> ")) quote.push(lines[index++].slice(2));
      blocks.push(
        <blockquote key={key++} className="my-4 border-l-4 border-[var(--primary)] bg-[var(--surface-container-low)] px-4 py-2">
          {inline(quote.join(" "), `q${key}`)}
        </blockquote>,
      );
      continue;
    }
    const paragraph: string[] = [];
    while (index < lines.length && lines[index].trim() && !/^(#{2,4}\s|```|>\s|\s*[-*]\s|\s*\d+\.\s)/.test(lines[index])) {
      paragraph.push(lines[index++].trim());
    }
    if (!paragraph.length) paragraph.push(lines[index++].trim()); // always make progress
    blocks.push(
      <p key={key++} className="my-4">
        {inline(paragraph.join(" "), `p${key}`)}
      </p>,
    );
  }
  return <div className="text-[15px] leading-7">{blocks}</div>;
}
