import type { Metadata } from "next";
import { RolesSettings } from "@/components/settings/roles-settings";

export const metadata: Metadata = { title: "Roles · Settings · LeadsGen" };

export default function RolesSettingsPage() {
  return <RolesSettings />;
}
