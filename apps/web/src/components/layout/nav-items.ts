import {
  BarChart3,
  Building2,
  CheckSquare,
  FileText,
  Inbox,
  KanbanSquare,
  LayoutDashboard,
  ListTodo,
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
  /** Only shown when this feature flag is on for the workspace. */
  flag?: string;
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
  { href: "/deals", label: "Deals", icon: KanbanSquare, flag: "crm" },
  { href: "/tasks", label: "Tasks", icon: ListTodo, flag: "crm" },
  { href: "/replies", label: "Replies", icon: MessagesSquare },
  { href: "/analytics", label: "Analytics", icon: BarChart3, flag: "analytics_v2" },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function isActive(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}
