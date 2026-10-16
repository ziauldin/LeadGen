"use client";

import type { ReactNode } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { useFlags } from "@/hooks/use-flags";

/** Page shell for CRM pages: explains when the feature is off for this workspace. */
export function CrmPage({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  const flags = useFlags();
  return (
    <div>
      <PageHeader title={title} description={description} />
      {flags.crm === false ? (
        <p className="rounded-lg border border-[var(--outline-variant)] bg-white p-4 text-[13px] text-[var(--on-surface-variant)]">
          Deals and tasks aren&apos;t turned on for this workspace yet.
        </p>
      ) : flags.crm ? (
        children
      ) : null}
    </div>
  );
}
