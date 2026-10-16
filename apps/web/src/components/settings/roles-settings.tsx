"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { LoadingState } from "@/components/shared/loading-error";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { AdminOnlyNotice, SettingsCard } from "@/components/settings/settings-card";
import { useWorkspace } from "@/hooks/use-workspace";
import { billingApi, rolesApi } from "@/lib/api/endpoints";
import type { components } from "@/lib/api/schema";

type Role = components["schemas"]["RoleRead"];
type PermissionInfo = components["schemas"]["PermissionInfo"];

function PermissionList({ granted, catalog }: { granted: string[]; catalog: PermissionInfo[] }) {
  if (!granted.length) {
    return <p className="text-[13px] text-[var(--on-surface-variant)]">View only. No changes allowed.</p>;
  }
  const labels = new Map(catalog.map((p) => [p.key, p.description]));
  return (
    <ul className="flex flex-wrap gap-1.5">
      {granted.map((key) => (
        <li
          key={key}
          title={key}
          className="rounded-full bg-[var(--surface-container)] px-2.5 py-0.5 text-[12px] text-[var(--on-surface-variant)]"
        >
          {labels.get(key) ?? key}
        </li>
      ))}
    </ul>
  );
}

function RoleDialog({
  open,
  role,
  catalog,
  grantable,
  onOpenChange,
}: {
  open: boolean;
  role: Role | null;
  catalog: PermissionInfo[];
  grantable: (key: string) => boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[560px]">
        {open ? (
          <RoleForm
            key={role?.id ?? "new"}
            role={role}
            catalog={catalog}
            grantable={grantable}
            onDone={() => onOpenChange(false)}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function RoleForm({
  role,
  catalog,
  grantable,
  onDone,
}: {
  role: Role | null;
  catalog: PermissionInfo[];
  grantable: (key: string) => boolean;
  onDone: () => void;
}) {
  const queryClient = useQueryClient();
  const [name, setName] = useState(role?.name ?? "");
  const [description, setDescription] = useState(role?.description ?? "");
  const [selected, setSelected] = useState<Set<string>>(new Set(role?.permissions ?? []));
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () => {
      const data = { name: name.trim(), description: description.trim() || null, permissions: [...selected] };
      return role?.id ? rolesApi.update(role.id, data) : rolesApi.create(data);
    },
    meta: { silent: true },
    onSuccess: (saved) => {
      void queryClient.invalidateQueries({ queryKey: ["roles"] });
      void queryClient.invalidateQueries({ queryKey: ["permissions"] });
      toast.success(role ? `Saved ${saved.name}` : `Created ${saved.name}`);
      onDone();
    },
    onError: (err) => setError(err.message),
  });

  function toggle(key: string, on: boolean) {
    setSelected((current) => {
      const next = new Set(current);
      if (on) next.add(key);
      else next.delete(key);
      return next;
    });
  }

  return (
    <form
      className="grid gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        setError(null);
        save.mutate();
      }}
    >
      <DialogHeader>
        <DialogTitle>{role ? `Edit ${role.name}` : "New role"}</DialogTitle>
        <DialogDescription>
          Give people with the member role exactly the permissions they need. Changes apply straight away.
        </DialogDescription>
      </DialogHeader>
      <div className="grid gap-1.5">
        <label htmlFor="role-name" className="text-[13px] font-medium">
          Name
        </label>
        <Input
          id="role-name"
          required
          maxLength={100}
          value={name}
          placeholder="e.g. Researcher"
          onChange={(event) => setName(event.target.value)}
        />
      </div>
      <div className="grid gap-1.5">
        <label htmlFor="role-description" className="text-[13px] font-medium">
          Description <span className="font-normal text-muted-foreground">(optional)</span>
        </label>
        <Textarea
          id="role-description"
          rows={2}
          maxLength={500}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />
      </div>
      <fieldset className="grid gap-2">
        <legend className="mb-1 text-[13px] font-medium">Permissions</legend>
        <div className="grid max-h-[280px] gap-1 overflow-y-auto pr-1 sm:grid-cols-2" tabIndex={0}>
          {catalog.map((permission) => {
            const allowed = grantable(permission.key);
            return (
              <label
                key={permission.key}
                className="flex items-start gap-2 rounded-md px-2 py-1.5 text-[13px] hover:bg-[var(--surface-container-low)]"
                title={allowed ? permission.key : "You can't grant a permission you don't have"}
              >
                <input
                  type="checkbox"
                  className="mt-0.5 size-4 cursor-pointer accent-[var(--primary)] disabled:cursor-not-allowed"
                  checked={selected.has(permission.key)}
                  disabled={!allowed}
                  onChange={(event) => toggle(permission.key, event.target.checked)}
                />
                <span className={allowed ? undefined : "text-[var(--on-surface-variant)]"}>
                  {permission.description}
                </span>
              </label>
            );
          })}
        </div>
      </fieldset>
      {error ? (
        <p
          role="alert"
          className="rounded-md bg-[var(--error-container)] px-3 py-2 text-[13px] text-[var(--on-error-container)]"
        >
          {error}
        </p>
      ) : null}
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onDone} disabled={save.isPending}>
          Cancel
        </Button>
        <Button type="submit" disabled={save.isPending || !name.trim()}>
          {save.isPending ? "Saving…" : role ? "Save role" : "Create role"}
        </Button>
      </DialogFooter>
    </form>
  );
}

