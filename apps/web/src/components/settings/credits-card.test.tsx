import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { CreditsCard } from "@/components/settings/credits-card";
import { renderWithClient } from "@/test/render";
import { server } from "@/test/server";

const url = (path: string) => `http://localhost:3000/api${path}`;
const can = vi.fn(() => true);
vi.mock("@/hooks/use-workspace", () => ({ useWorkspace: () => ({ can }) }));

const CREDITS = {
  balance: 1250,
  units: { monthly_verifications: 1, daily_hunter_lookups: 1, monthly_llm_tokens: 1000 },
  packs: [
    { credits: 1000, amount: 10, purchasable: true },
    { credits: 5000, amount: 40, purchasable: false },
  ],
};

describe("CreditsCard", () => {
  it("shows the balance, what a credit buys and recent activity, and buys a pack", async () => {
    const user = userEvent.setup();
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign, search: "" });
    let bought: unknown = null;
    server.use(
      http.get(url("/billing/credits"), () =>
        HttpResponse.json([
          { id: 2, amount: -3, kind: "usage", metric: "monthly_verifications", note: null, balance_after: 1250, created_at: "2026-10-20T00:00:00Z" },
          { id: 1, amount: 1000, kind: "purchase", metric: null, note: "Credit pack", balance_after: 1253, created_at: "2026-10-19T00:00:00Z" },
        ]),
      ),
      http.post(url("/billing/credits/checkout"), async ({ request }) => {
        bought = await request.json();
        return HttpResponse.json({ url: "https://checkout.stripe.com/c/pay/cs_1" });
      }),
    );
    renderWithClient(<CreditsCard credits={CREDITS} />);
    expect(screen.getByText("1,250")).toBeInTheDocument();
    expect(screen.getByText(/One credit buys 1 email verification, 1 email lookup, 1,000 AI tokens/)).toBeInTheDocument();
    expect(await screen.findByText("Used for email verification")).toBeInTheDocument();
    expect(screen.getByText("+1,000")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Not available online" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Buy 1,000" }));
    await waitFor(() => expect(assign).toHaveBeenCalledWith("https://checkout.stripe.com/c/pay/cs_1"));
    expect(bought).toEqual({ credits: 1000 });
    vi.unstubAllGlobals();
  });

  it("hides buying from people who can't manage billing", () => {
    can.mockReturnValue(false);
    server.use(http.get(url("/billing/credits"), () => HttpResponse.json([])));
    renderWithClient(<CreditsCard credits={CREDITS} />);
    expect(screen.queryByRole("button", { name: /Buy/ })).not.toBeInTheDocument();
    expect(screen.getByText(/Only people who manage billing can buy credits/)).toBeInTheDocument();
  });
});
