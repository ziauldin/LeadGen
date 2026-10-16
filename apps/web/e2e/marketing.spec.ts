import { expect, test } from "@playwright/test";
import { expectAccessible } from "./helpers";

test("public site: mobile menu, pricing switch and the estimate calculator", async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem("lg_cookie_consent", "essential"));

  // Mobile: the menu button opens the navigation, Escape closes it, links navigate.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Book more meetings");
  await page.getByRole("button", { name: "Open menu" }).click();
  const menu = page.getByRole("navigation", { name: "Main (mobile)" });
  await expect(menu).toBeVisible();
  await expectAccessible(page, "/ with the mobile menu open");
  await page.keyboard.press("Escape");
  await expect(menu).toBeHidden();
  await page.getByRole("button", { name: "Open menu" }).click();
  await menu.getByRole("link", { name: "Pricing" }).click();
  await expect(page).toHaveURL(/\/pricing$/);

  // Pricing: yearly by default (shown per month), monthly on request.
  await page.setViewportSize({ width: 1280, height: 900 });
  const starter = page.getByRole("listitem").filter({ has: page.getByRole("heading", { name: "starter" }) });
  await expect(starter.getByText("$390 billed yearly")).toBeVisible();
  await expect(starter.getByText("$32.50")).toBeVisible();
  await page.getByRole("radio", { name: "Monthly" }).click();
  await expect(starter.getByText("$39")).toBeVisible();
  await expect(starter.getByText("Billed monthly, cancel any time")).toBeVisible();
  await expect(page.getByRole("list", { name: "Credit packs" }).getByText("1,000 credits")).toBeVisible();

  // The calculator responds to its inputs.
  await page.goto("/");
  const prospects = page.getByLabel("New prospects emailed a month");
  await prospects.fill("2000");
  await expect(page.getByText("$36,000")).toBeVisible(); // 2,000 × 5% × 30% × 20% × $6,000
});
