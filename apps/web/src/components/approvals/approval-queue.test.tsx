import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApprovalQueueView } from "@/components/approvals/approval-queue";
import type { ApprovalItem } from "@/lib/api/types";
import { renderWithClient } from "@/test/render";
import { server } from "@/test/server";

const auth = { isVerified: true };
vi.mock("@/hooks/use-auth", () => ({ useAuth: () => auth }));

const API = "http://localhost:3000/api";

function draft(id: number, overrides: Partial<ApprovalItem> = {}): ApprovalItem {
  return {
    id,
    status: "pending_approval",
    recipient_email: `lead${id}@example.com`,
    subject: `Subject ${id}`,
    body: `Hi there,\n\nBody ${id}\n\nTo opt out, use this link: https://x/unsubscribe/t`,
    step_number: 1,
    scheduled_for: null,
    created_at: "2026-10-01T10:00:00Z",
    campaign_id: 7,
    campaign_name: "Q4 outreach",
    lead: {
      id: 100 + id,
      full_name: `Lead ${id}`,
      job_title: "Head of Ops",
      company_name: `Company ${id}`,
      company_domain: `company${id}.com`,
      score: 72,
      status: "ready_for_outreach",
    },
    generation_mode: "template",
    generation_note: null,
    llm_model: null,
    template_id: "system:intro",
    edited_at: null,
    problems: [],
    can_approve: true,
    ...overrides,
  };
}

let queue: ApprovalItem[];
let approved: number[];

beforeEach(() => {
  auth.isVerified = true;
  approved = [];
  queue = [draft(1), draft(2), draft(3)];
  server.use(
    http.get(`${API}/approvals`, () =>
      HttpResponse.json({
        items: queue,
        total: queue.length,
        skip: 0,
        limit: 50,
        by_campaign: { "7": queue.length },
      }),
    ),
    http.get(`${API}/campaigns`, () =>
      HttpResponse.json({
        items: [{ id: 7, name: "Q4 outreach" }],
        total: 1,
        skip: 0,
        limit: 200,
      }),
    ),
    http.post(`${API}/emails/:id/approve`, ({ params }) => {
      const id = Number(params.id);
      approved.push(id);
      const item = queue.find((entry) => entry.id === id)!;
      queue = queue.filter((entry) => entry.id !== id);
      return HttpResponse.json({ ...item, status: "approved" });
    }),
  );
});

async function renderQueue() {
  renderWithClient(<ApprovalQueueView />);
  await screen.findByRole("heading", { name: "Subject 1" });
}

const detail = () => screen.getByRole("region", { name: "Selected draft" });

describe("Approval queue", () => {
  it("selects the first draft and moves with j and k", async () => {
    const user = userEvent.setup();
    await renderQueue();
    expect(within(detail()).getByText("Draft 1 of 3")).toBeInTheDocument();

    await user.keyboard("j");
    expect(screen.getByRole("heading", { name: "Subject 2" })).toBeInTheDocument();
    await user.keyboard("j");
    expect(screen.getByRole("heading", { name: "Subject 3" })).toBeInTheDocument();
    await user.keyboard("j"); // already at the end
    expect(screen.getByRole("heading", { name: "Subject 3" })).toBeInTheDocument();
    await user.keyboard("k");
    expect(screen.getByRole("heading", { name: "Subject 2" })).toBeInTheDocument();
  });

  it("approves with a and moves on to the next draft", async () => {
    const user = userEvent.setup();
    await renderQueue();
    await user.keyboard("j"); // Subject 2
    await user.keyboard("a");

    await waitFor(() => expect(approved).toEqual([2]));
    expect(await screen.findByRole("heading", { name: "Subject 3" })).toBeInTheDocument();
    await waitFor(() => expect(within(detail()).getByText("Draft 2 of 2")).toBeInTheDocument());
  });

  it("approves the last draft with the button and falls back to the previous one", async () => {
    const user = userEvent.setup();
    await renderQueue();
    await user.keyboard("jj");
    await user.click(within(detail()).getByRole("button", { name: /Approve & next/ }));

    await waitFor(() => expect(approved).toEqual([3]));
    expect(await screen.findByRole("heading", { name: "Subject 2" })).toBeInTheDocument();
  });

  it("does not fire shortcuts while typing in the editor", async () => {
    const user = userEvent.setup();
    await renderQueue();
    await user.keyboard("e");
    const body = await screen.findByLabelText("Body");
    await user.click(body);
    await user.keyboard("ajk");
    expect(approved).toEqual([]);
    expect((body as HTMLTextAreaElement).value).toMatch(/ajk$/);
    expect(screen.queryByRole("heading", { name: "Subject 2" })).not.toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(screen.queryByLabelText("Body")).not.toBeInTheDocument();
    await user.keyboard("j");
    expect(screen.getByRole("heading", { name: "Subject 2" })).toBeInTheDocument();
  });

  it("opens the help dialog with ? and ignores shortcuts while it is open", async () => {
    const user = userEvent.setup();
    await renderQueue();
    await user.keyboard("?");
    expect(await screen.findByRole("dialog", { name: "Keyboard shortcuts" })).toBeInTheDocument();
    await user.keyboard("j");
    expect(screen.getByRole("heading", { name: "Subject 1", hidden: true })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Subject 2", hidden: true })).toBeNull();
  });

  it("opens the reject dialog with r", async () => {
    const user = userEvent.setup();
    await renderQueue();
    await user.keyboard("r");
    expect(await screen.findByRole("dialog", { name: "Reject this draft?" })).toBeInTheDocument();
    expect(screen.getByLabelText(/Reason/)).toBeInTheDocument();
  });

  it("blocks approval for unverified users", async () => {
    auth.isVerified = false;
    const user = userEvent.setup();
    await renderQueue();
    expect(within(detail()).getByRole("button", { name: /Approve & next/ })).toBeDisabled();
    expect(within(detail()).getByText(/Confirm your email address to approve/)).toBeInTheDocument();
    await user.keyboard("a");
    expect(approved).toEqual([]);
  });

  it("shows problems and blocks approval when compliance checks fail", async () => {
    queue = [draft(1, { problems: ["Lead has no source note"], can_approve: false })];
    const user = userEvent.setup();
    await renderQueue();
    expect(within(detail()).getByText("Lead has no source note")).toBeInTheDocument();
    expect(within(detail()).getByRole("button", { name: /Approve & next/ })).toBeDisabled();
    await user.keyboard("a");
    expect(approved).toEqual([]);
  });

  it("shows the empty state when nothing is waiting", async () => {
    queue = [];
    renderWithClient(<ApprovalQueueView />);
    expect(await screen.findByText("Nothing waiting for review")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to campaigns" })).toHaveAttribute(
      "href",
      "/campaigns",
    );
  });
});
