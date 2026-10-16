"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, type ReactNode } from "react";
import * as Sentry from "@sentry/nextjs";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getWorkspaceId, setWorkspaceId } from "@/lib/api/client";
import { rolesApi, workspacesApi } from "@/lib/api/endpoints";
import type { Workspace, WorkspaceRole } from "@/lib/api/types";
import { useAuth } from "@/hooks/use-auth";

const ROLE_RANK: Record<WorkspaceRole, number> = { member: 0, admin: 1, owner: 2 };

type WorkspaceContextValue = {
  workspaces: Workspace[];
  current: Workspace | null;
  loading: boolean;
  switchTo: (id: number) => Promise<void>;
  hasRole: (minimum: WorkspaceRole) => boolean;
  /** Whether the signed-in member's role (built-in or custom) grants `permission`. */
  can: (permission: string) => boolean;
  permissionsLoading: boolean;
};

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["workspaces"],
    queryFn: workspacesApi.list,
    enabled: Boolean(user),
    staleTime: 5 * 60_000,
  });

  const workspaces = useMemo(() => data?.items ?? [], [data]);
  const storedId = Number(getWorkspaceId()) || null;
  const current =
    workspaces.find((w) => w.id === storedId) ??
    workspaces.find((w) => w.id === data?.current_workspace_id) ??
    workspaces[0] ??
    null;

  // Keep the stored id valid (e.g. after being removed from a workspace).
  useEffect(() => {
    if (current && current.id !== storedId) setWorkspaceId(current.id);
    Sentry.setTag("workspace_id", current ? String(current.id) : undefined);
  }, [current, storedId]);

  const switchTo = useCallback(
    async (id: number) => {
      await workspacesApi.switch(id);
      setWorkspaceId(id);
      // Everything cached belongs to the old workspace.
      queryClient.clear();
      await queryClient.invalidateQueries();
    },
    [queryClient],
  );

  const mine = useQuery({
    queryKey: ["permissions", current?.id],
    queryFn: rolesApi.mine,
    enabled: Boolean(user && current),
    staleTime: 60_000,
  });
  const granted = useMemo(() => new Set(mine.data?.permissions ?? []), [mine.data]);
  const can = useCallback((permission: string) => granted.has(permission), [granted]);

  const hasRole = useCallback(
    (minimum: WorkspaceRole) =>
      current ? ROLE_RANK[current.role as WorkspaceRole] >= ROLE_RANK[minimum] : false,
    [current],
  );

  const value = useMemo(
    () => ({
      workspaces,
      current,
      loading: isLoading,
      switchTo,
      hasRole,
      can,
      permissionsLoading: mine.isLoading,
    }),
    [workspaces, current, isLoading, switchTo, hasRole, can, mine.isLoading],
  );
  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace() {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("useWorkspace must be used within WorkspaceProvider");
  return ctx;
}
