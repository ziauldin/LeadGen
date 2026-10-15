"use client";

import { Suspense, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Download, FlaskConical } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { RepliesList } from "@/components/replies/replies-list";
import { LoadingState } from "@/components/shared/loading-error";
import { Button } from "@/components/ui/button";
import { api, getErrorMessage } from "@/lib/api/client";
import { repliesApi } from "@/lib/api/endpoints";

/** Dev-only helper: simulate replies to emails sent with the mock provider. */
function SimulateRepliesButton() {
  const queryClient = useQueryClient();
  const [unavailable, setUnavailable] = useState(false);
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, staleTime: 5 * 60_000 });

  const sync = useMutation({
    mutationFn: repliesApi.sync,
    meta: { silent: true },
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["replies"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success(result.message);
    },
    onError: (error) => {
      // Not available here (production, or no mock sender): hide the button for this visit.
      setUnavailable(true);
      toast.info(getErrorMessage(error));
    },
  });

  if (unavailable || !health.data || health.data.environment === "production") return null;
  return (
    <Button variant="outline" onClick={() => sync.mutate()} disabled={sync.isPending}>
      <FlaskConical aria-hidden />
      {sync.isPending ? "Simulating…" : "Simulate replies"}
    </Button>
  );
}

export default function RepliesPage() {
  const exportCsv = useMutation({
    mutationFn: repliesApi.exportCsv,
    onSuccess: () => toast.success("Replies exported"),
  });

  return (
    <div>
      <PageHeader
        title="Replies"
        description="Every answer to your outreach in one inbox, labelled so you know who to follow up with first."
        actions={
          <>
            <SimulateRepliesButton />
            <Button
              variant="outline"
              onClick={() => exportCsv.mutate()}
              disabled={exportCsv.isPending}
            >
              <Download aria-hidden />
              {exportCsv.isPending ? "Exporting…" : "Export CSV"}
            </Button>
          </>
        }
      />
      <Suspense fallback={<LoadingState message="Loading replies…" />}>
        <RepliesList />
      </Suspense>
    </div>
  );
}
