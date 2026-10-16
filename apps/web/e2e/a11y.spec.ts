import { test } from "@playwright/test";
import { expectAccessible, signUp } from "./helpers";

test("public pages are accessible", async ({ page }) => {
  for (const path of ["/login", "/login/sso", "/register", "/forgot-password", "/subprocessors"]) {
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
    "/settings/privacy",
    "/settings/api",
    "/settings/usage",
  ]) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    await expectAccessible(page, path);
  }
});
