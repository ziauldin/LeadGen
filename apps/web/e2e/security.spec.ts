import { expect, test } from "@playwright/test";
import { signUp, totp } from "./helpers";

const PASSWORD = "correct-horse-battery";

test("turn on two-factor, sign out, and sign back in with a code", async ({ page }) => {
  const email = `mfa+${Date.now()}@acme-e2e.co.uk`;
  await signUp(page, email, PASSWORD);

  await page.goto("/settings/security");
  await page.getByRole("button", { name: "Set up two-factor" }).click();
  await expect(page.getByAltText("QR code to scan with your authenticator app")).toBeVisible();
  const secret = (await page.locator("code").first().textContent())!.trim();
  await page.getByLabel("Code from your app").fill(totp(secret));
  await page.getByRole("button", { name: "Turn on" }).click();

  const codes = page.getByRole("region", { name: "Recovery codes" });
  await expect(codes.getByRole("listitem")).toHaveCount(10);
  await page.getByRole("button", { name: "I've saved them" }).click();
  await expect(page.getByText(/On · 10 recovery codes left/)).toBeVisible();

  await page.getByRole("button", { name: /Account menu/ }).click();
  await page.getByRole("menuitem", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/\/login/);

  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  // The setup code's time step is used up, so sign in with the next one.
  await page.getByLabel("Authentication code").fill(totp(secret, 1));
  await page.getByRole("button", { name: "Verify and sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard/);

  await page.goto("/settings/security");
  await expect(page.getByText("This device")).toBeVisible();
});
