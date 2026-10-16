import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { LeadBulkActions } from "@/components/leads/lead-bulk-actions";
import { renderWithClient } from "@/test/render";
import { server } from "@/test/server";

type BulkBody = { lead_ids: number[]; action: string; status?: string; campaign_id?: number };

function captureBulk(result = { succeeded: 2, skipped: 0, failed: 0, results: [] }) {
  const bodies: BulkBody[] = [];
  server.use(
    http.post("http://localhost:3000/api/leads/bulk", async ({ request }) => {
      bodies.push((await request.json()) as BulkBody);
      return HttpResponse.json(result);
    }),
  );
  return bodies;
}

describe("LeadBulkActions", () => {
  it("sets a status for the selected leads and never offers opted out", async () => {
    const user = userEvent.setup();
    const bodies = captureBulk();
    const clear = vi.fn();
    renderWithClient(<LeadBulkActions selectedIds={[4, 9]} clear={clear} />);

    await user.click(screen.getByRole("button", { name: /Set status/ }));
    const dialog = await screen.findByRole("dialog", { name: "Set status for 2 leads" });
    const apply = within(dialog).getByRole("button", { name: "Apply status" });
    expect(apply).toBeDisabled();

    await user.click(within(dialog).getByRole("combobox", { name: "New status" }));
    const options = await screen.findAllByRole("option");
    expect(options.map((option) => option.textContent)).not.toContain("Opted out");
    await user.click(screen.getByRole("option", { name: "Qualified" }));

    await user.click(apply);
    await waitFor(() => expect(bodies).toHaveLength(1));
    expect(bodies[0]).toEqual({ lead_ids: [4, 9], action: "set_status", status: "qualified" });
    await waitFor(() => expect(clear).toHaveBeenCalled());
  });

  it("asks for confirmation before deleting", async () => {
    const user = userEvent.setup();
    const bodies = captureBulk({
      succeeded: 1,
      skipped: 0,
      failed: 1,
      results: [],
    });
    renderWithClient(<LeadBulkActions selectedIds={[1, 2]} clear={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: /Delete/ }));
    const dialog = await screen.findByRole("dialog", { name: "Delete 2 leads?" });
    expect(bodies).toHaveLength(0);
    await user.click(within(dialog).getByRole("button", { name: "Delete leads" }));
    await waitFor(() => expect(bodies[0]).toEqual({ lead_ids: [1, 2], action: "delete" }));
  });

  it("runs rescore straight away", async () => {
    const user = userEvent.setup();
    const bodies = captureBulk();
    renderWithClient(<LeadBulkActions selectedIds={[7]} clear={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Rescore/ }));
    await waitFor(() => expect(bodies[0]).toEqual({ lead_ids: [7], action: "rescore" }));
  });
});
