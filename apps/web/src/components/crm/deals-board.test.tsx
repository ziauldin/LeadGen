import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { DealsBoard } from "@/components/crm/deals-board";
import { TasksList } from "@/components/crm/tasks-list";
import { renderWithClient } from "@/test/render";
import { server } from "@/test/server";

const url = (path: string) => `http://localhost:3000/api${path}`;
vi.mock("@/hooks/use-workspace", () => ({ useWorkspace: () => ({ can: () => true }) }));

const BOARD = {
  stages: [
    { id: 1, name: "Interested", kind: "open", probability: 10, position: 0, count: 1, value_cents: 250000 },
    { id: 2, name: "Proposal", kind: "open", probability: 60, position: 1, count: 0, value_cents: 0 },
    { id: 3, name: "Won", kind: "won", probability: 100, position: 2, count: 0, value_cents: 0 },
  ],
  deals: [
    {
      id: 7,
      title: "Jo Smith · Acme",
      lead_id: 4,
      lead_name: "Jo Smith",
      company_id: null,
      stage_id: 1,
      owner_id: 1,
      owner_name: "Sam",
      value_cents: 250000,
      currency: "USD",
      expected_close_date: null,
      source: "reply",
      closed_at: null,
      created_at: "2026-10-01T00:00:00Z",
      updated_at: "2026-10-01T00:00:00Z",
    },
  ],
  weighted_pipeline_cents: 25000,
};

describe("DealsBoard", () => {
  it("shows stages with totals and moves deals with the keyboard-friendly menu", async () => {
    const user = userEvent.setup();
    let moved: unknown = null;
    server.use(
      http.get(url("/deals/board"), () => HttpResponse.json(BOARD)),
      http.patch(url("/deals/7"), async ({ request }) => {
        moved = await request.json();
        return HttpResponse.json({ ...BOARD.deals[0], stage_id: 2 });
      }),
    );
    renderWithClient(<DealsBoard />);
    const interested = await screen.findByRole("region", { name: /Interested/ });
    expect(within(interested).getByText("Jo Smith · Acme")).toBeInTheDocument();
    expect(screen.getByText(/weighted pipeline \$250/)).toBeInTheDocument();
    expect(screen.getByText(/from a reply/)).toBeInTheDocument();

    await user.selectOptions(screen.getByRole("combobox", { name: "Stage for Jo Smith · Acme" }), "2");
    await waitFor(() => expect(moved).toEqual({ stage_id: 2 }));
  });
});

describe("TasksList", () => {
  it("adds and completes tasks", async () => {
    const user = userEvent.setup();
    const calls: { method: string; body: unknown }[] = [];
    server.use(
      http.get(url("/tasks"), () =>
        HttpResponse.json([
          { id: 1, title: "Call Jo", notes: null, due_at: "2026-01-01T09:00:00Z", done_at: null, assignee_id: 1, assignee_name: "Sam", lead_id: null, lead_name: null, deal_id: null, created_at: "2026-01-01T00:00:00Z" },
        ]),
      ),
      http.post(url("/tasks"), async ({ request }) => {
        calls.push({ method: "POST", body: await request.json() });
        return HttpResponse.json({}, { status: 201 });
      }),
      http.patch(url("/tasks/1"), async ({ request }) => {
        calls.push({ method: "PATCH", body: await request.json() });
        return HttpResponse.json({});
      }),
    );
    renderWithClient(<TasksList />);
    expect(await screen.findByText(/Overdue/)).toBeInTheDocument();
    await user.type(screen.getByLabelText("New task"), "Send proposal");
    await user.click(screen.getByRole("button", { name: "Add task" }));
    await user.click(screen.getByRole("checkbox", { name: /Mark "Call Jo" done/ }));
    await waitFor(() => expect(calls).toHaveLength(2));
    expect(calls[0]).toEqual({ method: "POST", body: { title: "Send proposal", due_at: null, lead_id: null } });
    expect(calls[1]).toEqual({ method: "PATCH", body: { done: true } });
  });
});
