"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { notificationsApi } from "@/lib/api/endpoints";

function timeAgo(value: string) {
  const minutes = Math.round((Date.now() - new Date(value).getTime()) / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  return new Date(value).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

/** The bell: unread count polled every 30 seconds, newest notifications in a menu. */
export function NotificationBell() {
  const queryClient = useQueryClient();
  const notifications = useQuery({
    queryKey: ["notifications"],
    queryFn: () => notificationsApi.list(),
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  });
  const markRead = useMutation({
    mutationFn: (payload: { ids?: number[]; all?: boolean }) => notificationsApi.markRead(payload),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });
  const unread = notifications.data?.unread ?? 0;
  const items = notifications.data?.items ?? [];

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className="relative flex size-9 items-center justify-center rounded-lg text-[var(--on-surface-variant)] hover:bg-[var(--surface-container-low)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)]"
        aria-label={unread ? `Notifications (${unread} unread)` : "Notifications"}
      >
        <Bell className="size-5" aria-hidden />
        {unread ? (
          <span
            aria-hidden
            className="absolute right-0.5 top-0.5 flex min-w-4 items-center justify-center rounded-full bg-[var(--error)] px-1 text-[10px] font-bold leading-4 text-white"
          >
            {unread > 9 ? "9+" : unread}
          </span>
        ) : null}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80 p-0">
        <div className="flex items-center justify-between border-b border-[var(--outline-variant)] px-3 py-2">
          <p className="text-[13px] font-semibold">Notifications</p>
          {unread ? (
            <Button variant="ghost" size="xs" onClick={() => markRead.mutate({ all: true })}>
              Mark all as read
            </Button>
          ) : null}
        </div>
        {items.length ? (
          <ul className="max-h-96 divide-y divide-[var(--outline-variant)] overflow-y-auto">
            {items.map((item) => {
              const content = (
                <>
                  <p className={`text-[13px] ${item.read ? "" : "font-semibold"}`}>{item.title}</p>
                  {item.body ? <p className="mt-0.5 line-clamp-2 text-[12px] text-[var(--on-surface-variant)]">{item.body}</p> : null}
                  <p className="mt-1 text-[11px] text-[var(--on-surface-variant)]">{timeAgo(item.created_at)}</p>
                </>
              );
              const onOpen = () => !item.read && markRead.mutate({ ids: [item.id] });
              return (
                <li key={item.id} className={item.read ? "" : "bg-[var(--surface-container-low)]"}>
                  {item.link ? (
                    <Link href={item.link} onClick={onOpen} className="block px-3 py-2.5 hover:bg-[var(--surface-container)]">
                      {content}
                    </Link>
                  ) : (
                    <button type="button" onClick={onOpen} className="block w-full px-3 py-2.5 text-left hover:bg-[var(--surface-container)]">
                      {content}
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="px-3 py-6 text-center text-[13px] text-[var(--on-surface-variant)]">You&apos;re all caught up.</p>
        )}
        <div className="border-t border-[var(--outline-variant)] px-3 py-2 text-right">
          <Link href="/settings/notifications" className="text-[12px] text-[var(--primary)] hover:underline">
            Notification settings
          </Link>
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
