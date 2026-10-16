import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, type Page } from "@playwright/test";

const API_LOG = resolve(__dirname, "../../../services/api/e2e-api.log");

/** The newest link of a kind from the console mailer's output in the API log. */
export async function linkFromLog(path: string, email?: string): Promise<string> {
  for (let attempt = 0; attempt < 30; attempt += 1) {
    const log = readFileSync(API_LOG, "utf-8");
    const scope = email ? log.slice(log.lastIndexOf(`to=${email}`)) : log;
    const pattern = new RegExp(String.raw`(https?://\S+${path}\?token=[\w%-]+)`, "g");
    const matches = [...scope.matchAll(pattern)];
    if (matches.length) return matches[matches.length - 1][1];
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`No ${path} link in the API log`);
}

/** Register and verify a fresh account through the UI, leaving the page signed in. */
export async function signUp(page: Page, email: string, password = "correct-horse-battery") {
  await page.goto("/register");
  await page.getByLabel("Your name").fill("Sam Owner");
  await page.getByLabel("Work email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/dashboard/);
  const link = new URL(await linkFromLog("/verify-email", email));
  await page.goto(link.pathname + link.search);
  await expect(page.getByText("Thanks, your email address is confirmed.")).toBeVisible();
}
