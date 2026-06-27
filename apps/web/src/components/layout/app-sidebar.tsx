"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Building2,
  Database,
  HelpCircle,
  Inbox,
  LayoutDashboard,
  Mail,
  Megaphone,
  Plus,
  Search,
  Settings,
  Target,
  Users,
  FileText,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";

const navItems = [
  { href: "/dashboard",    label: "Dashboard",    icon: LayoutDashboard },
  { href: "/niches",       label: "Niches",        icon: Target },
  { href: "/search",       label: "Search",        icon: Search },
  { href: "/leads",        label: "Leads",         icon: Users },
  { href: "/companies",    label: "Companies",     icon: Building2 },
  { href: "/email-studio", label: "Email Studio",  icon: Mail },
  { href: "/campaigns",    label: "Campaigns",     icon: Megaphone },
  { href: "/replies",      label: "Replies",       icon: Inbox },
  { href: "/settings",     label: "Settings",      icon: Settings },
];

const footerItems = [
  { href: "/health", label: "System Status", icon: Database },
  { href: "#",       label: "Documentation", icon: FileText },
  { href: "#",       label: "Support",       icon: HelpCircle },
];

export function AppSidebar() {
  const pathname = usePathname();
  const { user } = useAuth();

  return (
    <aside
      className="hidden md:flex flex-col fixed left-0 top-0 h-screen w-[260px] border-r z-20"
      style={{
        background: "var(--surface)",
        borderColor: "var(--outline-variant)",
      }}
    >
      {/* Brand */}
      <div className="px-6 pt-8 pb-6">
        <div className="flex items-center gap-3">
          <div
            className="w-8 h-8 rounded flex items-center justify-center text-white flex-shrink-0"
            style={{ background: "var(--primary)" }}
          >
            <Database className="w-4 h-4" />
          </div>
          <div>
            <h1
              className="text-[14px] font-bold leading-tight tracking-tight"
              style={{ color: "var(--primary)" }}
            >
              LeadsGen Pro
            </h1>
            <p
              className="text-[11px] font-normal"
              style={{ color: "var(--on-surface-variant)" }}
            >
              Enterprise Plan
            </p>
          </div>
        </div>
      </div>

      {/* New Campaign CTA */}
      <div className="px-4 mb-5">
        <Link
          href="/campaigns"
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg text-[13px] font-medium text-white transition-opacity hover:opacity-90 active:scale-95 shadow-sm"
          style={{ background: "var(--primary)" }}
        >
          <Plus className="w-4 h-4" />
          New Campaign
        </Link>
      </div>

      {/* Main Nav */}
      <nav className="flex-1 overflow-y-auto px-2 space-y-0.5">
        {navItems.map((item) => {
          const active =
            pathname === item.href || pathname.startsWith(`${item.href}/`);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg mx-2 text-[13px] font-medium transition-colors duration-150 active:scale-95",
                active
                  ? "font-semibold"
                  : "hover:bg-[#dce9ff]"
              )}
              style={
                active
                  ? {
                      background: "var(--primary-container)",
                      color: "var(--on-primary-container)",
                    }
                  : { color: "var(--on-surface-variant)" }
              }
            >
              <Icon className="w-4 h-4 shrink-0" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Footer Nav */}
      <div
        className="mt-auto px-2 pt-4 pb-4 border-t space-y-0.5"
        style={{ borderColor: "var(--outline-variant)" }}
      >
        {footerItems.map((item) => {
          const active = pathname === item.href;
          const Icon = item.icon;
          return (
            <Link
              key={item.label}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg mx-2 text-[13px] transition-colors duration-150 active:scale-95",
                active ? "font-semibold" : "hover:bg-[#dce9ff]"
              )}
              style={{ color: "var(--on-surface-variant)" }}
            >
              <Icon className="w-4 h-4 shrink-0" />
              {item.label}
            </Link>
          );
        })}

        {/* User profile area */}
        {user && (
          <div
            className="mx-2 mt-2 pt-3 border-t flex items-center gap-3"
            style={{ borderColor: "var(--outline-variant)" }}
          >
            <div
              className="w-8 h-8 rounded-full flex items-center justify-center text-[12px] font-bold text-white shrink-0"
              style={{ background: "var(--primary)" }}
            >
              {user.name?.slice(0, 2).toUpperCase() ?? "LG"}
            </div>
            <div className="min-w-0 flex-1">
              <p
                className="text-[12px] font-semibold truncate"
                style={{ color: "var(--on-surface)" }}
              >
                {user.name}
              </p>
              <p
                className="text-[11px] truncate"
                style={{ color: "var(--on-surface-variant)" }}
              >
                {user.email}
              </p>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
