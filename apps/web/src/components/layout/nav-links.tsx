"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { approvalsApi } from "@/lib/api/endpoints";
import { cn } from "@/lib/utils";
import { NAV_ITEMS, isActive } from "@/components/layout/nav-items";
import { useFlags } from "@/hooks/use-flags";
import { useWorkspace } from "@/hooks/use-workspace";

export function useApprovalCount() {
  const { current } = useWorkspace();
  const { data } = useQuery({
    queryKey: ["approvals", "count", current?.id],
    queryFn: () => approvalsApi.list({ limit: 1 }),
    enabled: Boolean(current),
    refetchInterval: 60_000,
  });
  return data?.total ?? 0;
}

export function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const approvals = useApprovalCount();
  const flags = useFlags();

  return (
    <nav aria-label="Main" className="flex-1 space-y-0.5 overflow-y-auto px-2">
      {NAV_ITEMS.filter((item) => !item.flag || flags[item.flag]).map((item) => {
        const active = isActive(pathname, item.href);
        const Icon = item.icon;
        const count = item.badge === "approvals" ? approvals : 0;
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cn(
              "mx-2 flex items-center gap-3 rounded-lg px-3 py-2 text-[13px] font-medium transition-colors duration-150",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)]",
              active
                ? "bg-[var(--primary-container)] font-semibold text-[var(--on-primary-container)]"
                : "text-[var(--on-surface-variant)] hover:bg-[var(--surface-container-high)]",
            )}
          >
            <Icon className="size-4 shrink-0" aria-hidden />
            <span className="flex-1">{item.label}</span>
            {count > 0 && (
              <span
                className="rounded-full bg-[var(--primary)] px-1.5 py-0.5 text-[10px] font-semibold leading-none text-white"
                aria-label={`${count} waiting`}
              >
                {count > 99 ? "99+" : count}
              </span>
            )}
          </Link>
        );
      })}
    </nav>
  );
}
