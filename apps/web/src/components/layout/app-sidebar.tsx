"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Building2,
  Inbox,
  LayoutDashboard,
  Mail,
  Megaphone,
  Search,
  Settings,
  Target,
  Users,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/niches", label: "Niches", icon: Target },
  { href: "/search", label: "Search", icon: Search },
  { href: "/leads", label: "Leads", icon: Users },
  { href: "/companies", label: "Companies", icon: Building2 },
  { href: "/campaigns", label: "Campaigns", icon: Megaphone },
  { href: "/email-studio", label: "Email studio", icon: Mail },
  { href: "/replies", label: "Replies", icon: Inbox },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function AppSidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden w-60 shrink-0 border-r bg-card md:block">
      <div className="flex h-14 items-center border-b px-4">
        <Link href="/dashboard" className="font-semibold tracking-tight">
          LeadsGen
        </Link>
      </div>
      <nav className="flex flex-col gap-1 p-3">
        {navItems.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              <Icon className="size-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
