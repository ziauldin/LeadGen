import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { OnboardingChecklist } from "@/components/dashboard/onboarding-checklist";
import { renderWithClient } from "@/test/render";
import { server } from "@/test/server";

const ONBOARDING_URL = "http://localhost:3000/api/workspaces/current/onboarding";

function mockOnboarding(status: Record<string, boolean>) {
  server.use(http.get(ONBOARDING_URL, () => HttpResponse.json(status)));
}

const partial = {
  email_verified: false,
  sender_profile: true,
  sending_provider: false,
  niche_created: true,
  leads_added: false,
  campaign_created: false,
  completed: false,
};

describe("OnboardingChecklist", () => {
  it("shows progress and a link for each unfinished step", async () => {
    mockOnboarding(partial);
    renderWithClient(<OnboardingChecklist />);

    expect(await screen.findByRole("heading", { name: "Get set up" })).toBeInTheDocument();
    expect(screen.getByText(/2 of 6 steps done/)).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Setup progress" })).toHaveAttribute(
      "aria-valuenow",
      "2",
    );

    const steps = within(screen.getByRole("list")).getAllByRole("listitem");
    expect(steps).toHaveLength(6);
    expect(steps[1]).toHaveTextContent("Add your sender details (done)");
    expect(steps[3]).toHaveTextContent("Create a niche (done)");

    expect(screen.getByRole("link", { name: "Connect provider" })).toHaveAttribute(
      "href",
      "/settings/providers",
    );
    expect(screen.getByRole("link", { name: "Find leads" })).toHaveAttribute("href", "/search");
    expect(screen.getByRole("link", { name: "Import CSV" })).toHaveAttribute("href", "/leads");
    expect(screen.getByRole("link", { name: "Create campaign" })).toHaveAttribute(
      "href",
      "/campaigns/new",
    );
    // Finished steps don't offer an action.
    expect(screen.queryByRole("link", { name: "Create niche" })).not.toBeInTheDocument();
  });

  it("resends the verification email", async () => {
    const user = userEvent.setup();
    mockOnboarding(partial);
    let resent = 0;
    server.use(
      http.post("http://localhost:3000/api/auth/resend-verification", () => {
        resent += 1;
        return HttpResponse.json({ message: "sent" });
      }),
    );
    renderWithClient(<OnboardingChecklist />);

    await user.click(await screen.findByRole("button", { name: "Resend verification email" }));
    await waitFor(() => expect(resent).toBe(1));
    expect(await screen.findByRole("button", { name: "Email sent" })).toBeDisabled();
  });

  it("collapses the steps", async () => {
    const user = userEvent.setup();
    mockOnboarding(partial);
    renderWithClient(<OnboardingChecklist />);
    const toggle = await screen.findByRole("button", { name: /Hide steps/ });
    await user.click(toggle);
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Show steps/ })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });

  it("renders nothing once setup is complete", async () => {
    let requested = false;
    server.use(
      http.get(ONBOARDING_URL, () => {
        requested = true;
        return HttpResponse.json({
          email_verified: true,
          sender_profile: true,
          sending_provider: true,
          niche_created: true,
          leads_added: true,
          campaign_created: true,
          completed: true,
        });
      }),
    );
    const { container } = renderWithClient(<OnboardingChecklist />);
    await waitFor(() => expect(requested).toBe(true));
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });
});
