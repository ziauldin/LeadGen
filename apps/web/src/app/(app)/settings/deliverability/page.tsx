"use client";

import { DeliverabilityCheck } from "@/components/settings/deliverability-check";
import { VerificationSettingsCard } from "@/components/settings/verification-settings-card";

export default function DeliverabilitySettingsPage() {
  return (
    <div className="space-y-6">
      <DeliverabilityCheck />
      <VerificationSettingsCard />
    </div>
  );
}
