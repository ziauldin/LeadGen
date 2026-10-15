import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DataTable, type DataTableColumn } from "@/components/data-table/data-table";

type Row = { id: number; name: string; score: number };

const columns: DataTableColumn<Row>[] = [
  { accessorKey: "name", header: "Name", sortKey: "full_name" },
  { accessorKey: "score", header: "Score", sortKey: "score" },
];
const rows: Row[] = [
  { id: 1, name: "Alex", score: 80 },
  { id: 2, name: "Sam", score: 60 },
];

function setup(overrides: Partial<React.ComponentProps<typeof DataTable<Row>>> = {}) {
  const props = {
    columns,
    data: rows,
    total: 60,
    page: 0,
    pageSize: 25,
    onPageChange: vi.fn(),
    onSortChange: vi.fn(),
    ...overrides,
  };
  render(<DataTable<Row> {...props} />);
  return props;
}

describe("DataTable", () => {
  it("renders rows and paging text", () => {
    setup();
    expect(screen.getByText("Alex")).toBeInTheDocument();
    expect(screen.getByText("Showing 1–25 of 60")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();
  });

  it("cycles sort ascending, descending, off", async () => {
    const user = userEvent.setup();
    const props = setup({ sort: undefined });
    await user.click(screen.getByRole("button", { name: /Score/ }));
    expect(props.onSortChange).toHaveBeenLastCalledWith("score");
  });

  it("shows descending when sorted by -score and clears on next click", async () => {
    const user = userEvent.setup();
    const props = setup({ sort: "-score" });
    expect(screen.getByRole("columnheader", { name: /Score/ })).toHaveAttribute(
      "aria-sort",
      "descending",
    );
    await user.click(screen.getByRole("button", { name: /Score/ }));
    expect(props.onSortChange).toHaveBeenLastCalledWith(undefined);
  });

  it("selects rows and passes their ids to bulk actions", async () => {
    const user = userEvent.setup();
    const action = vi.fn();
    setup({
      bulkActions: (ids) => (
        <button type="button" onClick={() => action(ids)}>
          Approve selected
        </button>
      ),
    });
    expect(screen.queryByRole("region", { name: "Bulk actions" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: "Select all rows on this page" }));
    const bar = screen.getByRole("region", { name: "Bulk actions" });
    expect(within(bar).getByText("2 selected")).toBeInTheDocument();
    await user.click(within(bar).getByRole("button", { name: "Approve selected" }));
    expect(action).toHaveBeenCalledWith([1, 2]);
  });

  it("shows errors with a retry", async () => {
    const user = userEvent.setup();
    const retry = vi.fn();
    setup({ error: new Error("Boom"), onRetry: retry });
    expect(screen.getByRole("alert")).toHaveTextContent("Boom");
    await user.click(screen.getByRole("button", { name: /Try again/ }));
    expect(retry).toHaveBeenCalled();
  });
});
