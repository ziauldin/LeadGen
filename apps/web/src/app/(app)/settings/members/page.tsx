"use client";

import { InvitationsPanel } from "@/components/settings/invitations-panel";
import { MembersTable } from "@/components/settings/members-table";
import { AdminOnlyNotice } from "@/components/settings/settings-card";
import { useWorkspace } from "@/hooks/use-workspace";

export default function MembersSettingsPage() {
  const { can, permissionsLoading } = useWorkspace();
  return (
    <div className="space-y-6">
      <MembersTable />
      {can("members.manage") ? (
        <InvitationsPanel />
      ) : permissionsLoading ? null : (
        <AdminOnlyNotice what="invite people, change roles or remove members" />
      )}
    </div>
  );
}