export function RolesSettings() {
  const queryClient = useQueryClient();
  const { can } = useWorkspace();
  const canEdit = can("members.manage");
  const billing = useQuery({ queryKey: ["billing"], queryFn: billingApi.summary });
  const roles = useQuery({ queryKey: ["roles"], queryFn: rolesApi.list });
  const catalog = useQuery({ queryKey: ["permission-catalog"], queryFn: rolesApi.permissions, staleTime: Infinity });
  const [editing, setEditing] = useState<Role | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Role | null>(null);

  const remove = useMutation({
    mutationFn: (id: number) => rolesApi.remove(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["roles"] });
      void queryClient.invalidateQueries({ queryKey: ["members"] });
      toast.success(`Deleted ${deleteTarget?.name ?? "role"}`);
      setDeleteTarget(null);
    },
  });

  if (roles.isLoading || catalog.isLoading || billing.isLoading) return <LoadingState />;
  const features = (billing.data?.features ?? {}) as Record<string, boolean | number>;
  const customAllowed = Boolean(features.custom_roles);
  const permissions = catalog.data ?? [];
  const builtIn = (roles.data ?? []).filter((role) => role.built_in);
  const custom = (roles.data ?? []).filter((role) => !role.built_in);

  return (
    <div className="space-y-6">
      <SettingsCard
        id="built-in-roles"
        title="Built-in roles"
        description="Every workspace has these. Owners can do everything; admins can do everything except billing."
      >
        <ul className="divide-y divide-[var(--outline-variant)]">
          {builtIn.map((role) => (
            <li key={role.name} className="grid gap-2 py-3 sm:grid-cols-[120px_minmax(0,1fr)]">
              <p className="text-[14px] font-medium text-[var(--on-surface)]">{role.name}</p>
              <PermissionList granted={role.permissions} catalog={permissions} />
            </li>
          ))}
        </ul>
      </SettingsCard>

      <SettingsCard
        id="custom-roles"
        title="Custom roles"
        description="Give people with the member role a tailored set of permissions, such as read-only access or research without sending."
        actions={
          customAllowed && canEdit ? (
            <Button
              size="sm"
              onClick={() => {
                setEditing(null);
                setDialogOpen(true);
              }}
            >
              <Plus aria-hidden /> New role
            </Button>
          ) : null
        }
      >
        {!customAllowed ? (
          <p className="text-[13px] text-[var(--on-surface)]">
            Custom roles are included on the Enterprise plan. Your plan:{" "}
            <span className="font-medium capitalize">{billing.data?.plan ?? "free"}</span>.
          </p>
        ) : (
          <>
            {!canEdit ? <AdminOnlyNotice what="create or change roles" /> : null}
            {custom.length === 0 ? (
              <p className="text-[13px] text-[var(--on-surface-variant)]">
                No custom roles yet. Create one, then assign it on the Members page.
              </p>
            ) : (
              <ul className="divide-y divide-[var(--outline-variant)]">
                {custom.map((role) => (
                  <li key={role.id} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0 space-y-1.5">
                      <p className="text-[14px] font-medium text-[var(--on-surface)]">
                        {role.name}
                        <span className="ml-2 text-[12px] font-normal text-[var(--on-surface-variant)]">
                          {role.member_count} {role.member_count === 1 ? "member" : "members"}
                        </span>
                      </p>
                      {role.description ? (
                        <p className="text-[13px] text-[var(--on-surface-variant)]">{role.description}</p>
                      ) : null}
                      <PermissionList granted={role.permissions} catalog={permissions} />
                    </div>
                    {canEdit ? (
                      <div className="flex shrink-0 gap-1">
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          aria-label={`Edit ${role.name}`}
                          onClick={() => {
                            setEditing(role);
                            setDialogOpen(true);
                          }}
                        >
                          <Pencil aria-hidden />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          aria-label={`Delete ${role.name}`}
                          onClick={() => setDeleteTarget(role)}
                        >
                          <Trash2 aria-hidden />
                        </Button>
                      </div>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </SettingsCard>

      <RoleDialog
        open={dialogOpen}
        role={editing}
        catalog={permissions}
        grantable={can}
        onOpenChange={setDialogOpen}
      />
      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title={`Delete ${deleteTarget?.name ?? "this role"}?`}
        description="People with this role go back to the standard member permissions."
        confirmLabel="Delete role"
        destructive
        loading={remove.isPending}
        onConfirm={() => deleteTarget?.id && remove.mutate(deleteTarget.id)}
      />
    </div>
  );
}
