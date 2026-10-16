import { expect, test } from "@playwright/test";
import { apiLogin, grantSuperuser, signUp } from "./helpers";

const CSV = [
  "full_name,job_title,company,website,linkedin_url,email,source_url,compliance_source_note,niche",
  "Alex Morgan,Quality Manager,Example Foods,https://example-foods.co.uk,,alex@example-foods.co.uk,https://example.com/listing,Public company listing,Product Niche",
  "Jo Patel,Technical Director,Northern Grain,https://northern-grain.co.uk,,jo@northern-grain.co.uk,https://example.com/listing,Public company listing,Product Niche",
].join("\n");
const BODY = "Hi {{first_name}},\n\nWorth a chat about {{company}}?\n\n{{sender_name}}\n\nOpt out: {{unsubscribe_link}}";

test("A/B test a campaign, follow the deal and analytics, export a person's data, and use the API", async ({ browser, request }) => {
  const stamp = Date.now();
  const email = `growth+${stamp}@acme-e2e.co.uk`;
  const context = await browser.newContext();
  const page = await context.newPage();
  await signUp(page, email);
  const headers = await apiLogin(request, email);

  // --- Setup through the API -----------------------------------------------------------------
  const ok = async (response: Promise<import("@playwright/test").APIResponse>) => {
    const result = await response;
    expect(result.ok(), await result.text()).toBeTruthy();
    return result.json();
  };
  await ok(request.patch("/api/settings", { headers, data: { sender_name: "Sam", sender_company: "Acme Insights", business_address: "1 High St, London" } }));
  const credential = await ok(request.post("/api/provider-settings", { headers, data: { provider_type: "email", provider_name: "mock", config: {} } }));
  await ok(request.patch(`/api/provider-settings/${credential.id}/activate`, { headers }));
  const niche = await ok(request.post("/api/niches", { headers, data: { name: "Product Niche", country: "UK", industry: "Food", target_roles: ["Quality Manager"] } }));
  await ok(request.post("/api/leads/import-csv", { headers, multipart: { file: { name: "leads.csv", mimeType: "text/csv", buffer: Buffer.from(CSV) } } }));
  const leads = await ok(request.get("/api/leads", { headers }));
  const campaign = await ok(
    request.post("/api/campaigns", {
      headers,
      data: {
        niche_id: niche.id,
        name: "A/B campaign",
        sending_window_start: "00:00",
        sending_window_end: "23:59",
        sending_days: [0, 1, 2, 3, 4, 5, 6],
        steps: [
          {
            step_number: 1,
            subject_template: "Quick question about {{company}}",
            body_template: BODY,
            variants: [{ key: "B", subject_template: "An idea for {{company}}", body_template: BODY }],
          },
        ],
      },
    }),
  );
  const added = await ok(request.post(`/api/campaigns/${campaign.id}/add-leads`, { headers, data: { lead_ids: leads.items.map((l: { id: number }) => l.id) } }));
  for (const id of added.message_ids) await ok(request.post("/api/emails/approve", { headers, data: { email_message_id: id } }));
  await ok(request.post(`/api/campaigns/${campaign.id}/start`, { headers }));
  await ok(request.post(`/api/campaigns/${campaign.id}/process-sends`, { headers }));
  await ok(request.post("/api/replies/sync", { headers }));

  // --- The campaign overview shows results for each version ---------------------------------
  await page.goto(`/campaigns/${campaign.id}`);
  await expect(page.getByRole("heading", { name: "A/B test results" })).toBeVisible();
  const results = page.getByRole("table", { name: "Results for each version of step 1" });
  await expect(results.getByRole("rowheader", { name: "A" })).toBeVisible();
  await expect(results.getByRole("rowheader", { name: "B" })).toBeVisible();

  // --- Analytics -------------------------------------------------------------------------------
  await page.getByRole("navigation").getByRole("link", { name: "Analytics" }).first().click();
  await expect(page).toHaveURL(/\/analytics/);
  await expect(page.getByText("Emails sent")).toBeVisible();
  await page.getByRole("button", { name: "A/B version" }).click();
  await expect(page.getByRole("table").getByRole("rowheader", { name: "B" })).toBeVisible();

  // --- The interested reply opened a deal ------------------------------------------------------
  await page.goto("/deals");
  await expect(page.getByText(/Alex Morgan|Jo Patel/).first()).toBeVisible();

  // --- Export everything held about a person ----------------------------------------------------
  await page.goto("/settings/privacy");
  await page.getByLabel("Person's email address").fill("alex@example-foods.co.uk");
  await page.getByRole("button", { name: "Export their data" }).click();
  const requests = page.getByRole("list", { name: "Data requests" });
  await expect(requests.getByText("alex@example-foods.co.uk")).toBeVisible();
  await expect(requests.getByText("completed")).toBeVisible();

  // --- An operator moves the workspace to Pro; the customer creates an API key ------------------
  const ops = await browser.newContext();
  const opsPage = await ops.newPage();
  const opsEmail = `ops+${stamp}@leadsgen-e2e.co.uk`;
  await signUp(opsPage, opsEmail);
  grantSuperuser(opsEmail);
  const workspace = await ok(request.get("/api/workspaces/current", { headers }));
  const adminHeaders = await apiLogin(request, opsEmail);
  await ok(request.patch(`/api/admin/workspaces/${workspace.id}`, { headers: adminHeaders, data: { plan: "pro" } }));
  await ops.close();

  await page.goto("/settings/api");
  await page.getByRole("button", { name: "New key" }).click();
  await page.getByLabel("Name").fill("E2E script");
  await page.getByRole("button", { name: "Create key" }).click();
  const reveal = page.getByRole("dialog", { name: "Your new API key" });
  const key = (await reveal.locator("code").innerText()).trim();
  expect(key.length).toBeGreaterThan(20);
  await reveal.getByRole("button", { name: "Done" }).click();

  const viaApi = await request.get("/api/v1/leads", { headers: { Authorization: `Bearer ${key}` } });
  expect(viaApi.ok(), await viaApi.text()).toBeTruthy();
  const names = (await viaApi.json()).items.map((lead: { full_name: string }) => lead.full_name);
  expect(names).toEqual(expect.arrayContaining(["Alex Morgan", "Jo Patel"]));
  expect((await request.get("/api/v1/leads", { headers: { Authorization: "Bearer lg_wrong" } })).status()).toBe(401);
  await context.close();
});
