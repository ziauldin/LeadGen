import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { VerificationBadge } from "@/components/leads/verification-badge";
import { VerificationSettingsCard } from "@/components/settings/verification-settings-card";
import { renderWithClient } from "@/test/render";
import { server } from "@/test/server";

const url = (path: string) => `http://localhost:3000/api${path}`;
vi.mock("@/hooks/use-workspace", () => ({ useWorkspace: () => ({ can: () => true }) }));

describe("verification", () => {
  it("labels each status", () => {
    const { rerender } = render(<VerificationBadge status="invalid" detail="Mailbox doesn't exist" />);
    expect(screen.getByText("Invalid")).toHaveAttribute("title", "Mailbox doesn't exist");
    rerender(<VerificationBadge status="valid" />);
    expect(screen.getByText("Verified")).toBeInTheDocument();
    rerender(<VerificationBadge status={null} />);
    expect(screen.queryByText("Verified")).not.toBeInTheDocument();
  });

  it("saves the risky-address policy", async () => {
    const user = userEvent.setup();
    let body: unknown = null;
    server.use(
      http.get(url("/settings"), () => HttpResponse.json({ ai_mode: "off", block_risky_emails: false })),
      http.patch(url("/settings"), async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ ai_mode: "off", block_risky_emails: true });
      }),
    );
    renderWithClient(<VerificationSettingsCard />);
    const toggle = await screen.findByRole("checkbox", { name: /risky addresses/ });
    await waitFor(() => expect(toggle).not.toBeDisabled());
    await user.click(toggle);
    await waitFor(() => expect(body).toEqual({ block_risky_emails: true }));
  });
});
