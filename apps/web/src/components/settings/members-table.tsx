"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { UserMinus } from "lucide-react";
import { DataTable, type DataTableColumn } from "@/components/data-table/data-table";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { EmptyState } from "@/components/shared/empty-state";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { SettingsCard, formatDate } from "@/components/settings/settings-card";
import { useAuth } from "@/hooks/use-auth";
import { useWorkspace } from "@/hooks/use-workspace";
import { rolesApi, workspacesApi } from "@/lib/api/endpoints";
import type { Member, WorkspaceRole } from "@/lib/api/types";

const ROLE_RANK: Record<WorkspaceRole, number> = { member: 0, admin: 1, owner: 2 };
export const ROLE_LABELS: Record<WorkspaceRole, string> = {
  owner: "Owner",
  admin: "Admin",
  member: "Member",
};
export const ROLE_HINTS: Record<WorkspaceRole, string> = {
  owner: "Everything, including billing and deleting the workspace.",
  admin: "Manage settings, sending accounts and the team.",
  member: "Find leads, write and approve emails, run campaigns.",
};

type Row = Member & { id: number };

function RoleBadge({ role }: { role: WorkspaceRole }) {
  const styles: Record<WorkspaceRole, string> = {
    owner: "bg-[var(--primary-fixed)] text-[var(--on-primary-fixed)]",
    admin: "bg-[var(--secondary-fixed)] text-[var(--on-secondary-fixed)]",
    member: "bg-[var(--surface-container)] text-[var(--on-surface-variant)]",
  };
  return (
    <span className={`inline-flex rounded-full px-2.5 py-0.5 text-[12px] font-semibold ${styles[role]}`}>
      {ROLE_LABELS[role]}
    </span>
  );
}

