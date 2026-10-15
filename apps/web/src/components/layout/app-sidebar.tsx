"use client";

import Link from "next/link";
import { Activity, Database, Plus } from "lucide-react";
import { NavLinks } from "@/components/layout/nav-links";
import { useWorkspace } from "@/hooks/use-workspace";

export function Brand() {
  const { current } = useWorkspace();
  return (
    <div className="flex items-center gap-3">
      <div className="flex size-8 shrink-0 items-center justify-center rounded bg-[var(--primary)] text-white">
        <Database className="size-4" aria-hidden />
      </div>
      <div className="min-w-0">
        <p className="text-[14px] font-bold leading-tight tracking-tight text-[var(--primary)]">
          LeadsGen
        </p>
        <p className="truncate text-[11px] capitalize text-[var(--on-surface-variant)]">
          {current ? `${current.plan} plan` : " "}
        </p>
      </div>
    </div>
  );
}

export function NewCampaignButton({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <Link
      href="/campaigns/new"
      onClick={onNavigate}
      className="flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--primary)] py-2.5 text-[13px] font-medium text-white shadow-sm transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[var(--primary)]"
    >
      <Plus className="size-4" aria-hidden />
      New campaign
    </Link>
  );
}

export function AppSidebar() {
  return (
    <aside
      className="fixed left-0 top-0 z-20 hidden h-screen w-[260px] flex-col border-r border-[var(--outline-variant)] bg-[var(--surface)] lg:flex"
      aria-label="Sidebar"
    >
      <div className="px-6 pb-6 pt-8">
        <Brand />
      </div>
      <div className="mb-5 px-4">
        <NewCampaignButton />
      </div>
      <NavLinks />
      <div className="mt-auto border-t border-[var(--outline-variant)] px-4 py-4">
        <Link
          href="/health"
          className="flex items-center gap-3 rounded-lg px-3 py-2 text-[13px] text-[var(--on-surface-variant)] hover:bg-[var(--surface-container-high)]"
        >
          <Activity className="size-4" aria-hidden />
          System status
        </Link>
      </div>
    </aside>
  );
}
