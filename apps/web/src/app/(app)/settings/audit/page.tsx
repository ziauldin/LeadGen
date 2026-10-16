"use client";

import { Suspense } from "react";
import { LoadingState } from "@/components/shared/loading-error";
import { AuditLogTable } from "@/components/settings/audit-log-table";
import { SettingsCard } from "@/components/settings/settings-card";
import { useWorkspace } from "@/hooks/use-workspace";

export default function AuditLogSettingsPage() {
  const { can, permissionsLoading } = useWorkspace();
  return (
    <SettingsCard
      id="audit-log"
      title="Audit log"
      description="Who changed what in this workspace: members, roles, settings, sending accounts and sign-in methods."
    >
      {permissionsLoading ? (
        <LoadingState />
      ) : can("audit.view") ? (
        <Suspense fallback={<LoadingState message="Loading activity…" />}>
          <AuditLogTable />
        </Suspense>
      ) : (
        <p className="text-[13px] text-[var(--on-surface-variant)]">
          Your role doesn&apos;t include viewing the audit log. Ask a workspace admin or owner.
        </p>
      )}
    </SettingsCard>
  );
}