export function MembersTable() {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const { current } = useWorkspace();
  const myRole = (current?.role ?? "member") as WorkspaceRole;
  const isAdmin = ROLE_RANK[myRole] >= ROLE_RANK.admin;
  const [removeTarget, setRemoveTarget] = useState<Member | null>(null);
  const [removeError, setRemoveError] = useState<string | null>(null);

  const members = useQuery({ queryKey: ["members"], queryFn: workspacesApi.members });
  const rows = useMemo<Row[] | undefined>(
    () => members.data?.map((member) => ({ ...member, id: member.user_id })),
    [members.data],
  );

  const roles = useQuery({ queryKey: ["roles"], queryFn: rolesApi.list });
  const customRoles = useMemo(() => (roles.data ?? []).filter((role) => !role.built_in), [roles.data]);

  const changeRole = useMutation({
    mutationFn: ({ userId, role }: { userId: number; role: WorkspaceRole }) =>
      workspacesApi.updateMember(userId, { role }),
    onSuccess: (member) => {
      void queryClient.invalidateQueries({ queryKey: ["members"] });
      toast.success(`${member.name} is now ${ROLE_LABELS[member.role].toLowerCase()}`);
    },
  });

  const changeCustomRole = useMutation({
    mutationFn: ({ userId, roleId }: { userId: number; roleId: number | null }) =>
      workspacesApi.updateMember(userId, { custom_role_id: roleId }),
    onSuccess: (member) => {
      void queryClient.invalidateQueries({ queryKey: ["members"] });
      void queryClient.invalidateQueries({ queryKey: ["roles"] });
      toast.success(
        member.custom_role
          ? `${member.name} now has the ${member.custom_role} role`
          : `${member.name} is back on the standard member permissions`,
      );
    },
  });

  const remove = useMutation({
    mutationFn: (userId: number) => workspacesApi.removeMember(userId),
    meta: { silent: true },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["members"] });
      void queryClient.invalidateQueries({ queryKey: ["billing"] });
      toast.success(`${removeTarget?.name ?? "Member"} was removed`);
      setRemoveTarget(null);
    },
    onError: (error) => setRemoveError(error.message),
  });

  /** Mirrors the API's rules so we only offer actions that will work. */
  function canManage(member: Member) {
    if (!isAdmin || member.user_id === user?.id) return false;
    if (myRole === "owner") return true;
    return ROLE_RANK[member.role] < ROLE_RANK[myRole];
  }

  function roleOptions(member: Member): WorkspaceRole[] {
    if (myRole === "owner") return ["owner", "admin", "member"];
    return member.role === "owner" ? [] : ["admin", "member"];
  }

  const columns = useMemo<DataTableColumn<Row>[]>(
    () => [
      {
        id: "name",
        header: "Name",
        cell: ({ row }) => (
          <div className="min-w-[160px]">
            <p className="font-medium text-[var(--on-surface)]">
              {row.original.name}
              {row.original.user_id === user?.id ? (
                <span className="ml-2 text-[12px] font-normal text-[var(--on-surface-variant)]">(you)</span>
              ) : null}
            </p>
            <p className="text-[12px] text-[var(--on-surface-variant)] sm:hidden">{row.original.email}</p>
          </div>
        ),
      },
      {
        id: "email",
        header: "Email",
        className: "hidden sm:table-cell",
        cell: ({ row }) => <span className="text-[var(--on-surface-variant)]">{row.original.email}</span>,
      },
      {
        id: "role",
        header: "Role",
        cell: ({ row }) => {
          const member = row.original;
          if (!canManage(member)) return <RoleBadge role={member.role} />;
          const options = roleOptions(member);
          const items = Object.fromEntries(options.map((role) => [role, ROLE_LABELS[role]]));
          return (
            <Select
              value={member.role}
              items={items}
              onValueChange={(value) =>
                value &&
                value !== member.role &&
                changeRole.mutate({ userId: member.user_id, role: value as WorkspaceRole })
              }
              disabled={changeRole.isPending}
            >
              <SelectTrigger
                size="sm"
                className="w-[120px] bg-white"
                aria-label={`Role for ${member.name}`}
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent alignItemWithTrigger={false}>
                {options.map((role) => (
                  <SelectItem key={role} value={role}>
                    {ROLE_LABELS[role]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          );
        },
      },
      ...(customRoles.length
        ? [
            {
              id: "custom_role",
              header: "Custom role",
              className: "hidden md:table-cell",
              cell: ({ row }: { row: { original: Row } }) => {
                const member = row.original;
                if (member.role !== "member") {
                  return <span className="text-[var(--on-surface-variant)]">—</span>;
                }
                if (!canManage(member)) {
                  return (
                    <span className="text-[var(--on-surface-variant)]">{member.custom_role ?? "Standard"}</span>
                  );
                }
                const items: Record<string, string> = {
                  none: "Standard",
                  ...Object.fromEntries(customRoles.map((role) => [String(role.id), role.name])),
                };
                return (
                  <Select
                    value={member.custom_role_id ? String(member.custom_role_id) : "none"}
                    items={items}
                    onValueChange={(value) => {
                      const roleId = !value || value === "none" ? null : Number(value);
                      if (roleId !== (member.custom_role_id ?? null)) {
                        changeCustomRole.mutate({ userId: member.user_id, roleId });
                      }
                    }}
                    disabled={changeCustomRole.isPending}
                  >
                    <SelectTrigger
                      size="sm"
                      className="w-[150px] bg-white"
                      aria-label={`Custom role for ${member.name}`}
                    >
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent alignItemWithTrigger={false}>
                      {Object.entries(items).map(([value, label]) => (
                        <SelectItem key={value} value={value}>
                          {label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                );
              },
            } satisfies DataTableColumn<Row>,
          ]
        : []),
      {
        id: "joined",
        header: "Joined",
        className: "hidden md:table-cell whitespace-nowrap",
        cell: ({ row }) => (
          <span className="text-[var(--on-surface-variant)]">{formatDate(row.original.joined_at)}</span>
        ),
      },
      {
        id: "actions",
        header: () => <span className="sr-only">Actions</span>,
        className: "w-12 text-right",
        cell: ({ row }) =>
          canManage(row.original) ? (
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={`Remove ${row.original.name}`}
              onClick={() => {
                setRemoveError(null);
                setRemoveTarget(row.original);
              }}
            >
              <UserMinus aria-hidden />
            </Button>
          ) : null,
      },
    ],
    // canManage/roleOptions only depend on these values.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [user?.id, myRole, isAdmin, changeRole.isPending, changeCustomRole.isPending, customRoles],
  );

  const count = rows?.length ?? 0;

  return (
    <SettingsCard
      id="members"
      title="Members"
      description={
        <>
          {Object.entries(ROLE_HINTS).map(([role, hint]) => (
            <span key={role} className="block">
              <span className="font-medium text-[var(--on-surface)]">{ROLE_LABELS[role as WorkspaceRole]}:</span>{" "}
              {hint}
            </span>
          ))}
        </>
      }
    >
      <DataTable<Row>
        caption="Workspace members"
        columns={columns}
        data={rows}
        total={count}
        page={0}
        pageSize={Math.max(count, 1)}
        onPageChange={() => undefined}
        isLoading={members.isLoading}
        error={members.error}
        onRetry={() => void members.refetch()}
        emptyState={
          <div className="p-4">
            <EmptyState title="No members" description="Invite your team below." />
          </div>
        }
      />

      <ConfirmDialog
        open={removeTarget !== null}
        onOpenChange={(open) => {
          if (!open) {
            setRemoveTarget(null);
            setRemoveError(null);
          }
        }}
        title={`Remove ${removeTarget?.name ?? "this member"}?`}
        description="They'll lose access to this workspace straight away. Their past work stays."
        confirmLabel="Remove member"
        destructive
        loading={remove.isPending}
        onConfirm={() => removeTarget && remove.mutate(removeTarget.user_id)}
      >
        {removeError ? (
          <p role="alert" className="rounded-md bg-[var(--error-container)] px-3 py-2 text-[13px] text-[var(--on-error-container)]">
            {removeError}
          </p>
        ) : null}
      </ConfirmDialog>
    </SettingsCard>
  );
}
