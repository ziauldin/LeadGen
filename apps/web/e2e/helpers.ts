import AxeBuilder from "@axe-core/playwright";
import { execFileSync } from "node:child_process";
import { createHmac } from "node:crypto";
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

const BASE32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";

/** RFC 6238 TOTP code for a base32 secret, `stepsAhead` 30-second steps from now. */
export function totp(secret: string, stepsAhead = 0): string {
  let bits = "";
  for (const char of secret.replace(/=+$/, "").toUpperCase()) {
    bits += BASE32.indexOf(char).toString(2).padStart(5, "0");
  }
  const key = Buffer.from(bits.match(/.{8}/g)!.map((byte) => parseInt(byte, 2)));
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 1000 / 30) + stepsAhead));
  const hmac = createHmac("sha1", key).update(counter).digest();
  const offset = hmac[hmac.length - 1] & 0xf;
  const value = (hmac.readUInt32BE(offset) & 0x7fffffff) % 1_000_000;
  return String(value).padStart(6, "0");
}

// Fail on serious or critical WCAG 2.1 A/AA problems; report the rest in the test output.
export async function expectAccessible(page: Page, name: string) {
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


/** Run the API's superuser CLI against the end-to-end database. */
export function grantSuperuser(email: string) {
  const api = resolve(__dirname, "../../../services/api");
  execFileSync(process.env.E2E_PYTHON ?? "python", ["-m", "scripts.manage_superusers", "grant", email], {
    cwd: api,
    env: { ...process.env, DATABASE_URL: `sqlite:///${resolve(api, "data/e2e.db").split("\\").join("/")}` },
  });
}
