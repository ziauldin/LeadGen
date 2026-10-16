import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RolesSettings } from "@/components/settings/roles-settings";
import { renderWithClient } from "@/test/render";
import { server } from "@/test/server";

const url = (path: string) => `http://localhost:3000/api${path}`;

let granted = new Set<string>();
vi.mock("@/hooks/use-workspace", () => ({
  useWorkspace: () => ({ can: (permission: string) => granted.has(permission) }),
}));

const catalog = [
  { key: "leads.write", description: "Add, import, edit and enrich leads and companies" },
  { key: "members.manage", description: "Invite people and change roles" },
  { key: "billing.manage", description: "Manage the plan and billing" },
];
const builtIn = [
  { id: null, name: "Owner", description: null, permissions: catalog.map((p) => p.key), built_in: true, member_count: 0 },
  { id: null, name: "Member", description: null, permissions: ["leads.write"], built_in: true, member_count: 0 },
];

function mockApi(plan: string, custom: unknown[] = []) {
  server.use(
    http.get(url("/billing"), () =>
      HttpResponse.json({ plan, features: { custom_roles: plan === "enterprise" } }),
    ),
    http.get(url("/roles"), () => HttpResponse.json([...builtIn, ...custom])),
    http.get(url("/roles/permissions"), () => HttpResponse.json(catalog)),
  );
}

describe("RolesSettings", () => {
  beforeEach(() => {
    granted = new Set(["leads.write", "members.manage"]);
  });

  it("explains that custom roles need the Enterprise plan", async () => {
    mockApi("pro");
    renderWithClient(<RolesSettings />);
    expect(await screen.findByText(/included on the Enterprise plan/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /New role/ })).not.toBeInTheDocument();
    expect(screen.getByText("Owner")).toBeInTheDocument();
  });

  it("creates a role with only the permissions the admin holds", async () => {
    const user = userEvent.setup();
    let body: unknown = null;
    mockApi("enterprise");
    server.use(
      http.post(url("/roles"), async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(
          { id: 7, name: "Researcher", description: null, permissions: ["leads.write"], built_in: false, member_count: 0 },
          { status: 201 },
        );
      }),
    );
    renderWithClient(<RolesSettings />);

    await user.click(await screen.findByRole("button", { name: /New role/ }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Name"), "Researcher");
    // Billing isn't held by this admin, so it can't be granted.
    expect(within(dialog).getByRole("checkbox", { name: /Manage the plan and billing/ })).toBeDisabled();
    await user.click(within(dialog).getByRole("checkbox", { name: /Add, import, edit/ }));
    await user.click(within(dialog).getByRole("button", { name: "Create role" }));

    await waitFor(() =>
      expect(body).toEqual({ name: "Researcher", description: null, permissions: ["leads.write"] }),
    );
  });

  it("hides editing for people who can't manage members", async () => {
    granted = new Set(["leads.write"]);
    mockApi("enterprise", [
      { id: 3, name: "Viewer", description: "Read only", permissions: [], built_in: false, member_count: 2 },
    ]);
    renderWithClient(<RolesSettings />);
    expect(await screen.findByText("Viewer")).toBeInTheDocument();
    expect(screen.getByText("2 members")).toBeInTheDocument();
    expect(screen.getAllByText("View only. No changes allowed.").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Edit Viewer" })).not.toBeInTheDocument();
    expect(screen.getByText(/create or change roles/)).toBeInTheDocument();
  });
});
