import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PrivacySettings } from "@/components/settings/privacy-settings";
import { renderWithClient } from "@/test/render";
import { server } from "@/test/server";

const url = (path: string) => `http://localhost:3000/api${path}`;

let granted = new Set<string>();
vi.mock("@/hooks/use-workspace", () => ({
  useWorkspace: () => ({ can: (p: string) => granted.has(p), permissionsLoading: false }),
}));

const SETTINGS = { require_lia_note: false, retention_uncontacted_lead_days: null, retention_reply_days: null };

function mockApi(items: unknown[] = []) {
  server.use(
    http.get(url("/privacy/requests"), () => HttpResponse.json({ items, total: items.length, skip: 0, limit: 50 })),
    http.get(url("/privacy/settings"), () => HttpResponse.json(SETTINGS)),
  );
}

describe("PrivacySettings", () => {
  beforeEach(() => {
    granted = new Set(["privacy.manage", "data.export"]);
  });

  it("asks for confirmation before erasing someone", async () => {
    const user = userEvent.setup();
    const bodies: unknown[] = [];
    mockApi();
    server.use(
      http.post(url("/privacy/requests"), async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        bodies.push(body);
        return HttpResponse.json(
          {
            id: 1,
            kind: body.kind,
            status: "pending",
            subject_email: null,
            requested_by: "Sam",
            note: null,
            created_at: "2026-10-01T00:00:00Z",
            completed_at: null,
            expires_at: null,
            downloadable: false,
            summary: null,
            error: null,
          },
          { status: 201 },
        );
      }),
    );
    renderWithClient(<PrivacySettings />);

    const erase = await screen.findByRole("button", { name: /Erase this person/ });
    expect(erase).toBeDisabled();
    await user.type(screen.getByLabelText("Person's email address"), "alex@acme.co.uk");
    await user.click(erase);
    const dialog = await screen.findByRole("dialog", { name: "Erase alex@acme.co.uk?" });
    expect(within(dialog).getByText(/can't be undone/)).toBeInTheDocument();
    expect(bodies).toHaveLength(0);
    await user.click(within(dialog).getByRole("button", { name: "Erase permanently" }));
    await waitFor(() => expect(bodies).toEqual([{ kind: "erase", email: "alex@acme.co.uk", note: null }]));
  });

  it("shows erased people only as a hash and offers downloads", async () => {
    mockApi([
      {
        id: 2,
        kind: "erase",
        status: "completed",
        subject_email: null,
        requested_by: "Sam",
        note: "Asked by email",
        created_at: "2026-10-01T00:00:00Z",
        completed_at: "2026-10-01T00:00:05Z",
        expires_at: null,
        downloadable: false,
        summary: { leads: 1, replies: 2, contacts: 0 },
        error: null,
      },
      {
        id: 3,
        kind: "workspace_export",
        status: "completed",
        subject_email: null,
        requested_by: "Sam",
        note: null,
        created_at: "2026-10-02T00:00:00Z",
        completed_at: "2026-10-02T00:00:05Z",
        expires_at: "2026-10-09T00:00:00Z",
        downloadable: true,
        summary: { leads: 10 },
        error: null,
      },
    ]);
    renderWithClient(<PrivacySettings />);
    expect(await screen.findByText(/Erased person \(kept only as a hash\)/)).toBeInTheDocument();
    expect(screen.getByText("1 leads, 2 replies")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Download/ })).toHaveLength(1);
  });

  it("members can export the workspace but not handle requests", async () => {
    granted = new Set(["data.export"]);
    mockApi();
    renderWithClient(<PrivacySettings />);
    expect(await screen.findByRole("button", { name: /Export workspace/ })).toBeInTheDocument();
    expect(screen.queryByLabelText("Person's email address")).not.toBeInTheDocument();
    expect(screen.getByText(/export or erase a person's data/)).toBeInTheDocument();
    expect(await screen.findByRole("checkbox", { name: /legitimate-interest note/ })).toBeDisabled();
  });
});
