import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { server } from "@/test/server";
import {
  ApiError,
  apiFetch,
  errorMessage,
  setAccessToken,
  setSessionExpiredHandler,
  setWorkspaceId,
} from "@/lib/api/client";

const url = (path: string) => `http://localhost:3000/api${path}`;

describe("apiFetch", () => {
  it("refreshes once on 401 and retries with the new token", async () => {
    setAccessToken("expired");
    let refreshCalls = 0;
    const seen: string[] = [];
    server.use(
      http.post(url("/auth/refresh"), ({ request }) => {
        refreshCalls += 1;
        expect(request.headers.get("X-Requested-With")).toBe("fetch");
        return HttpResponse.json({ access_token: "fresh" });
      }),
      http.get(url("/leads"), ({ request }) => {
        const auth = request.headers.get("Authorization") ?? "";
        seen.push(auth);
        if (auth !== "Bearer fresh") return new HttpResponse(null, { status: 401 });
        return HttpResponse.json({ items: [], total: 0, skip: 0, limit: 50 });
      }),
    );

    const [a, b] = await Promise.all([apiFetch("/leads"), apiFetch("/leads")]);
    expect(a).toEqual({ items: [], total: 0, skip: 0, limit: 50 });
    expect(b).toEqual(a);
    expect(refreshCalls).toBe(1);
    expect(seen.filter((value) => value === "Bearer fresh")).toHaveLength(2);
  });

  it("calls the session-expired handler when refresh fails", async () => {
    setAccessToken(null);
    const expired = vi.fn();
    setSessionExpiredHandler(expired);
    server.use(
      http.post(url("/auth/refresh"), () => new HttpResponse(null, { status: 401 })),
      http.get(url("/auth/me"), () => new HttpResponse(null, { status: 401 })),
    );
    await expect(apiFetch("/auth/me")).rejects.toBeInstanceOf(ApiError);
    expect(expired).toHaveBeenCalledOnce();
    setSessionExpiredHandler(null);
  });

  it("sends the current workspace and surfaces API error details", async () => {
    setAccessToken("token");
    setWorkspaceId(42);
    server.use(
      http.post(url("/campaigns"), ({ request }) => {
        expect(request.headers.get("X-Workspace-Id")).toBe("42");
        return HttpResponse.json(
          { detail: "You've reached your plan's limit", code: "quota_exceeded" },
          { status: 402 },
        );
      }),
    );
    const error = (await apiFetch("/campaigns", { method: "POST", body: "{}" }).catch(
      (e: unknown) => e,
    )) as ApiError;
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(402);
    expect(error.message).toBe("You've reached your plan's limit");
  });
});

describe("errorMessage", () => {
  it("flattens FastAPI validation errors", () => {
    const detail = {
      detail: [
        { loc: ["body", "steps", 0], msg: "Value error, Give a template_id" },
        { loc: ["body", "name"], msg: "Field required" },
      ],
    };
    expect(errorMessage(detail, 422)).toBe("steps.0: Give a template_id; name: Field required");
  });

  it("falls back to friendly text by status", () => {
    expect(errorMessage(undefined, 429)).toMatch(/Too many requests/);
    expect(errorMessage("<html>oops</html>".repeat(40), 500)).toMatch(/Something went wrong/);
  });
});
