import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DeveloperSettings } from "@/components/settings/developer-settings";
import { renderWithClient } from "@/test/render";
import { server } from "@/test/server";

const url = (path: string) => `http://localhost:3000/api${path}`;

let granted = new Set<string>();
vi.mock("@/hooks/use-workspace", () => ({
  useWorkspace: () => ({ can: (p: string) => granted.has(p), permissionsLoading: false }),
}));

const OPTIONS = {
  enabled: true,
  scopes: [
    { key: "leads:read", description: "Read leads and companies" },
    { key: "leads:write", description: "Create and update leads" },
  ],
  events: [
    { key: "reply.received", description: "Someone replied" },
    { key: "lead.created", description: "A lead was added" },
  ],
};

function mockApi({ plan = "pro", enabled = true } = {}) {
  server.use(
    http.get(url("/developer/options"), () => HttpResponse.json({ ...OPTIONS, enabled })),
    http.get(url("/billing"), () => HttpResponse.json({ plan, features: { api_access: plan !== "free" } })),
    http.get(url("/api-keys"), () => HttpResponse.json([])),
    http.get(url("/webhook-endpoints"), () => HttpResponse.json([])),
  );
}

describe("DeveloperSettings", () => {
  beforeEach(() => {
    granted = new Set(["api_keys.manage"]);
  });

  it("shows a new key exactly once", async () => {
    const user = userEvent.setup();
    let body: unknown = null;
    mockApi();
    server.use(
      http.post(url("/api-keys"), async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(
          {
            id: 1,
            name: "Zapier",
            prefix: "lg_live_abcd1234",
            scopes: ["leads:read", "leads:write"],
            created_by: "Sam",
            created_at: "2026-10-01T00:00:00Z",
            last_used_at: null,
            expires_at: null,
            revoked_at: null,
            key: "lg_live_abcd1234-the-full-secret",
          },
          { status: 201 },
        );
      }),
    );
    renderWithClient(<DeveloperSettings />);

    await user.click(await screen.findByRole("button", { name: /New key/ }));
    const dialog = await screen.findByRole("dialog", { name: "New API key" });
    await user.type(within(dialog).getByLabelText("Name"), "Zapier");
    await user.click(within(dialog).getByRole("checkbox", { name: /leads:write/ }));
    await user.click(within(dialog).getByRole("button", { name: "Create key" }));

    await waitFor(() =>
      expect(body).toEqual({ name: "Zapier", scopes: ["leads:read", "leads:write"], expires_in_days: null }),
    );
    const reveal = await screen.findByRole("dialog", { name: "Your new API key" });
    expect(within(reveal).getByText("lg_live_abcd1234-the-full-secret")).toBeInTheDocument();
    await user.click(within(reveal).getByRole("button", { name: "Done" }));
    await waitFor(() => expect(screen.queryByText("lg_live_abcd1234-the-full-secret")).not.toBeInTheDocument());
  });

  it("explains plan and permission limits", async () => {
    mockApi({ plan: "free" });
    const { unmount } = renderWithClient(<DeveloperSettings />);
    expect(await screen.findByText(/included on the Starter plan/)).toBeInTheDocument();
    unmount();

    granted = new Set();
    mockApi();
    renderWithClient(<DeveloperSettings />);
    expect(await screen.findByText(/create API keys or webhooks/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /New key/ })).not.toBeInTheDocument();
  });

  it("says when the API is switched off", async () => {
    mockApi({ enabled: false });
    renderWithClient(<DeveloperSettings />);
    expect(await screen.findByText(/isn't turned on for this installation/)).toBeInTheDocument();
  });
});
