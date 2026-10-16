import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { NotificationBell } from "@/components/layout/notification-bell";
import { renderWithClient } from "@/test/render";
import { server } from "@/test/server";

const url = (path: string) => `http://localhost:3000/api${path}`;
const ITEMS = [
  { id: 2, kind: "positive_reply", title: "Jo replied with interest", body: "Sounds good", link: "/replies?reply=4", read: false, created_at: new Date().toISOString() },
  { id: 1, kind: "member_joined", title: "Sam joined the workspace", body: null, link: null, read: true, created_at: "2026-10-01T00:00:00Z" },
];

describe("NotificationBell", () => {
  it("shows the unread count and marks everything read", async () => {
    const user = userEvent.setup();
    let unread = 1;
    let marked: unknown = null;
    server.use(
      http.get(url("/notifications"), () =>
        HttpResponse.json({ items: ITEMS.map((n) => ({ ...n, read: unread === 0 || n.read })), unread }),
      ),
      http.post(url("/notifications/read"), async ({ request }) => {
        marked = await request.json();
        unread = 0;
        return HttpResponse.json({ message: "ok" });
      }),
    );
    renderWithClient(<NotificationBell />);
    await user.click(await screen.findByRole("button", { name: "Notifications (1 unread)" }));
    expect(await screen.findByText("Jo replied with interest")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Jo replied/ })).toHaveAttribute("href", "/replies?reply=4");
    await user.click(screen.getByRole("button", { name: "Mark all as read" }));
    await waitFor(() => expect(marked).toEqual({ all: true }));
    expect(await screen.findByRole("button", { name: "Notifications" })).toBeInTheDocument();
  });

  it("says when there's nothing new", async () => {
    const user = userEvent.setup();
    server.use(http.get(url("/notifications"), () => HttpResponse.json({ items: [], unread: 0 })));
    renderWithClient(<NotificationBell />);
    await user.click(await screen.findByRole("button", { name: "Notifications" }));
    expect(await screen.findByText(/all caught up/)).toBeInTheDocument();
  });
});
