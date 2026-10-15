import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { AddLeadsDialog, AddLeadsResults } from "@/components/campaigns/add-leads-dialog";
import { renderWithClient } from "@/test/render";
import { server } from "@/test/server";
import type { AddLeadsResult, Lead } from "@/lib/api/types";

const url = (path: string) => `http://localhost:3000/api${path}`;

function lead(id: number, name: string, overrides: Partial<Lead> = {}): Lead {
  return {
    id,
    full_name: name,
    niche_id: 3,
    company_id: null,
    company: { id: id * 10, name: `${name} Co`, domain: null, website: null, enrichment_status: null },
    compliance_source_note: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    email_contacts: [],
    job_title: "Founder",
    linkedin_url: null,
    primary_email: `${name.toLowerCase().replace(/\s/g, ".")}@example.com`,
    qualification_notes: null,
    score: 50,
    source_provider: null,
    source_url: null,
    status: "qualified",
    ...overrides,
  };
}

const RESULT: AddLeadsResult = {
  created: 1,
  skipped: 2,
  errors: [],
  message_ids: [99],
  results: [
    { id: 1, status: "ok", detail: "Draft 99 created" },
    { id: 2, status: "skipped", detail: "Already in this campaign" },
    { id: 3, status: "failed", detail: "Lead has no active email contact" },
  ],
};

describe("AddLeadsResults", () => {
  it("summarises outcomes and lists each lead's result, problems first", () => {
    renderWithClient(
      <AddLeadsResults
        result={RESULT}
        campaignId={7}
        leadNames={new Map([
          [1, "Ada Lovelace"],
          [2, "Alan Turing"],
        ])}
      />,
    );

    const summary = screen.getByLabelText("Summary");
    expect(within(summary).getByText("Drafts created").previousSibling).toHaveTextContent("1");
    expect(within(summary).getByText("Skipped").previousSibling).toHaveTextContent("1");
    expect(within(summary).getByText("Failed").previousSibling).toHaveTextContent("1");

    const items = within(screen.getByRole("list", { name: "Results for each lead" })).getAllByRole(
      "listitem",
    );
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveTextContent("Lead #3");
    expect(items[0]).toHaveTextContent("Lead has no active email contact");
    expect(items[1]).toHaveTextContent("Alan Turing");
    expect(items[1]).toHaveTextContent("Already in this campaign");
    expect(items[2]).toHaveTextContent("Ada Lovelace");
    expect(items[2]).toHaveTextContent("Added");

    expect(screen.getByText(/1 draft is waiting for approval/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Review in Approvals/ })).toHaveAttribute(
      "href",
      "/approvals?campaign_id=7",
    );
  });
});

describe("AddLeadsDialog", () => {
  it("lets the user pick leads, submits them and shows per-lead results", async () => {
    let leadQuery: URLSearchParams | null = null;
    let submitted: unknown = null;
    server.use(
      http.get(url("/leads"), ({ request }) => {
        leadQuery = new URL(request.url).searchParams;
        return HttpResponse.json({
          items: [
            lead(1, "Ada Lovelace"),
            lead(2, "Alan Turing"),
            lead(3, "Grace Hopper", { status: "opted_out" }),
          ],
          total: 3,
          skip: 0,
          limit: 20,
        });
      }),
      http.post(url("/campaigns/7/add-leads"), async ({ request }) => {
        submitted = await request.json();
        return HttpResponse.json({
          created: 1,
          skipped: 1,
          errors: [],
          message_ids: [99],
          results: [
            { id: 1, status: "ok", detail: "Draft 99 created" },
            { id: 2, status: "skipped", detail: "Already in this campaign" },
          ],
        } satisfies AddLeadsResult);
      }),
    );

    const user = userEvent.setup();
    renderWithClient(
      <AddLeadsDialog
        campaign={{ id: 7, niche_id: 3, name: "Spring outreach" }}
        open
        onOpenChange={() => {}}
      />,
    );

    const dialog = await screen.findByRole("dialog");
    await within(dialog).findByText("Ada Lovelace");
    expect(leadQuery!.get("niche_id")).toBe("3");
    expect(leadQuery!.get("has_email")).toBe("true");

    // Opted-out leads can't be picked.
    expect(within(dialog).getByRole("checkbox", { name: "Select Grace Hopper" })).toBeDisabled();

    const add = within(dialog).getByRole("button", { name: "Add leads" });
    expect(add).toBeDisabled();
    await user.click(within(dialog).getByRole("checkbox", { name: "Select all on this page" }));
    expect(within(dialog).getByText("2 selected")).toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: "Add 2 leads" }));

    expect(await within(dialog).findByText("Leads added to Spring outreach")).toBeInTheDocument();
    expect(submitted).toEqual({ lead_ids: [1, 2] });
    const items = within(within(dialog).getByRole("list", { name: "Results for each lead" })).getAllByRole(
      "listitem",
    );
    expect(items[0]).toHaveTextContent("Alan Turing");
    expect(items[0]).toHaveTextContent("Skipped · Already in this campaign");
    expect(items[1]).toHaveTextContent("Ada Lovelace");
    expect(within(dialog).getByRole("button", { name: "Add more leads" })).toBeInTheDocument();
  });
});
