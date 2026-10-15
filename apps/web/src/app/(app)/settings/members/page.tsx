"use client";

import { InvitationsPanel } from "@/components/settings/invitations-panel";
import { MembersTable } from "@/components/settings/members-table";
import { AdminOnlyNotice } from "@/components/settings/settings-card";
import { useWorkspace } from "@/hooks/use-workspace";

export default function MembersSettingsPage() {
  const { hasRole, loading } = useWorkspace();
  const isAdmin = hasRole("admin");
  return (
    <div className="space-y-6">
      <MembersTable />
      {isAdmin ? (
        <InvitationsPanel />
      ) : loading ? null : (
        <AdminOnlyNotice what="invite people, change roles or remove members" />
      )}
    </div>
  );
}
