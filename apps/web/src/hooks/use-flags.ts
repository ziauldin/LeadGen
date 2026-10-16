"use client";

import { useQuery } from "@tanstack/react-query";
import { useWorkspace } from "@/hooks/use-workspace";
import { crmApi } from "@/lib/api/endpoints";

/** Optional features switched on for the current workspace. */
export function useFlags(): Record<string, boolean> {
  const { current } = useWorkspace();
  const { data } = useQuery({
    queryKey: ["flags", current?.id],
    queryFn: crmApi.flags,
    enabled: Boolean(current),
    staleTime: 5 * 60_000,
  });
  return data ?? {};
}
