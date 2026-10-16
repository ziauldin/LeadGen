import { Suspense } from "react";
import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/page-header";
import { ApprovalQueueView } from "@/components/approvals/approval-queue";

export const metadata: Metadata = { title: "Approvals — LeadsGen" };

export default function ApprovalsPage() {
  return (
    <div>
      <PageHeader
        title="Approvals"
        description="Every email is a draft until someone here approves it. Review, edit or reject before anything is sent."
      />
      <Suspense fallback={<p className="py-6 text-sm text-muted-foreground">Loading drafts…</p>}>
        <ApprovalQueueView />
      </Suspense>
    </div>
  );
}
