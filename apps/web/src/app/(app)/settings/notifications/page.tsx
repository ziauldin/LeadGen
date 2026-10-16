import type { Metadata } from "next";
import { NotificationSettings } from "@/components/settings/notification-settings";

export const metadata: Metadata = { title: "Notifications · Settings · LeadsGen" };

export default function NotificationSettingsPage() {
  return <NotificationSettings />;
}
