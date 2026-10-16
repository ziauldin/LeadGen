import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HelpMenu, unseenCount } from "@/components/layout/help-menu";
import { CHANGELOG } from "@/content/changelog";
import { renderWithClient } from "@/test/render";
import { server } from "@/test/server";

vi.mock("next/navigation", () => ({ usePathname: () => "/leads" }));

const url = (path: string) => `http://localhost:3000/api${path}`;

describe("HelpMenu", () => {
  afterEach(() => window.localStorage.clear());

  it("counts changelog entries newer than the last one seen", () => {
    expect(unseenCount(null)).toBe(Math.min(CHANGELOG.length, 3));
    expect(unseenCount(CHANGELOG[0].id)).toBe(0);
    expect(unseenCount(CHANGELOG[1].id)).toBe(1);
    expect(unseenCount("gone")).toBe(CHANGELOG.length);
  });

  it("marks what's new as seen once opened", async () => {
    const user = userEvent.setup();
    renderWithClient(<HelpMenu />);
    await user.click(await screen.findByRole("button", { name: /new\)/ }));
    await user.click(await screen.findByRole("menuitem", { name: /What.s new/ }));
    expect(await screen.findByRole("dialog", { name: "What's new" })).toBeInTheDocument();
    expect(screen.getByText(CHANGELOG[0].title)).toBeInTheDocument();
    expect(window.localStorage.getItem("lg_changelog_seen")).toBe(CHANGELOG[0].id);
  });

  it("sends feedback with the current page", async () => {
    const user = userEvent.setup();
    let body: unknown = null;
    server.use(
      http.post(url("/feedback"), async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ message: "Thanks" });
      }),
    );
    renderWithClient(<HelpMenu />);
    await user.click(await screen.findByRole("button", { name: /Help and what's new/ }));
    await user.click(await screen.findByRole("menuitem", { name: /Send feedback/ }));
    await user.click(await screen.findByLabelText("Something's broken"));
    await user.type(screen.getByLabelText("Your feedback"), "Export does nothing");
    await user.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(body).toEqual({ kind: "bug", message: "Export does nothing", page: "/leads" }));
  });
});
