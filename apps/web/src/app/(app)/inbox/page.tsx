"use client";

import { Suspense } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { InboxView } from "@/components/inbox/inbox-view";
import { LoadingState } from "@/components/shared/loading-error";

export default function InboxPage() {
  return (
    <div>
      <PageHeader title="Inbox" description="Every reply from every mailbox and campaign, one conversation per person." />
      <Suspense fallback={<LoadingState />}>
        <InboxView />
      </Suspense>
    </div>
  );
}
