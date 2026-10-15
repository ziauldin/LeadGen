import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { ReplyLinkPanel } from "@/components/replies/reply-link-panel";
import { ReplyTriagePanel } from "@/components/replies/reply-triage-panel";
import type { ReplyDetail } from "@/lib/api/types";
import { renderWithClient } from "@/test/render";
import { server } from "@/test/server";

const url = (path: string) => `http://localhost:3000/api${path}`;

const reply: ReplyDetail = {
  id: 7,
  email_message_id: null,
  from_email: "sam@acme.com",
  subject: "Re: Quick question",
  body: "Sounds interesting, tell me more.",
  raw_body: null,
  snippet: "Sounds interesting, tell me more.",
  classification: "unknown",
  classified_by: null,
  classification_confidence: null,
  is_auto_reply: false,
  match_method: "unmatched",
  received_at: "2026-10-10T09:00:00Z",
  lead_id: null,
  lead_name: null,
  campaign_id: null,
  notes: null,
  in_reply_to: null,
  thread: [],
};

const message = (id: number, recipient: string, subject: string) => ({
  id,
  lead_id: id * 10,
  lead_name: null,
  recipient_email: recipient,
  subject,
  status: "sent",
  step_number: 1,
  sent_at: "2026-10-01T10:00:00Z",
  scheduled_for: null,
  failure_reason: null,
  generation_mode: "template",
  reply_status: null,
});

describe("ReplyLinkPanel", () => {
  it("lists sent emails to the sender's domain first and links the chosen one", async () => {
    const user = userEvent.setup();
    let linkBody: unknown;
    let messagesQuery = "";
    server.use(
      http.get(url("/campaigns"), () =>
        HttpResponse.json({
          items: [{ id: 3, name: "UK dentists" }],
          total: 1,
          skip: 0,
          limit: 200,
        }),
      ),
      http.get(url("/campaigns/3/messages"), ({ request }) => {
        messagesQuery = new URL(request.url).search;
        return HttpResponse.json({
          items: [
            message(11, "sam@acme.com", "Quick question"),
            message(12, "lee@other.io", "Hello Lee"),
          ],
          total: 2,
          skip: 0,
          limit: 50,
        });
      }),
      http.post(url("/replies/7/link"), async ({ request }) => {
        linkBody = await request.json();
        return HttpResponse.json({ ...reply, email_message_id: 11 });
      }),
    );

    renderWithClient(<ReplyLinkPanel reply={reply} />);

    const linkButton = screen.getByRole("button", { name: /Link reply/ });
    expect(linkButton).toBeDisabled();

    await user.click(await screen.findByRole("combobox", { name: "Campaign" }));
    await user.click(await screen.findByRole("option", { name: "UK dentists" }));

    const group = await screen.findByRole("group", { name: /Which email is this a reply to/ });
    expect(messagesQuery).toContain("status=sent");
    expect(messagesQuery).toContain("limit=50");
    // Only the same-domain email is shown at first.
    expect(within(group).getAllByRole("radio")).toHaveLength(1);
    await user.click(within(group).getByLabelText(/Only show recipients at @acme.com/));
    expect(within(group).getAllByRole("radio")).toHaveLength(2);

    await user.click(within(group).getByRole("radio", { name: /sam@acme.com/ }));
    await user.click(linkButton);

    await waitFor(() => expect(linkBody).toEqual({ email_message_id: 11 }));
  });
});

describe("ReplyTriagePanel", () => {
  it("updates the label", async () => {
    const user = userEvent.setup();
    let patchBody: unknown;
    server.use(
      http.patch(url("/replies/7"), async ({ request }) => {
        patchBody = await request.json();
        return HttpResponse.json({ ...reply, classification: "positive", classified_by: "user" });
      }),
    );
    renderWithClient(<ReplyTriagePanel reply={{ ...reply, email_message_id: 11, lead_id: 110 }} />);

    await user.click(screen.getByRole("combobox", { name: "Reply label" }));
    await user.click(await screen.findByRole("option", { name: "Positive" }));

    await waitFor(() => expect(patchBody).toEqual({ classification: "positive" }));
  });
});
