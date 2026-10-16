import { expect, test } from "@playwright/test";
import { expectAccessible, grantSuperuser, signUp } from "./helpers";

test("an admin finds a workspace and views it read-only as the customer", async ({ browser }) => {
  const stamp = Date.now();
  const customerEmail = `customer+${stamp}@acme-e2e.co.uk`;
  const adminEmail = `ops+${stamp}@leadsgen-e2e.co.uk`;

  const customer = await browser.newContext();
  const customerPage = await customer.newPage();
  await signUp(customerPage, customerEmail);
  await customer.close();

  const context = await browser.newContext();
  const page = await context.newPage();
  await signUp(page, adminEmail);
  grantSuperuser(adminEmail);
  // Existing access tokens are invalidated; the page load refreshes the session.
  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await expectAccessible(page, "/admin");

  await page.goto("/admin/workspaces");
  await page.getByLabel("Search by name or member email").fill(customerEmail);
  const row = page.getByRole("table", { name: "Workspaces" }).getByRole("row").filter({ hasText: customerEmail });
  await row.getByRole("link").click();
  await expect(page.getByText(`Owner ${customerEmail}`, { exact: false }).first()).toBeVisible();
  await expectAccessible(page, "/admin/workspaces/[id]");

  await page.getByRole("button", { name: "View as customer" }).click();
  await page.getByRole("dialog").getByLabel("Reason").fill("E2E: checking the customer's dashboard");
  const [viewer] = await Promise.all([
    context.waitForEvent("page"),
    page.getByRole("button", { name: "Open as customer" }).click(),
  ]);
  await expect(viewer).toHaveURL(/\/dashboard/);
  await expect(viewer.getByText(`as Sam Owner (${customerEmail})`)).toBeVisible();
  await expect(viewer.getByText(/Read-only/)).toBeVisible();

  // The admin's own tab is still the admin.
  await page.reload();
  await expect(page.getByRole("button", { name: "View as customer" })).toBeVisible();

  await viewer.getByRole("button", { name: "End session" }).click();
  await expect(viewer).toHaveURL(/\/admin\/workspaces/);

  for (const path of ["/admin/users", "/admin/abuse", "/admin/suppressions", "/admin/audit"]) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    await expectAccessible(page, path);
  }
  await expect(page.getByText("Impersonation started").first()).toBeVisible();
});
