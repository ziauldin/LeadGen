"use client";

import { ProviderSettingsPanel } from "@/components/settings/provider-settings-panel";

export default function ProvidersSettingsPage() {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-[16px] font-semibold text-[var(--on-surface)]">Providers</h2>
        <p className="text-[13px] text-[var(--on-surface-variant)]">
          Connect the services this workspace uses: where emails are sent from, where replies
          arrive, and which search, email-finding and AI services to use.
        </p>
      </div>
      <ProviderSettingsPanel />
    </div>
  );
}
