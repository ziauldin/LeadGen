import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { OnboardingWizard } from "@/components/dashboard/onboarding-wizard";
import { renderWithClient } from "@/test/render";
import { server } from "@/test/server";

const url = (path: string) => `http://localhost:3000/api${path}`;
const STATUS = {
  email_verified: true,
  sender_profile: true,
  sending_provider: false,
  niche_created: false,
  leads_added: false,
  campaign_created: false,
  completed: false,
};

describe("OnboardingWizard", () => {
  it("opens on the first unfinished step and can skip ahead", async () => {
    const user = userEvent.setup();
    server.use(http.get(url("/workspaces/current/onboarding"), () => HttpResponse.json(STATUS)));
    renderWithClient(<OnboardingWizard />);
    expect(await screen.findByRole("heading", { level: 2, name: "Connect an email provider" })).toBeInTheDocument();
    expect(screen.getByText("2 of 7 done. This takes about 15 minutes.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Connect provider" })).toHaveAttribute("href", "/settings/providers");

    await user.click(screen.getByRole("button", { name: "Skip for now" }));
    expect(screen.getByRole("heading", { level: 2, name: "Check your domain's DNS" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Verify your email address/ }));
    expect(screen.getByRole("heading", { level: 2, name: "Verify your email address" })).toBeInTheDocument();
    expect(screen.getByText("Done")).toBeInTheDocument();
  });

  it("celebrates when the required steps are done", async () => {
    server.use(
      http.get(url("/workspaces/current/onboarding"), () =>
        HttpResponse.json(Object.fromEntries(Object.keys(STATUS).map((key) => [key, true]))),
      ),
    );
    renderWithClient(<OnboardingWizard />);
    expect(await screen.findByRole("heading", { name: "You're ready to go" })).toBeInTheDocument();
  });
});
