import type { Metadata } from "next";
import { IntegrationsSettings } from "@/components/settings/integrations-settings";

export const metadata: Metadata = { title: "Integrations · Settings · LeadsGen" };

export default function IntegrationsSettingsPage() {
  return <IntegrationsSettings />;
}
