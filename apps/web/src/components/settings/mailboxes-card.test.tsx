import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { CampaignSendersCard } from "@/components/campaigns/campaign-senders-card";
import { MailboxesCard } from "@/components/settings/mailboxes-card";
import { renderWithClient } from "@/test/render";
import { server } from "@/test/server";

const url = (path: string) => `http://localhost:3000/api${path}`;

vi.mock("@/hooks/use-workspace", () => ({ useWorkspace: () => ({ can: () => true }) }));

const ACCOUNTS = [
  { id: 1, provider: "gmail", label: "Gmail: sam@acme.co.uk", email: "sam@acme.co.uk", daily_limit: 50, cap_today: 15, healthy: true, problem: null, is_mailbox: true },
  {
    id: 2,
    provider: "outlook",
    label: "Microsoft 365: jo@acme.co.uk",
    email: "jo@acme.co.uk",
    daily_limit: 50,
    cap_today: 50,
    healthy: false,
    problem: "Reconnect needed: token revoked",
    is_mailbox: true,
  },
];

function mockApi() {
  server.use(
    http.get(url("/mailboxes/providers"), () =>
      HttpResponse.json([
        { key: "gmail", label: "Gmail", available: true },
        { key: "outlook", label: "Microsoft 365", available: true },
      ]),
    ),
    http.get(url("/sending-accounts"), () => HttpResponse.json(ACCOUNTS)),
  );
}

describe("MailboxesCard", () => {
  it("lists mailboxes with health and starts OAuth", async () => {
    const user = userEvent.setup();
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign, search: "" });
    mockApi();
    server.use(http.post(url("/mailboxes/gmail/connect"), () => HttpResponse.json({ url: "https://accounts.google.com/o/oauth2/v2/auth?x=1" })));
    renderWithClient(<MailboxesCard />);
    expect(await screen.findByText("sam@acme.co.uk")).toBeInTheDocument();
    expect(screen.getByText("Gmail · up to 15 emails today")).toBeInTheDocument();
    expect(screen.getByText("Reconnect needed: token revoked")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reconnect" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Connect Gmail/ }));
    await waitFor(() => expect(assign).toHaveBeenCalledWith("https://accounts.google.com/o/oauth2/v2/auth?x=1"));
    vi.unstubAllGlobals();
  });
});

describe("CampaignSendersCard", () => {
  it("saves the rotation pool", async () => {
    const user = userEvent.setup();
    let saved: unknown = null;
    mockApi();
    server.use(
      http.get(url("/campaigns/9/senders"), () => HttpResponse.json([ACCOUNTS[0]])),
      http.put(url("/campaigns/9/senders"), async ({ request }) => {
        saved = await request.json();
        return HttpResponse.json(ACCOUNTS);
      }),
    );
    renderWithClient(<CampaignSendersCard campaignId={9} />);
    const outlook = await screen.findByRole("checkbox", { name: /jo@acme.co.uk/ });
    expect(screen.getByRole("checkbox", { name: /sam@acme.co.uk/ })).toBeChecked();
    expect(screen.getByRole("button", { name: "Save sending accounts" })).toBeDisabled();
    await user.click(outlook);
    await user.click(screen.getByRole("button", { name: "Save sending accounts" }));
    await waitFor(() => expect(saved).toEqual({ credential_ids: [1, 2] }));
  });
});
