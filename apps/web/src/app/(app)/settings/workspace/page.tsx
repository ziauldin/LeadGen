"use client";

import { SenderProfileForm } from "@/components/settings/sender-profile-form";
import { WorkspaceActions } from "@/components/settings/workspace-actions";
import { WorkspaceProfileForm } from "@/components/settings/workspace-profile-form";

export default function WorkspaceSettingsPage() {
  return (
    <div className="space-y-6">
      <WorkspaceProfileForm />
      <SenderProfileForm />
      <WorkspaceActions />
    </div>
  );
}
