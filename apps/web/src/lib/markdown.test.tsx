import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Markdown, parseFrontmatter, slugify } from "@/lib/markdown";

describe("markdown", () => {
  it("parses frontmatter", () => {
    const { data, body } = parseFrontmatter('---\ntitle: "Hello"\ndate: 2026-10-01\n---\nBody text');
    expect(data).toEqual({ title: "Hello", date: "2026-10-01" });
    expect(body).toBe("Body text");
  });

  it("renders blocks and inline formatting without raw HTML", () => {
    render(
      <Markdown
        source={[
          "## Set up DNS",
          "Add **SPF** and *DKIM* records, then run `dig`.",
          "",
          "- First [guide](/help/getting-started)",
          "- Then [external](https://example.com) and [bad](javascript:alert(1))",
          "",
          "1. One",
          "2. Two",
          "",
          "> Tip: test first",
          "",
          "```",
          "<script>alert(1)</script>",
          "```",
          ">\tweird line",
          "<b>not html</b>",
        ].join("\n")}
      />,
    );
    expect(screen.getByRole("heading", { level: 2, name: "Set up DNS" })).toHaveAttribute("id", "set-up-dns");
    expect(screen.getByText("SPF").tagName).toBe("STRONG");
    expect(screen.getByText("DKIM").tagName).toBe("EM");
    expect(screen.getByRole("link", { name: "guide" })).toHaveAttribute("href", "/help/getting-started");
    expect(screen.getByRole("link", { name: "bad" })).toHaveAttribute("href", "#");
    expect(screen.getAllByRole("list")).toHaveLength(2);
    expect(screen.getByText("<script>alert(1)</script>").tagName).toBe("CODE");
    expect(screen.getByText("<b>not html</b>")).toBeInTheDocument();
    expect(document.querySelector("script")).toBeNull();
  });

  it("slugifies headings", () => {
    expect(slugify("What's new in October?")).toBe("whats-new-in-october");
  });
});
