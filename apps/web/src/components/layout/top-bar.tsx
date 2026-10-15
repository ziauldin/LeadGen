"use client";

import Link from "next/link";
import { Check, ChevronDown, ChevronsUpDown, LogOut, Settings } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/hooks/use-auth";
import { useWorkspace } from "@/hooks/use-workspace";
import { authApi } from "@/lib/api/endpoints";
import { getErrorMessage } from "@/lib/api/client";
import { MobileNav } from "@/components/layout/mobile-nav";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

function WorkspaceSwitcher() {
  const { workspaces, current, switchTo } = useWorkspace();
  if (!current) return null;

  async function choose(id: number) {
    if (id === current?.id) return;
    try {
      await switchTo(id);
      toast.success("Switched workspace");
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className="flex max-w-[220px] items-center gap-2 rounded-lg border border-[var(--outline-variant)] px-3 py-1.5 text-[13px] font-medium text-[var(--on-surface)] hover:bg-[var(--surface-container-low)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)]"
        aria-label={`Workspace: ${current.name}. Switch workspace`}
      >
        <span className="truncate">{current.name}</span>
        <ChevronsUpDown className="size-3.5 shrink-0 opacity-60" aria-hidden />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-60">
        {workspaces.map((workspace) => (
          <DropdownMenuItem
            key={workspace.id}
            onClick={() => void choose(workspace.id)}
            className="cursor-pointer gap-2 text-[13px]"
          >
            <span className="flex-1 truncate">{workspace.name}</span>
            <span className="text-[11px] capitalize text-[var(--on-surface-variant)]">
              {workspace.role}
            </span>
            {workspace.id === current.id && <Check className="size-3.5" aria-hidden />}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="cursor-pointer text-[13px]"
          render={<Link href="/settings/workspace" />}
        >
          Workspace settings
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function TopBar() {
  const { user, logout } = useAuth();

  async function signOutEverywhere() {
    try {
      await authApi.logoutAll();
    } finally {
      await logout();
    }
  }

  return (
    <header className="fixed left-0 right-0 top-0 z-10 flex h-16 items-center gap-3 border-b border-[var(--outline-variant)] bg-[var(--surface-container-lowest)] px-4 shadow-[0_1px_3px_rgba(0,0,0,0.05)] sm:px-6 lg:left-[260px] lg:px-8">
      <MobileNav />
      <WorkspaceSwitcher />

      <div className="ml-auto flex items-center gap-3">
        <DropdownMenu>
          <DropdownMenuTrigger
            className="flex items-center gap-2 rounded-lg px-2 py-1.5 transition-colors hover:bg-[var(--surface-container-low)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)]"
            aria-label="Account menu"
          >
            <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-[var(--primary)] text-[11px] font-bold text-white">
              {user?.name?.slice(0, 2).toUpperCase() ?? "LG"}
            </span>
            {user && (
              <span className="hidden max-w-[140px] truncate text-[13px] font-medium text-[var(--on-surface)] sm:block">
                {user.name}
              </span>
            )}
            <ChevronDown className="size-3.5 shrink-0 text-[var(--on-surface-variant)]" aria-hidden />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            {user && (
              <>
                <div className="px-3 py-2">
                  <p className="truncate text-[13px] font-semibold text-[var(--on-surface)]">
                    {user.name}
                  </p>
                  <p className="truncate text-[11px] text-[var(--on-surface-variant)]">
                    {user.email}
                  </p>
                </div>
                <DropdownMenuSeparator />
              </>
            )}
            <DropdownMenuItem
              className="cursor-pointer gap-2 text-[13px]"
              render={<Link href="/settings" />}
            >
              <Settings className="size-3.5" aria-hidden />
              Settings
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => void signOutEverywhere()}
              className="cursor-pointer gap-2 text-[13px]"
            >
              <LogOut className="size-3.5" aria-hidden />
              Sign out on all devices
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => void logout()}
              className="cursor-pointer gap-2 text-[13px] text-[var(--error)]"
            >
              <LogOut className="size-3.5" aria-hidden />
              Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
