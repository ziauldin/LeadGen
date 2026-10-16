import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { IntegrationsSettings } from "@/components/settings/integrations-settings";
import { renderWithClient } from "@/test/render";
import { server } from "@/test/server";
import type { components } from "@/lib/api/schema";

const url = (path: string) => `http://localhost:3000/api${path}`;
vi.mock("@/hooks/use-workspace", () => ({ useWorkspace: () => ({ can: () => true }) }));

const PROVIDERS = [
  { key: "hubspot", label: "HubSpot", auth: "oauth", available: true },
  { key: "pipedrive", label: "Pipedrive", auth: "token", available: true },
];
const PIPEDRIVE: components["schemas"]["IntegrationConnectionRead"] = {
  id: 4,
  provider: "pipedrive",
  label: "Pipedrive",
  status: "error",
  account_label: "Acme Ltd",
  settings: { push_contacts: true, push_deals: true, pull_status: true },
  last_synced_at: null,
  last_error: "Pipedrive deal: access was refused. Reconnect the account.",
  created_at: "2026-10-01T00:00:00Z",
};

describe("IntegrationsSettings", () => {
  it("connects Pipedrive with a token and starts HubSpot OAuth", async () => {
    const user = userEvent.setup();
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign, search: "" });
    let connections: (typeof PIPEDRIVE)[] = [];
    let sent: unknown = null;
    server.use(
      http.get(url("/integrations"), () => HttpResponse.json({ enabled: true, in_plan: true, providers: PROVIDERS, connections })),
      http.post(url("/integrations/pipedrive"), async ({ request }) => {
        sent = await request.json();
        connections = [{ ...PIPEDRIVE, status: "active", last_error: null }];
        return HttpResponse.json(connections[0], { status: 201 });
      }),
      http.post(url("/integrations/hubspot/connect"), () => HttpResponse.json({ url: "https://app.hubspot.com/oauth/authorize?x=1" })),
    );
    renderWithClient(<IntegrationsSettings />);
    await user.type(await screen.findByLabelText("Company domain"), "acme");
    await user.type(screen.getByLabelText("API token"), "pd-token-0123456789");
    await user.click(screen.getByRole("button", { name: "Connect Pipedrive" }));
    await waitFor(() => expect(sent).toEqual({ api_token: "pd-token-0123456789", company_domain: "acme" }));
    expect(await screen.findByText("Acme Ltd")).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: /Send deals/ })).toBeChecked();

    await user.click(screen.getByRole("button", { name: "Connect HubSpot" }));
    await waitFor(() => expect(assign).toHaveBeenCalledWith("https://app.hubspot.com/oauth/authorize?x=1"));
    vi.unstubAllGlobals();
  });

  it("explains a broken connection and toggles settings", async () => {
    const user = userEvent.setup();
    let patched: unknown = null;
    server.use(
      http.get(url("/integrations"), () => HttpResponse.json({ enabled: true, in_plan: true, providers: PROVIDERS, connections: [PIPEDRIVE] })),
      http.patch(url("/integrations/4"), async ({ request }) => {
        patched = await request.json();
        return HttpResponse.json(PIPEDRIVE);
      }),
    );
    renderWithClient(<IntegrationsSettings />);
    expect(await screen.findByRole("alert")).toHaveTextContent("access was refused");
    expect(screen.getByRole("button", { name: "Sync now" })).toBeDisabled();
    await user.click(screen.getByRole("switch", { name: /Bring back won and lost/ }));
    await waitFor(() => expect(patched).toEqual({ pull_status: false }));
  });

  it("shows the upgrade note outside the plan", async () => {
    server.use(
      http.get(url("/integrations"), () => HttpResponse.json({ enabled: true, in_plan: false, providers: PROVIDERS, connections: [] })),
    );
    renderWithClient(<IntegrationsSettings />);
    expect(await screen.findByText(/part of the Pro and Enterprise plans/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Connect Pipedrive" })).not.toBeInTheDocument();
  });
});
