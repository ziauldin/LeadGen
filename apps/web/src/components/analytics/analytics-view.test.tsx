import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { AnalyticsView } from "@/components/analytics/analytics-view";
import { CampaignVariantsCard } from "@/components/campaigns/campaign-variants-card";
import { renderWithClient } from "@/test/render";
import { server } from "@/test/server";

const url = (path: string) => `http://localhost:3000/api${path}`;
vi.mock("@/hooks/use-workspace", () => ({ useWorkspace: () => ({ can: () => true }) }));

const rates = { reply_rate: 0.25, positive_rate: 0.125, bounce_rate: 0.05 };
const row = (key: unknown, label: string) => ({ key, label, sent: 40, bounced: 2, replies: 10, positive: 5, ...rates });

function overview(days: number) {
  return {
    days,
    totals: { sent: 40, bounced: 2, replies: 10, positive: 5, ...rates },
    series: [{ date: "2026-10-15", sent: 40, bounced: 2, replies: 10, positive: 5 }],
    by_campaign: [row(1, "Food manufacturers")],
    by_step: [row(1, "Step 1")],
    by_variant: [row("A", "A"), row("B", "B")],
    by_mailbox: [row(null, "Default sender")],
    by_template: [row(null, "Custom / AI")],
  };
}

describe("AnalyticsView", () => {
  it("shows totals and switches range and breakdown", async () => {
    const user = userEvent.setup();
    const requested: string[] = [];
    server.use(
      http.get(url("/analytics/overview"), ({ request }) => {
        const days = Number(new URL(request.url).searchParams.get("days"));
        requested.push(String(days));
        return HttpResponse.json(overview(days));
      }),
    );
    renderWithClient(<AnalyticsView />);
    expect(await screen.findByText("Reply rate", { selector: "p" })).toBeInTheDocument();
    expect(screen.getAllByText("25%").length).toBeGreaterThan(1);
    expect(screen.getByText("12.5%")).toBeInTheDocument();
    const table = screen.getByRole("table");
    expect(within(table).getByRole("rowheader", { name: "Food manufacturers" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "A/B version" }));
    expect(within(screen.getByRole("table")).getByRole("rowheader", { name: "B" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Last 90 days" }));
    expect(await screen.findByRole("button", { name: "Last 90 days", pressed: true })).toBeInTheDocument();
    expect(requested).toEqual(["30", "90"]);
  });
});

describe("CampaignVariantsCard", () => {
  it("lists versions and the suggested winner", async () => {
    server.use(
      http.get(url("/campaigns/3/variants"), () =>
        HttpResponse.json([
          {
            step_number: 1,
            min_sends: 30,
            winner: { variant: "B", p_value: 0.004 },
            variants: [
              { variant: "A", sent: 40, bounced: 0, replies: 2, positive: 1, reply_rate: 0.05, positive_rate: 0.025, bounce_rate: 0 },
              { variant: "B", sent: 40, bounced: 0, replies: 12, positive: 6, reply_rate: 0.3, positive_rate: 0.15, bounce_rate: 0 },
            ],
          },
          { step_number: 2, min_sends: 30, winner: null, variants: [{ variant: "A", sent: 10, bounced: 0, replies: 0, positive: 0, reply_rate: 0, positive_rate: 0, bounce_rate: 0 }] },
        ]),
      ),
    );
    renderWithClient(<CampaignVariantsCard campaignId={3} />);
    expect(await screen.findByText(/Version B is winning/)).toBeInTheDocument();
    expect(screen.getByText("30%")).toBeInTheDocument();
    // Step 2 has only one version, so it isn't an A/B test.
    expect(screen.queryByText("Step 2")).not.toBeInTheDocument();
  });
});
