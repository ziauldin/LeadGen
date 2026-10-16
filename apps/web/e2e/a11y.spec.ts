import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { signUp } from "./helpers";

// Fail on serious or critical WCAG 2.1 A/AA problems; report the rest in the test output.
async function expectAccessible(page: Page, name: string) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  const blocking = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  const summary = blocking.map(
    (v) =>
      `${v.id} (${v.impact}): ${v.help} — ${v.nodes.length} element(s): ` +
      v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | "),
  );
  expect(summary, `${name} has accessibility problems`).toEqual([]);
}

test("public pages are accessible", async ({ page }) => {
  for (const path of ["/login", "/login/sso", "/register", "/forgot-password"]) {
    await page.goto(path);
    await expectAccessible(page, path);
  }
});

test("main app pages are accessible", async ({ page }) => {
  await signUp(page, `a11y+${Date.now()}@acme-e2e.co.uk`);
  for (const path of [
    "/dashboard",
    "/leads",
    "/companies",
    "/approvals",
    "/campaigns",
    "/campaigns/new",
    "/templates",
    "/email-studio",
    "/replies",
    "/settings/workspace",
    "/settings/providers",
    "/settings/security",
    "/settings/sso",
    "/settings/roles",
    "/settings/audit",
  ]) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    await expectAccessible(page, path);
  }
});
