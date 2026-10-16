import {
  Building2,
  CheckSquare,
  FileText,
  Inbox,
  LayoutDashboard,
  Mail,
  Megaphone,
  MessagesSquare,
  Search,
  Settings,
  Target,
  Users,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  badge?: "approvals";
};

export const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/niches", label: "Niches", icon: Target },
  { href: "/search", label: "Search", icon: Search },
  { href: "/leads", label: "Leads", icon: Users },
  { href: "/companies", label: "Companies", icon: Building2 },
  { href: "/approvals", label: "Approvals", icon: CheckSquare, badge: "approvals" },
  { href: "/campaigns", label: "Campaigns", icon: Megaphone },
  { href: "/templates", label: "Templates", icon: FileText },
  { href: "/email-studio", label: "Email Studio", icon: Mail },
  { href: "/inbox", label: "Inbox", icon: Inbox },
  { href: "/replies", label: "Replies", icon: MessagesSquare },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function isActive(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}
