"use client";

import { useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/layout/page-header";
import { LeadTable } from "@/components/leads/lead-table";
import { leadsApi } from "@/lib/api/endpoints";

export default function LeadsPage() {
  const searchParams = useSearchParams();
  const nicheId = searchParams.get("niche_id");
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [importing, setImporting] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["leads", nicheId],
    queryFn: () =>
      leadsApi.list(nicheId ? { niche_id: Number(nicheId) } : undefined),
  });

  const recalcMutation = useMutation({
    mutationFn: () => leadsApi.recalculateScores(nicheId ? Number(nicheId) : undefined),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      toast.success(`Updated scores for ${result.updated} leads`);
    },
  });

  async function handleImport(file: File) {
    setImporting(true);
    try {
      const result = await leadsApi.importCsv(file);
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      toast.success(`Imported ${result.created} leads (${result.skipped} skipped)`);
      if (result.errors.length > 0) {
        toast.warning(`${result.errors.length} rows had errors`);
      }
    } catch {
      toast.error("CSV import failed");
    } finally {
      setImporting(false);
    }
  }

  async function handleExport() {
    try {
      await leadsApi.exportCsv(nicheId ? Number(nicheId) : undefined);
      toast.success("Export started");
    } catch {
      toast.error("Export failed");
    }
  }

  return (
    <div>
      <PageHeader
        title="Leads"
        description="Qualified contacts for outreach."
        actions={
          <>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void handleImport(file);
                e.target.value = "";
              }}
            />
            <Button
              variant="outline"
              onClick={() => fileInputRef.current?.click()}
              disabled={importing}
            >
              {importing ? "Importing…" : "Import CSV"}
            </Button>
            <Button variant="outline" onClick={() => void handleExport()}>
              Export CSV
            </Button>
            <Button
              variant="outline"
              onClick={() => recalcMutation.mutate()}
              disabled={recalcMutation.isPending}
            >
              Recalculate scores
            </Button>
          </>
        }
      />
      {isLoading ? <p className="text-sm text-muted-foreground">Loading…</p> : null}
      {data ? <LeadTable leads={data.items} /> : null}
    </div>
  );
}
