"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Laptop, Smartphone } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { ErrorState, LoadingState } from "@/components/shared/loading-error";
import { SettingsCard } from "@/components/settings/settings-card";
import { useAuth } from "@/hooks/use-auth";
import { useWorkspace } from "@/hooks/use-workspace";
import { authApi, workspacesApi } from "@/lib/api/endpoints";
import { getErrorMessage, setAccessToken } from "@/lib/api/client";

function describeDevice(userAgent: string | null): { label: string; mobile: boolean } {
  if (!userAgent) return { label: "Unknown device", mobile: false };
  const mobile = /iphone|android|mobile/i.test(userAgent);
  const browser = /edg\//i.test(userAgent)
    ? "Edge"
    : /chrome\//i.test(userAgent)
      ? "Chrome"
      : /firefox\//i.test(userAgent)
        ? "Firefox"
        : /safari\//i.test(userAgent)
          ? "Safari"
          : "Browser";
  const os = /windows/i.test(userAgent)
    ? "Windows"
    : /mac os/i.test(userAgent)
      ? "macOS"
      : /android/i.test(userAgent)
        ? "Android"
        : /iphone|ipad/i.test(userAgent)
          ? "iOS"
          : /linux/i.test(userAgent)
            ? "Linux"
            : "";
  return { label: os ? `${browser} on ${os}` : browser, mobile };
}

const when = (value: string) =>
  new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });

export function SessionsCard() {
  const queryClient = useQueryClient();
  const sessions = useQuery({ queryKey: ["sessions"], queryFn: authApi.sessions });
  const revoke = useMutation({
    mutationFn: authApi.revokeSession,
    onSuccess: () => {
      toast.success("Signed out that device");
      void queryClient.invalidateQueries({ queryKey: ["sessions"] });
    },
  });

  return (
    <SettingsCard
      title="Where you're signed in"
      description="Sign out of any device you don't recognise, then change your password."
    >
      {sessions.isLoading ? (
        <LoadingState />
      ) : sessions.error ? (
        <ErrorState error={sessions.error} onRetry={() => sessions.refetch()} />
      ) : (
        <ul className="divide-y divide-[var(--outline-variant)]">
          {(sessions.data ?? []).map((session) => {
            const device = describeDevice(session.user_agent);
            const Icon = device.mobile ? Smartphone : Laptop;
            return (
              <li key={session.id} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center">
                <Icon className="hidden size-5 text-[var(--on-surface-variant)] sm:block" aria-hidden />
                <div className="min-w-0 flex-1">
                  <p className="text-[13px] font-medium text-[var(--on-surface)]">
                    {device.label}
                    {session.current && (
                      <span className="ml-2 rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-800">
                        This device
                      </span>
                    )}
                  </p>
                  <p className="text-[12px] text-[var(--on-surface-variant)]">
                    Active {when(session.last_active_at)}
                    {session.ip ? ` · ${session.ip}` : ""} · signed in {when(session.signed_in_at)}
                  </p>
                </div>
                {!session.current && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => revoke.mutate(session.id)}
                    disabled={revoke.isPending}
                  >
                    Sign out
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </SettingsCard>
  );
}

export function ChangePasswordCard() {
  const queryClient = useQueryClient();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const mismatch = confirm.length > 0 && next !== confirm;
  const change = useMutation({
    mutationFn: () => authApi.changePassword(current, next),
    onSuccess: (result) => {
      setAccessToken(result.access_token ?? null);
      setCurrent("");
      setNext("");
      setConfirm("");
      void queryClient.invalidateQueries({ queryKey: ["sessions"] });
      toast.success("Password changed. Your other devices were signed out.");
    },
  });

  return (
    <SettingsCard title="Password" description="Changing it signs you out everywhere else.">
      <form
        className="grid max-w-md gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          change.mutate();
        }}
      >
        <label className="text-[13px] font-medium" htmlFor="current-password">Current password</label>
        <Input id="current-password" type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
        <label className="text-[13px] font-medium" htmlFor="new-password">New password</label>
        <Input id="new-password" type="password" autoComplete="new-password" minLength={8} value={next} onChange={(e) => setNext(e.target.value)} />
        <label className="text-[13px] font-medium" htmlFor="confirm-password">Confirm new password</label>
        <Input id="confirm-password" type="password" autoComplete="new-password" aria-invalid={mismatch} value={confirm} onChange={(e) => setConfirm(e.target.value)} />
        {mismatch && <p className="text-[12px] text-destructive">The passwords don&apos;t match.</p>}
        <div>
          <Button type="submit" disabled={!current || next.length < 8 || next !== confirm || change.isPending}>
            {change.isPending ? "Saving…" : "Change password"}
          </Button>
        </div>
      </form>
    </SettingsCard>
  );
}

export function WorkspaceTwoFactorPolicyCard() {
  const { current, hasRole } = useWorkspace();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const workspace = useQuery({ queryKey: ["workspace", "current"], queryFn: workspacesApi.current, enabled: hasRole("owner") });
  const update = useMutation({
    mutationFn: (value: boolean) => workspacesApi.update({ require_2fa: value }),
    onSuccess: (data) => {
      queryClient.setQueryData(["workspace", "current"], data);
      toast.success(data.require_2fa ? "Two-factor is now required" : "Two-factor is optional again");
    },
  });
  if (!current || !hasRole("owner")) return null;
  const required = workspace.data?.require_2fa ?? false;

  return (
    <SettingsCard
      title="Require two-factor for this workspace"
      description={`Everyone in ${current.name} must turn on two-factor authentication before they can use it.`}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <p className="flex-1 text-[13px] text-[var(--on-surface)]">
          {required ? "Required for all members." : "Optional."}
          {!user?.mfa_enabled && !required && " Turn it on for your own account first."}
        </p>
        <Button
          variant={required ? "outline" : "default"}
          disabled={update.isPending || workspace.isLoading || (!required && !user?.mfa_enabled)}
          onClick={() => update.mutate(!required)}
        >
          {required ? "Make optional" : "Require two-factor"}
        </Button>
      </div>
    </SettingsCard>
  );
}

export function DeleteAccountCard() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const remove = useMutation({
    mutationFn: () => authApi.deleteAccount(password, code),
    meta: { silent: true },
    onSuccess: async () => {
      toast.success("Your account was deleted");
      await logout();
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  return (
    <SettingsCard
      title="Delete account"
      description="Permanently delete your account. Workspaces where you're the only member are deleted too, including their leads, campaigns and emails. This can't be undone."
      className="border-destructive/40"
    >
      <Button variant="destructive" onClick={() => { setError(null); setPassword(""); setCode(""); setOpen(true); }}>
        Delete my account
      </Button>
      <ConfirmDialog
        open={open}
        onOpenChange={setOpen}
        title="Delete your account?"
        description={`This permanently deletes ${user?.email ?? "your account"}. If you own a workspace with other members, make someone else an owner first.`}
        confirmLabel="Delete forever"
        destructive
        loading={remove.isPending}
        confirmDisabled={!password || (Boolean(user?.mfa_enabled) && code.trim().length < 6)}
        onConfirm={() => remove.mutate()}
      >
        <div className="space-y-3">
          <Input type="password" aria-label="Password" placeholder="Password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          {user?.mfa_enabled && (
            <Input aria-label="Two-factor code" placeholder="Two-factor code" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} />
          )}
          {error && <p role="alert" className="text-[13px] text-destructive">{error}</p>}
        </div>
      </ConfirmDialog>
    </SettingsCard>
  );
}
