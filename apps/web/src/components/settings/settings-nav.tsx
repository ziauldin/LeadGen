"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Ban,
  Building2,
  Gauge,
  KeyRound,
  MailCheck,
  Users,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

export const SETTINGS_SECTIONS: { href: string; label: string; icon: LucideIcon }[] = [
  { href: "/settings/workspace", label: "Workspace", icon: Building2 },
  { href: "/settings/members", label: "Members", icon: Users },
  { href: "/settings/providers", label: "Providers", icon: KeyRound },
  { href: "/settings/suppressions", label: "Suppressions", icon: Ban },
  { href: "/settings/deliverability", label: "Deliverability", icon: MailCheck },
  { href: "/settings/usage", label: "Plan & usage", icon: Gauge },
];

/** Left column on desktop, a horizontally scrolling tab strip on small screens. */
export function SettingsNav() {
  const pathname = usePathname();
  return (
    <nav aria-label="Settings sections" className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
      <ul className="flex w-max gap-1 border-b border-[var(--outline-variant)] lg:w-auto lg:flex-col lg:border-b-0">
        {SETTINGS_SECTIONS.map((section) => {
          const active = pathname === section.href || pathname.startsWith(`${section.href}/`);
          const Icon = section.icon;
          return (
            <li key={section.href}>
              <Link
                href={section.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-2 whitespace-nowrap px-3 py-2 text-[13px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)]",
                  "-mb-px border-b-2 lg:mb-0 lg:rounded-md lg:border-b-0",
                  active
                    ? "border-[var(--primary)] text-[var(--primary)] lg:bg-[var(--surface-container-high)]"
                    : "border-transparent text-[var(--on-surface-variant)] hover:text-[var(--on-surface)] lg:hover:bg-[var(--surface-container-low)]",
                )}
              >
                <Icon className="size-4 shrink-0" aria-hidden />
                {section.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
