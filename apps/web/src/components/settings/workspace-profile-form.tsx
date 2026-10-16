"use client";

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ErrorState } from "@/components/shared/loading-error";
import { AdminOnlyNotice, Field, SettingsCard, formatDate } from "@/components/settings/settings-card";
import { TimezoneSelect } from "@/components/settings/timezone-select";
import { useWorkspace } from "@/hooks/use-workspace";
import { workspacesApi } from "@/lib/api/endpoints";

const schema = z.object({
  name: z.string().trim().min(1, "Give your workspace a name").max(255, "Keep it under 255 characters"),
  timezone: z.string().min(1, "Pick a timezone"),
});
type Values = z.infer<typeof schema>;

export function WorkspaceProfileForm() {
  const queryClient = useQueryClient();
  const { hasRole } = useWorkspace();
  const canEdit = hasRole("admin");
  const current = useQuery({ queryKey: ["workspace-current"], queryFn: workspacesApi.current });

  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", timezone: "UTC" },
  });
  const { reset } = form;
  useEffect(() => {
    if (current.data) reset({ name: current.data.name, timezone: current.data.timezone });
  }, [current.data, reset]);

  const save = useMutation({
    mutationFn: (values: Values) => workspacesApi.update(values),
    onSuccess: (workspace) => {
      void queryClient.invalidateQueries({ queryKey: ["workspace-current"] });
      void queryClient.invalidateQueries({ queryKey: ["workspaces"] });
      reset({ name: workspace.name, timezone: workspace.timezone });
      toast.success("Workspace updated");
    },
  });

  const errors = form.formState.errors;

  return (
    <SettingsCard
      id="workspace-profile"
      title="Workspace"
      description="The name your team sees, and the timezone used for sending windows and daily limits."
    >
      {current.error ? (
        <ErrorState error={current.error} onRetry={() => void current.refetch()} />
      ) : (
        <form
          onSubmit={form.handleSubmit((values) => save.mutate(values))}
          className="space-y-4"
          aria-busy={current.isLoading}
        >
          {!canEdit ? <AdminOnlyNotice what="rename the workspace or change its timezone" /> : null}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Workspace name" htmlFor="ws-name" error={errors.name?.message} required>
              <Input
                id="ws-name"
                className="h-9 bg-white"
                disabled={!canEdit || current.isLoading}
                aria-invalid={Boolean(errors.name)}
                aria-describedby={errors.name ? "ws-name-error" : undefined}
                {...form.register("name")}
              />
            </Field>
            <Field
              label="Timezone"
              htmlFor="ws-timezone"
              error={errors.timezone?.message}
              hint="Campaign sending windows follow this unless a campaign sets its own."
            >
              <TimezoneSelect
                id="ws-timezone"
                current={current.data?.timezone}
                disabled={!canEdit || current.isLoading}
                aria-describedby="ws-timezone-hint"
                {...form.register("timezone")}
              />
            </Field>
          </div>
          {current.data ? (
            <dl className="grid gap-x-6 gap-y-1 text-[12px] text-[var(--on-surface-variant)] sm:grid-cols-3">
              <div>
                <dt className="inline">Plan: </dt>
                <dd className="inline font-medium capitalize text-[var(--on-surface)]">
                  {current.data.plan}
                </dd>
              </div>
              <div>
                <dt className="inline">Workspace ID: </dt>
                <dd className="inline font-mono text-[var(--on-surface)]">{current.data.slug}</dd>
              </div>
              <div>
                <dt className="inline">Created: </dt>
                <dd className="inline text-[var(--on-surface)]">{formatDate(current.data.created_at)}</dd>
              </div>
            </dl>
          ) : null}
          {canEdit ? (
            <div className="flex justify-end">
              <Button type="submit" disabled={!form.formState.isDirty || save.isPending}>
                {save.isPending ? "Saving…" : "Save workspace"}
              </Button>
            </div>
          ) : null}
        </form>
      )}
    </SettingsCard>
  );
}
