import { Suspense } from "react";
import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/page-header";
import { EmailStudio } from "@/components/emails/email-studio";

export const metadata: Metadata = { title: "Email Studio — LeadsGen" };

export default function EmailStudioPage() {
  return (
    <div>
      <PageHeader
        title="Email Studio"
        description="Write a one-off email for a single lead from a template or with AI. It becomes a draft in Approvals, so nothing is sent until someone approves it."
      />
      <Suspense fallback={<p className="py-6 text-sm text-muted-foreground">Loading…</p>}>
        <EmailStudio />
      </Suspense>
    </div>
  );
}
