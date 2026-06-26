import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export type SearchResultRow = {
  index: number;
  title: string;
  url: string;
  snippet?: string;
};

export function SearchResultsTable({
  results,
  selected,
  onToggle,
  onToggleAll,
}: {
  results: SearchResultRow[];
  selected: Set<number>;
  onToggle: (index: number) => void;
  onToggleAll: () => void;
}) {
  if (results.length === 0) {
    return <p className="text-sm text-muted-foreground">No results to display.</p>;
  }

  const allSelected = selected.size === results.length;

  return (
    <div className="rounded-lg border">
      <div className="flex items-center justify-between border-b px-4 py-2">
        <p className="text-sm font-medium">{results.length} results</p>
        <Button size="sm" variant="outline" onClick={onToggleAll}>
          {allSelected ? "Deselect all" : "Select all"}
        </Button>
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-12">Save</TableHead>
            <TableHead>Title</TableHead>
            <TableHead>URL</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {results.map((row) => (
            <TableRow key={row.index}>
              <TableCell>
                <input
                  type="checkbox"
                  checked={selected.has(row.index)}
                  onChange={() => onToggle(row.index)}
                  className="size-4"
                />
              </TableCell>
              <TableCell className="font-medium">{row.title}</TableCell>
              <TableCell className="max-w-md truncate text-sm text-muted-foreground">
                {row.url}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
