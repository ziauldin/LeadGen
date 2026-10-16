"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Eye, PauseCircle, PlayCircle } from "lucide-react";
import { Stat, percent } from "@/components/admin/admin-shell";
import { SettingsCard, formatDate } from "@/components/settings/settings-card";
import { ErrorState, LoadingState } from "@/components/shared/loading-error";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { adminApi } from "@/lib/api/endpoints";
import type { components } from "@/lib/api/schema";

type Detail = components["schemas"]["WorkspaceDetail"];

function ImpersonateDialog({ workspace, open, onOpenChange }: { workspace: Detail; open: boolean; onOpenChange: (open: boolean) => void }) {
  const [reason, setReason] = useState("");
  const [userId, setUserId] = useState<string>("owner");
  const [write, setWrite] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const memberItems: Record<string, string> = {
    owner: "A workspace owner",
    ...Object.fromEntries(workspace.members_list.map((m) => [String(m.user_id), `${m.name} (${m.role})`])),
  };

  const start = useMutation({
    mutationFn: () =>
      adminApi.impersonate(workspace.id, {
        reason: reason.trim(),
        write,
        minutes: 30,
        user_id: userId === "owner" ? null : Number(userId),
      }),
    meta: { silent: true },
    onSuccess: (session) => {
      const payload = encodeURIComponent(
        JSON.stringify({
          token: session.access_token,
          workspaceId: session.workspace_id,
          workspaceName: session.workspace_name,
          userName: session.user_name,
          userEmail: session.user_email,
          readOnly: session.read_only,
          expiresAt: session.expires_at,
        }),
      );
      window.open(`/impersonate#${payload}`, "_blank", "noopener");
      onOpenChange(false);
      setReason("");
      toast.success("Opened in a new tab. Your own session is unchanged.");
    },
    onError: (err) => setError(err.message),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[520px]">
        <form
          className="grid gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            setError(null);
            start.mutate();
          }}
        >
          <DialogHeader>
            <DialogTitle>View as a customer</DialogTitle>
            <DialogDescription>
              Opens {workspace.name} in a new tab for 30 minutes. The customer sees this in their audit log.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-1.5">
            <label id="impersonate-user-label" className="text-[13px] font-medium">
              Person
            </label>
            <Select value={userId} items={memberItems} onValueChange={(value) => setUserId(String(value ?? "owner"))}>
              <SelectTrigger className="w-full bg-white" aria-labelledby="impersonate-user-label">
                <SelectValue />
              </SelectTrigger>
              <SelectContent alignItemWithTrigger={false}>
                {Object.entries(memberItems).map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <label htmlFor="impersonate-reason" className="text-[13px] font-medium">
              Reason
            </label>
            <Textarea
              id="impersonate-reason"
              rows={2}
              required
              minLength={5}
              maxLength={500}
              value={reason}
              placeholder="e.g. Support ticket #1234: campaign stuck"
              onChange={(event) => setReason(event.target.value)}
            />
          </div>
          <label className="flex items-start gap-2 text-[13px]">
            <input
              type="checkbox"
              className="mt-0.5 size-4 accent-[var(--primary)]"
              checked={write}
              onChange={(event) => setWrite(event.target.checked)}
            />
            <span>
              Allow changes
              <span className="block text-[12px] text-[var(--on-surface-variant)]">
                Off by default. Security settings, access, billing and data requests stay locked either way.
              </span>
            </span>
          </label>
          {error ? (
            <p role="alert" className="rounded-md bg-[var(--error-container)] px-3 py-2 text-[13px] text-[var(--on-error-container)]">
              {error}
            </p>
          ) : null}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={start.isPending || reason.trim().length < 5}>
              Open as customer
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

const FLAG_STATE: Record<string, string> = { default: "Default", on: "On", off: "Off" };

export function AdminWorkspacePage({ id }: { id: number }) {
  const queryClient = useQueryClient();
  const workspace = useQuery({ queryKey: ["admin", "workspace", id], queryFn: () => adminApi.workspace(id) });
  const flags = useQuery({ queryKey: ["admin", "flags"], queryFn: adminApi.flags, staleTime: Infinity });
  const [impersonating, setImpersonating] = useState(false);
  const [suspendReason, setSuspendReason] = useState("");
  const [overridesText, setOverridesText] = useState<string | null>(null);
  const [overridesError, setOverridesError] = useState<string | null>(null);

  const onSaved = (detail: Detail) => {
    queryClient.setQueryData(["admin", "workspace", id], detail);
    void queryClient.invalidateQueries({ queryKey: ["admin", "workspaces"] });
  };
  const update = useMutation({
    mutationFn: (data: components["schemas"]["WorkspacePatch"]) => adminApi.updateWorkspace(id, data),
    onSuccess: (detail) => {
      onSaved(detail);
      setOverridesText(null);
      toast.success("Workspace updated");
    },
  });
  const suspend = useMutation({
    mutationFn: () => adminApi.suspend(id, suspendReason.trim()),
    onSuccess: (detail) => {
      onSaved(detail);
      setSuspendReason("");
      toast.success("Sending suspended");
    },
  });
  const unsuspend = useMutation({
    mutationFn: () => adminApi.unsuspend(id),
    onSuccess: (detail) => {
      onSaved(detail);
      toast.success("Sending resumed");
    },
  });

  if (workspace.isLoading) return <LoadingState />;
  if (workspace.error) return <ErrorState error={workspace.error} onRetry={() => void workspace.refetch()} />;
  const w = workspace.data!;
  const planItems = Object.fromEntries((flags.data?.plans ?? [w.plan]).map((p) => [p, p.charAt(0).toUpperCase() + p.slice(1)]));

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-[22px] font-semibold">{w.name}</h1>
          <p className="text-[13px] text-[var(--on-surface-variant)]">
            #{w.id} · Created {formatDate(w.created_at)} · Owner {w.owner_email ?? "—"}
          </p>
        </div>
        <Button onClick={() => setImpersonating(true)} disabled={Boolean(w.deleted_at)}>
          <Eye aria-hidden /> View as customer
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Stat label="Members" value={w.members} />
        <Stat label="Leads" value={w.leads.toLocaleString()} />
        <Stat label="Sent (30 days)" value={w.sent_30d.toLocaleString()} />
        <Stat label="Bounce rate" value={percent(w.bounce_rate_30d)} tone={w.bounce_rate_30d >= 0.05 ? "bad" : undefined} />
        <Stat label="Complaint rate" value={percent(w.complaint_rate_30d)} tone={w.complaint_rate_30d >= 0.003 ? "bad" : undefined} />
      </div>

      <SettingsCard title="Sending" description="Suspending stops every campaign from sending until resumed. Drafts and approvals keep working.">
        {w.sending_suspended_at ? (
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-[13px]">
              <span className="font-semibold text-[var(--error)]">Suspended</span> since {formatDate(w.sending_suspended_at)}
              {w.sending_suspended_reason ? `: ${w.sending_suspended_reason}` : ""}
            </p>
            <Button variant="outline" disabled={unsuspend.isPending} onClick={() => unsuspend.mutate()}>
              <PlayCircle aria-hidden /> Resume sending
            </Button>
          </div>
        ) : (
          <form
            className="flex flex-col gap-2 sm:flex-row sm:items-end"
            onSubmit={(event) => {
              event.preventDefault();
              if (suspendReason.trim().length >= 3) suspend.mutate();
            }}
          >
            <div className="grid flex-1 gap-1.5">
              <label htmlFor="suspend-reason" className="text-[13px] font-medium">
                Suspension reason
              </label>
              <Input id="suspend-reason" className="bg-white" value={suspendReason} maxLength={500} onChange={(e) => setSuspendReason(e.target.value)} />
            </div>
            <Button type="submit" variant="destructive" disabled={suspendReason.trim().length < 3 || suspend.isPending}>
              <PauseCircle aria-hidden /> Suspend sending
            </Button>
          </form>
        )}
      </SettingsCard>

      <SettingsCard title="Plan and limits">
        <div className="grid gap-5">
          <div className="grid gap-1.5">
            <label id="admin-plan-label" className="text-[13px] font-medium">
              Plan
            </label>
            <Select
              value={w.plan}
              items={planItems}
              disabled={update.isPending}
              onValueChange={(plan) => plan && plan !== w.plan && update.mutate({ plan: String(plan), note: "Plan changed by admin" })}
            >
              <SelectTrigger className="w-full bg-white sm:w-[220px]" aria-labelledby="admin-plan-label">
                <SelectValue />
              </SelectTrigger>
              <SelectContent alignItemWithTrigger={false}>
                {Object.entries(planItems).map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <div>
              <p className="mb-1 text-[13px] font-medium">Effective limits (used this period)</p>
              <ul className="text-[13px] text-[var(--on-surface-variant)]">
                {Object.entries(w.limits).map(([key, limit]) => (
                  <li key={key}>
                    {key.replace(/_/g, " ")}: {(w.usage[key] ?? 0).toLocaleString()} / {limit.toLocaleString()}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="mb-1 text-[13px] font-medium">Effective features</p>
              <ul className="text-[13px] text-[var(--on-surface-variant)]">
                {Object.entries(w.features).map(([key, value]) => (
                  <li key={key}>
                    {key.replace(/_/g, " ")}: {typeof value === "boolean" ? (value ? "yes" : "no") : value}
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <form
            className="grid gap-1.5"
            onSubmit={(event) => {
              event.preventDefault();
              try {
                const parsed = JSON.parse(overridesText || "{}") as Record<string, unknown>;
                setOverridesError(null);
                update.mutate({ plan_overrides: parsed, note: "Overrides changed by admin" });
              } catch {
                setOverridesError("That isn't valid JSON");
              }
            }}
          >
            <label htmlFor="plan-overrides" className="text-[13px] font-medium">
              Overrides (JSON)
            </label>
            <Textarea
              id="plan-overrides"
              rows={4}
              className="font-mono text-[12px]"
              value={overridesText ?? JSON.stringify(w.plan_overrides ?? {}, null, 2)}
              onChange={(event) => setOverridesText(event.target.value)}
            />
            <p className="text-[12px] text-[var(--on-surface-variant)]">
              e.g. {"{\"monthly_sends\": 75000, \"features\": {\"custom_roles\": true}}"}
            </p>
            {overridesError ? <p role="alert" className="text-[12px] text-[var(--error)]">{overridesError}</p> : null}
            <div>
              <Button type="submit" size="sm" variant="outline" disabled={overridesText === null || update.isPending}>
                Save overrides
              </Button>
            </div>
          </form>
        </div>
      </SettingsCard>

      <SettingsCard title="Feature flags" description="Override the server-wide setting for this workspace only.">
        <ul className="divide-y divide-[var(--outline-variant)]">
          {(flags.data?.flags ?? []).map((flag) => {
            const override = w.feature_flags?.[flag.key];
            const state = override === undefined || override === null ? "default" : override ? "on" : "off";
            return (
              <li key={flag.key} className="flex flex-col gap-2 py-2 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-[13px] font-medium">{flag.description}</p>
                  <p className="text-[12px] text-[var(--on-surface-variant)]">
                    <code className="font-mono">{flag.key}</code> · server default {flag.default ? "on" : "off"} · now{" "}
                    {w.effective_flags[flag.key] ? "on" : "off"}
                  </p>
                </div>
                <Select
                  value={state}
                  items={FLAG_STATE}
                  disabled={update.isPending}
                  onValueChange={(next) =>
                    next !== state &&
                    update.mutate({ feature_flags: { [flag.key]: next === "default" ? null : next === "on" } })
                  }
                >
                  <SelectTrigger size="sm" className="w-[130px] bg-white" aria-label={`${flag.description} flag`}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent alignItemWithTrigger={false}>
                    {Object.entries(FLAG_STATE).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </li>
            );
          })}
        </ul>
      </SettingsCard>

      <SettingsCard title="Members">
        <ul className="divide-y divide-[var(--outline-variant)]">
          {w.members_list.map((m) => (
            <li key={m.user_id} className="flex justify-between py-2 text-[13px]">
              <span>
                <span className="font-medium">{m.name}</span>{" "}
                <span className="text-[var(--on-surface-variant)]">{m.email}</span>
              </span>
              <span className="capitalize text-[var(--on-surface-variant)]">
                {m.role} · 2FA {m.mfa_enabled ? "on" : "off"}
              </span>
            </li>
          ))}
        </ul>
      </SettingsCard>

      <ImpersonateDialog workspace={w} open={impersonating} onOpenChange={setImpersonating} />
    </div>
  );
}
