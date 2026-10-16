import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";
import {
  apiFetch,
  endImpersonation,
  getImpersonation,
  getWorkspaceId,
  refreshAccessToken,
  setWorkspaceId,
  startImpersonation,
} from "@/lib/api/client";
import { server } from "@/test/server";

const url = (path: string) => `http://localhost:3000/api${path}`;

const session = (minutes: number) => ({
  token: "imp-token",
  workspaceId: 42,
  workspaceName: "Acme",
  userName: "Jo",
  userEmail: "jo@acme.co.uk",
  readOnly: true,
  expiresAt: new Date(Date.now() + minutes * 60_000).toISOString(),
});

describe("impersonation sessions", () => {
  afterEach(() => {
    endImpersonation();
    window.localStorage.clear();
  });

  it("sends the impersonation token and workspace, and never uses the refresh cookie", async () => {
    let refreshCalls = 0;
    let seen: { auth: string | null; workspace: string | null } = { auth: null, workspace: null };
    server.use(
      http.post(url("/auth/refresh"), () => {
        refreshCalls += 1;
        return HttpResponse.json({ access_token: "admin-token" });
      }),
      http.get(url("/niches"), ({ request }) => {
        seen = { auth: request.headers.get("Authorization"), workspace: request.headers.get("X-Workspace-Id") };
        return HttpResponse.json({ items: [] });
      }),
    );
    setWorkspaceId(7);
    startImpersonation(session(30));

    expect(await refreshAccessToken()).toBe("imp-token");
    await apiFetch("/niches");
    expect(seen).toEqual({ auth: "Bearer imp-token", workspace: "42" });
    expect(refreshCalls).toBe(0);

    // The admin's own workspace choice in other tabs is left alone.
    setWorkspaceId(99);
    expect(window.localStorage.getItem("lg_workspace")).toBe("7");
  });

  it("expires on its own and falls back to the admin's workspace", () => {
    setWorkspaceId(7);
    startImpersonation(session(-1));
    expect(getImpersonation()).toBeNull();
    expect(getWorkspaceId()).toBe("7");
  });
});
