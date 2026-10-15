"use client";

import { Suspense } from "react";
import { LoadingState } from "@/components/shared/loading-error";
import { SettingsCard } from "@/components/settings/settings-card";
import { SuppressionAddForm } from "@/components/settings/suppression-add-form";
import { SuppressionsTable } from "@/components/settings/suppressions-table";
import { useWorkspace } from "@/hooks/use-workspace";

export default function SuppressionsSettingsPage() {
  const { hasRole } = useWorkspace();
  return (
    <div className="space-y-6">
      <SettingsCard
        id="add-suppression"
        title="Do not contact"
        description="Anyone on this list is skipped by every campaign, and drafts to them can't be approved. It's checked again right before each email is sent."
      >
        <SuppressionAddForm />
      </SettingsCard>

      <SettingsCard id="suppression-list" title="Suppression list">
        <Suspense fallback={<LoadingState message="Loading suppression list…" />}>
          <SuppressionsTable canDelete={hasRole("admin")} />
        </Suspense>
        {!hasRole("admin") ? (
          <p className="mt-3 text-[12px] text-[var(--on-surface-variant)]">
            Only admins and owners can remove entries from the list.
          </p>
        ) : null}
      </SettingsCard>
    </div>
  );
}
