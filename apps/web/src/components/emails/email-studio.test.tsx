import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { EmailStudio } from "@/components/emails/email-studio";
import { renderWithClient } from "@/test/render";
import { server } from "@/test/server";

const API = "http://localhost:3000/api";

let previews: Array<{ mode: string; template_id: string }>;

beforeEach(() => {
  previews = [];
  window.history.pushState({}, "", "/email-studio?lead_id=5");
  server.use(
    http.get(`${API}/leads/5`, () =>
      HttpResponse.json({
        id: 5,
        full_name: "Dana Reyes",
        job_title: "Practice Manager",
        company: { id: 1, name: "Northwind Clinic" },
        primary_email: "dana@northwind.test",
        score: 81,
        status: "ready_for_outreach",
      }),
    ),
    http.get(`${API}/templates`, () =>
      HttpResponse.json([
        { id: "system:intro", name: "Introduction", is_system: true, is_archived: false, description: "", subject: "", body: "" },
      ]),
    ),
    http.get(`${API}/campaigns`, () => HttpResponse.json({ items: [], total: 0, skip: 0, limit: 200 })),
    http.post(`${API}/emails/preview`, async ({ request }) => {
      const body = (await request.json()) as { mode: string; template_id: string };
      previews.push(body);
      if (body.mode === "ai") {
        return HttpResponse.json(
          { detail: "AI drafting is turned off for this workspace." },
          { status: 400 },
        );
      }
      return HttpResponse.json({
        lead_id: 5,
        template_id: body.template_id,
        recipient_email: "dana@northwind.test",
        subject: "Quick question about Northwind Clinic",
        body: "Hi Dana,\n\nTo opt out, use this link: https://x/unsubscribe/t",
        variables: {},
        has_opt_out_line: true,
        compliance_errors: [],
        can_send: true,
        generation_mode: "template",
        llm_model: null,
        generation_note: null,
      });
    }),
  );
});

afterEach(() => window.history.pushState({}, "", "/"));

describe("EmailStudio", () => {
  it("loads the lead from the URL and previews the template automatically", async () => {
    renderWithClient(<EmailStudio />);
    expect(await screen.findByText("Dana Reyes")).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "Quick question about Northwind Clinic" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Compliance checks passed/)).toBeInTheDocument();
    expect(previews).toEqual([expect.objectContaining({ mode: "template", template_id: "system:intro" })]);
  });

  it("only previews AI drafts on request and shows why AI is unavailable", async () => {
    const user = userEvent.setup();
    renderWithClient(<EmailStudio />);
    await screen.findByRole("heading", { name: "Quick question about Northwind Clinic" });

    await user.click(screen.getByRole("radio", { name: /Write with AI/ }));
    expect(screen.getByText(/A person still reviews and approves every email/)).toBeInTheDocument();
    expect(previews.filter((p) => p.mode === "ai")).toHaveLength(0);

    await user.click(screen.getByRole("button", { name: "Generate preview" }));
    expect(
      await screen.findByText("AI drafting is turned off for this workspace."),
    ).toBeInTheDocument();
    await waitFor(() => expect(previews.filter((p) => p.mode === "ai")).toHaveLength(1));
  });
});
