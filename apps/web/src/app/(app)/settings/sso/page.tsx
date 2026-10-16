import type { Metadata } from "next";
import { SsoSettings } from "@/components/settings/sso-settings";

export const metadata: Metadata = { title: "Single sign-on · Settings · LeadsGen" };

export default function SsoSettingsPage() {
  return <SsoSettings />;
}
