"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { ArrowLeft, ShieldHalf } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { cn } from "@/lib/utils";

const SECTIONS = [
  { href: "/admin", label: "Overview" },
  { href: "/admin/workspaces", label: "Workspaces" },
  { href: "/admin/users", label: "Users" },
  { href: "/admin/abuse", label: "Abuse review" },
  { href: "/admin/suppressions", label: "Global suppressions" },
  { href: "/admin/audit", label: "Admin audit trail" },
];

export function AdminShell({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const pathname = usePathname();

  if (!user?.is_superuser || user.impersonation) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[var(--background)] p-4">
        <div className="text-center">
          <h1 className="text-[20px] font-semibold">Page not found</h1>
          <Link href="/dashboard" className="mt-2 inline-block text-[13px] text-[var(--primary)] underline">
            Go to the dashboard
          </Link>
        </div>
      </main>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--background)]">
      <header className="border-b border-[var(--outline-variant)] bg-[var(--inverse-surface,#1f2937)] text-white">
        <div className="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <p className="flex items-center gap-2 text-[15px] font-semibold">
            <ShieldHalf className="size-5" aria-hidden />
            LeadsGen admin
          </p>
          <Link href="/dashboard" className="flex items-center gap-1 text-[13px] text-white/90 hover:text-white">
            <ArrowLeft className="size-4" aria-hidden /> Back to the app
          </Link>
        </div>
        <nav aria-label="Admin sections" className="mx-auto max-w-[1440px] overflow-x-auto px-4 sm:px-6">
          <ul className="flex w-max gap-1">
            {SECTIONS.map((section) => {
              const active =
                section.href === "/admin" ? pathname === "/admin" : pathname.startsWith(section.href);
              return (
                <li key={section.href}>
                  <Link
                    href={section.href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "block border-b-2 px-3 py-2 text-[13px] font-medium",
                      active ? "border-white text-white" : "border-transparent text-white/80 hover:text-white",
                    )}
                  >
                    {section.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </header>
      <main className="mx-auto max-w-[1440px] p-4 sm:p-6">{children}</main>
    </div>
  );
}

export function Stat({ label, value, tone }: { label: string; value: ReactNode; tone?: "bad" | "good" }) {
  return (
    <div className="rounded-lg border border-[var(--outline-variant)] bg-white p-4">
      <p className="text-[12px] text-[var(--on-surface-variant)]">{label}</p>
      <p
        className={cn(
          "mt-1 text-[22px] font-semibold",
          tone === "bad" && "text-[var(--error)]",
          tone === "good" && "text-[var(--primary)]",
        )}
      >
        {value}
      </p>
    </div>
  );
}

export function percent(value: number) {
  return `${(value * 100).toFixed(value && value < 0.01 ? 2 : 1)}%`;
}
