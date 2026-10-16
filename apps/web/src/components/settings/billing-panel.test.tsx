import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BillingPanel } from "@/components/settings/billing-panel";
import type { BillingSummary } from "@/lib/api/types";
import { renderWithClient } from "@/test/render";
import { server } from "@/test/server";

const url = (path: string) => `http://localhost:3000/api${path}`;

let granted = new Set<string>();
vi.mock("@/hooks/use-workspace", () => ({
  useWorkspace: () => ({ can: (p: string) => granted.has(p) }),
}));

const LIMITS = { monthly_sends: 5000, monthly_leads: 10000, seats: 5, max_campaigns: 20 };
function summary(overrides: Partial<BillingSummary> = {}): BillingSummary {
  return {
    plan: "free",
    limits: LIMITS,
    features: {},
    usage: [],
    billing_enabled: true,
    purchasable: ["pro:month", "pro:year", "starter:month"],
    plan_limits: { starter: LIMITS, pro: { ...LIMITS, monthly_sends: 50000 } },
    trial_ends_at: null,
    subscription: null,
    sending_paused_for_payment: false,
    ...overrides,
  } as BillingSummary;
}

describe("BillingPanel", () => {
  beforeEach(() => {
    granted = new Set(["billing.manage"]);
  });

  it("starts checkout for the chosen plan and period", async () => {
    const user = userEvent.setup();
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign, search: "" });
    let body: unknown = null;
    server.use(
      http.post(url("/billing/checkout"), async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ url: "https://checkout.stripe.com/c/pay/cs_1" });
      }),
    );
    renderWithClient(<BillingPanel data={summary()} />);
    expect(screen.getByText("50,000 emails a month")).toBeInTheDocument();

    await user.click(screen.getByRole("radio", { name: "Yearly" }));
    expect(screen.getByRole("button", { name: "Not available yearly" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Choose pro" }));
    await waitFor(() => expect(body).toEqual({ plan: "pro", interval: "year" }));
    await waitFor(() => expect(assign).toHaveBeenCalledWith("https://checkout.stripe.com/c/pay/cs_1"));
    vi.unstubAllGlobals();
  });

  it("warns about failed payments and offers the billing portal", () => {
    renderWithClient(
      <BillingPanel
        data={summary({
          plan: "pro",
          subscription: {
            status: "past_due",
            plan: "pro",
            interval: "month",
            current_period_end: "2026-11-01T00:00:00Z",
            cancel_at_period_end: false,
            past_due_since: "2026-10-01T00:00:00Z",
            grace_ends_at: "2026-10-08T00:00:00Z",
            has_billing_account: true,
          },
        })}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/payment failed/);
    expect(screen.getByRole("button", { name: /Manage billing/ })).toBeInTheDocument();
    expect(screen.getByText(/Payment overdue · billed monthly/)).toBeInTheDocument();
  });

  it("shows trials and hides purchase options from non-owners", () => {
    granted = new Set();
    const ends = new Date(Date.now() + 5 * 86_400_000).toISOString();
    renderWithClient(<BillingPanel data={summary({ plan: "starter", trial_ends_at: ends })} />);
    expect(screen.getByText("Free trial: 5 days left")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Choose/ })).not.toBeInTheDocument();
    expect(screen.getByText(/Only workspace owners can change the plan/)).toBeInTheDocument();
  });
});
