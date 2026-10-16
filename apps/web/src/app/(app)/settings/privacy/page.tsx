import type { Metadata } from "next";
import { PrivacySettings } from "@/components/settings/privacy-settings";

export const metadata: Metadata = { title: "Privacy · Settings · LeadsGen" };

export default function PrivacySettingsPage() {
  return <PrivacySettings />;
}
