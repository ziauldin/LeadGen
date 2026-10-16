import type { Metadata } from "next";
import { DeveloperSettings } from "@/components/settings/developer-settings";

export const metadata: Metadata = { title: "API & webhooks · Settings · LeadsGen" };

export default function DeveloperSettingsPage() {
  return <DeveloperSettings />;
}
