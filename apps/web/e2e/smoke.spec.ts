import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { linkFromLog } from "./helpers";

const EMAIL = `owner+${Date.now()}@acme-e2e.co.uk`;
const PASSWORD = "correct-horse-battery";

const CSV = [
  "full_name,job_title,company,website,linkedin_url,email,source_url,compliance_source_note,niche",
  "Alex Morgan,Quality Manager,Example Foods,https://example-foods.co.uk,,alex@example-foods.co.uk,https://example.com/listing,Public company listing,E2E Niche",
  "Jo Patel,Technical Director,Northern Grain,https://northern-grain.co.uk,,jo@northern-grain.co.uk,https://example.com/listing,Public company listing,E2E Niche",
].join("\n");


/** An API client that uses the browser's session (refresh cookie → access token). */
async function apiFor(page: Page): Promise<APIRequestContext & { token: string }> {
  const refreshed = await page.request.post("/api/auth/refresh", {
    headers: { "X-Requested-With": "fetch" },
  });
  expect(refreshed.ok()).toBeTruthy();
  const { access_token: token } = await refreshed.json();
  return Object.assign(page.request, { token });
}

function auth(token: string) {
  return { Authorization: `Bearer ${token}` };
}

test("sign up, build a campaign, approve, send, and handle a reply", async ({ page }) => {
  // --- Sign up and verify -------------------------------------------------------------------
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login/);
  await page.getByRole("link", { name: "Create an account" }).click();
  await page.getByLabel("Your name").fill("Sam Owner");
  await page.getByLabel("Work email").fill(EMAIL);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/dashboard/);
  await expect(page.getByText(/Confirm your email address/)).toBeVisible();

  const verifyLink = new URL(await linkFromLog("/verify-email"));
  await page.goto(verifyLink.pathname + verifyLink.search);
  await expect(page.getByText("Thanks, your email address is confirmed.")).toBeVisible();

  // --- Setup through the API (the UI for these is covered by component tests) ---------------
  const api = await apiFor(page);
  const headers = auth(api.token);
  expect(
    (
      await api.patch("/api/settings", {
        headers,
        data: { sender_name: "Sam Owner", sender_company: "Acme Insights", business_address: "1 High St, London" },
      })
    ).ok(),
  ).toBeTruthy();
  const credential = await (
    await api.post("/api/provider-settings", {
      headers,
      data: { provider_type: "email", provider_name: "mock", config: {} },
    })
  ).json();
  expect((await api.patch(`/api/provider-settings/${credential.id}/activate`, { headers })).ok()).toBeTruthy();
  const niche = await (
    await api.post("/api/niches", {
      headers,
      data: { name: "E2E Niche", country: "UK", industry: "Food Manufacturing", target_roles: ["Quality Manager"], keywords: ["food safety"] },
    })
  ).json();

  // --- Import leads in the UI ---------------------------------------------------------------
  await page.goto("/leads");
  await page.getByRole("button", { name: /Import CSV/ }).click();
  await page.locator('input[type="file"]').setInputFiles({ name: "leads.csv", mimeType: "text/csv", buffer: Buffer.from(CSV) });
  await page.getByRole("button", { name: /^Import/ }).last().click();
  await expect(page.getByText(/2 created|Created\s*2/i)).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("link", { name: "Alex Morgan" })).toBeVisible();

  // --- A two-step campaign ------------------------------------------------------------------
  const campaign = await (
    await api.post("/api/campaigns", {
      headers,
      data: {
        niche_id: niche.id,
        name: "E2E campaign",
        sending_window_start: "00:00",
        sending_window_end: "23:59",
        sending_days: [0, 1, 2, 3, 4, 5, 6],
        steps: [
          { step_number: 1, template_id: "system:intro" },
          { step_number: 2, delay_days: 3, template_id: "system:follow-up" },
        ],
      },
    })
  ).json();

  // --- Bulk-add the leads to the campaign ---------------------------------------------------
  await page.reload();
  await expect(page.getByText("Showing 1–2 of 2")).toBeVisible();
  await page.getByRole("checkbox", { name: "Select all rows on this page" }).check();
  await page.getByRole("region", { name: "Bulk actions" }).getByRole("button", { name: /Add to campaign/ }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("combobox", { name: "Campaign" }).click();
  await page.getByRole("option", { name: /E2E campaign/ }).click();
  await dialog.getByRole("button", { name: "Add to campaign" }).click();
  await expect(page.getByRole("link", { name: /Approvals 2 waiting/ })).toBeVisible();
  if (await dialog.isVisible()) await page.keyboard.press("Escape");

  // --- Edit and approve in the queue --------------------------------------------------------
  await page.goto("/approvals");
  const approve = page.getByRole("button", { name: /Approve & next/ });
  await expect(approve).toBeEnabled();
  await approve.click();
  await expect(page.getByText(/approved/i).first()).toBeVisible();
  await page.keyboard.press("a");
  await expect(page.getByText("Nothing waiting for review")).toBeVisible();

  // --- Start and send (mock provider), then see the emails marked sent -----------------------
  await page.goto(`/campaigns/${campaign.id}`);
  await page.getByRole("button", { name: /^(Start|Resume)/ }).first().click();
  await page.getByRole("dialog").getByRole("button", { name: /Start|Resume/ }).click();
  await page.getByRole("button", { name: "Send due emails now" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Send due emails" }).click();
  await page.getByRole("tab", { name: "Emails" }).click();
  await expect(page.getByText("Sent", { exact: true }).first()).toBeVisible();

  // --- A simulated reply stops that lead's sequence -----------------------------------------
  expect((await api.post("/api/replies/sync", { headers })).ok()).toBeTruthy();
  await page.goto(`/campaigns/${campaign.id}?tab=enrollments`);
  await expect(page.getByRole("cell", { name: "Replied", exact: true }).first()).toBeVisible();
  await page.goto("/replies");
  await expect(page.getByRole("link").filter({ hasText: /Re:/ }).first()).toBeVisible();

  // --- Answer it from the unified inbox ------------------------------------------------------
  await page.goto("/inbox");
  await page
    .getByRole("list", { name: "Conversations" })
    .getByRole("button")
    .filter({ hasNotText: /unsubscribe/i })
    .first()
    .click();
  await expect(page.getByRole("list", { name: "Messages" }).getByRole("listitem")).toHaveCount(2);
  await page.getByLabel("Reply", { exact: true }).fill("Thanks for getting back to me. Does Tuesday at 10 work?");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByText("Reply sent")).toBeVisible();
  await expect(page.getByRole("list", { name: "Messages" }).getByRole("listitem")).toHaveCount(3);

  // --- Unsubscribe link shows a confirmation; nothing happens until it's submitted -----------
  const leads = await (await api.get(`/api/leads?search=Jo Patel`, { headers })).json();
  const draft = await (
    await api.post("/api/emails/generate", { headers, data: { lead_id: leads.items[0].id } })
  ).json();
  const before = (await (await api.get("/api/suppressions", { headers })).json()).total;
  await page.goto(`/api/unsubscribe/${draft.message.unsubscribe_token}`);
  await expect(page.getByRole("button", { name: "Unsubscribe" })).toBeVisible();
  const after = (await (await api.get("/api/suppressions", { headers })).json()).total;
  expect(after).toBe(before);

  // --- Mobile navigation and sign out ---------------------------------------------------------
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/dashboard");
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("dialog").getByRole("link", { name: "Templates" }).click();
  await expect(page).toHaveURL(/\/templates/);
  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/\/login/);
  await page.goto("/leads");
  await expect(page).toHaveURL(/\/login\?next=/);
});
