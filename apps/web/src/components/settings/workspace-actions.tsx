"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { LogOut, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { Field, SettingsCard } from "@/components/settings/settings-card";
import { TimezoneSelect } from "@/components/settings/timezone-select";
import { useAuth } from "@/hooks/use-auth";
import { useWorkspace } from "@/hooks/use-workspace";
import { setWorkspaceId } from "@/lib/api/client";
import { workspacesApi } from "@/lib/api/endpoints";

const createSchema = z.object({
  name: z.string().trim().min(1, "Give the workspace a name").max(255, "Keep it under 255 characters"),
  timezone: z.string().min(1),
});
type CreateValues = z.infer<typeof createSchema>;

function browserTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

function CreateWorkspaceDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const router = useRouter();
  const { switchTo } = useWorkspace();
  const form = useForm<CreateValues>({
    resolver: zodResolver(createSchema),
    defaultValues: { name: "", timezone: browserTimezone() },
  });

  const create = useMutation({
    mutationFn: (values: CreateValues) => workspacesApi.create(values),
    onSuccess: async (workspace) => {
      toast.success(`Created ${workspace.name}`);
      onOpenChange(false);
      form.reset();
      await switchTo(workspace.id);
      router.push("/dashboard");
    },
  });

  return (
    <Dialog open={open} onOpenChange={(next) => !create.isPending && onOpenChange(next)}>
      <DialogContent className="sm:max-w-[460px]">
        <DialogHeader>
          <DialogTitle>Create a new workspace</DialogTitle>
          <DialogDescription>
            Workspaces keep leads, campaigns, sending accounts and team members completely
            separate, e.g. one per client or brand. You&apos;ll be its owner.
          </DialogDescription>
        </DialogHeader>
        <form
          id="create-workspace-form"
          onSubmit={form.handleSubmit((values) => create.mutate(values))}
          className="space-y-4"
        >
          <Field
            label="Name"
            htmlFor="new-ws-name"
            error={form.formState.errors.name?.message}
            required
          >
            <Input
              id="new-ws-name"
              className="h-9 bg-white"
              placeholder="Acme outreach"
              autoFocus
              aria-invalid={Boolean(form.formState.errors.name)}
              {...form.register("name")}
            />
          </Field>
          <Field label="Timezone" htmlFor="new-ws-timezone">
            <TimezoneSelect
              id="new-ws-timezone"
              current={browserTimezone()}
              {...form.register("timezone")}
            />
          </Field>
        </form>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={create.isPending}>
            Cancel
          </Button>
          <Button type="submit" form="create-workspace-form" disabled={create.isPending}>
            {create.isPending ? "Creating…" : "Create workspace"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function WorkspaceActions() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { isVerified } = useAuth();
  const { current, workspaces } = useWorkspace();
  const [createOpen, setCreateOpen] = useState(false);
  const [leaveOpen, setLeaveOpen] = useState(false);

  const leave = useMutation({
    mutationFn: workspacesApi.leave,
    onSuccess: async () => {
      setLeaveOpen(false);
      toast.success(`You left ${current?.name ?? "the workspace"}`);
      // Forget the old workspace; the app picks another one you belong to.
      setWorkspaceId(null);
      queryClient.clear();
      await queryClient.invalidateQueries();
      router.push("/dashboard");
    },
  });

  const onlyWorkspace = workspaces.length <= 1;

  return (
    <SettingsCard
      id="workspace-actions"
      title="Workspaces"
      description="Create another workspace, or leave this one."
    >
      <div className="divide-y divide-[var(--outline-variant)]">
        <div className="flex flex-col gap-3 pb-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-[13px] font-medium text-[var(--on-surface)]">New workspace</p>
            <p className="text-[12px] text-[var(--on-surface-variant)]">
              {isVerified
                ? "Start fresh with separate leads, campaigns and team."
                : "Verify your email address first to create a workspace."}
            </p>
          </div>
          <Button variant="outline" onClick={() => setCreateOpen(true)} disabled={!isVerified}>
            <Plus aria-hidden />
            Create workspace
          </Button>
        </div>
        <div className="flex flex-col gap-3 pt-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-[13px] font-medium text-[var(--on-surface)]">Leave workspace</p>
            <p className="text-[12px] text-[var(--on-surface-variant)]">
              {onlyWorkspace
                ? "This is your only workspace. Create or join another before leaving."
                : "You'll lose access to its leads, campaigns and replies. A workspace must keep at least one owner."}
            </p>
          </div>
          <Button variant="destructive" onClick={() => setLeaveOpen(true)} disabled={onlyWorkspace}>
            <LogOut aria-hidden />
            Leave
          </Button>
        </div>
      </div>

      <CreateWorkspaceDialog open={createOpen} onOpenChange={setCreateOpen} />
      <ConfirmDialog
        open={leaveOpen}
        onOpenChange={setLeaveOpen}
        title={`Leave ${current?.name ?? "this workspace"}?`}
        description="You'll need a new invitation to get back in."
        confirmLabel="Leave workspace"
        destructive
        loading={leave.isPending}
        onConfirm={() => leave.mutate()}
      />
    </SettingsCard>
  );
}
