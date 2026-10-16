"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Search, Trash2 } from "lucide-react";
import { Stat, percent } from "@/components/admin/admin-shell";
import { describeAction } from "@/components/settings/audit-log-table";
import { SettingsCard, formatDate } from "@/components/settings/settings-card";
import { ErrorState, LoadingState } from "@/components/shared/loading-error";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { adminApi } from "@/lib/api/endpoints";

function SearchBox({ id, label, value, onChange }: { id: string; label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div className="relative w-full sm:max-w-sm">
      <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-[var(--on-surface-variant)]" aria-hidden />
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <Input id={id} type="search" value={value} placeholder={label} onChange={(e) => onChange(e.target.value)} className="h-9 bg-white pl-8" />
    </div>
  );
}

function Table({ caption, head, children }: { caption: string; head: string[]; children: React.ReactNode }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--outline-variant)] bg-white" tabIndex={0}>
      <table className="w-full min-w-[720px] text-left text-[13px]">
        <caption className="sr-only">{caption}</caption>
        <thead className="bg-[var(--surface-container-low)] text-[12px] text-[var(--on-surface-variant)]">
          <tr>
            {head.map((h) => (
              <th key={h} scope="col" className="px-3 py-2 font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--outline-variant)]">{children}</tbody>
      </table>
    </div>
  );
}

export function AdminOverviewPage() {
  const overview = useQuery({ queryKey: ["admin", "overview"], queryFn: adminApi.overview });
  const health = useQuery({ queryKey: ["admin", "health"], queryFn: adminApi.health, refetchInterval: 30_000 });
  if (overview.isLoading) return <LoadingState />;
  if (overview.error) return <ErrorState error={overview.error} onRetry={() => void overview.refetch()} />;
  const o = overview.data!;
  return (
    <div className="space-y-6">
      <h1 className="text-[22px] font-semibold">Overview</h1>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Users" value={o.users.toLocaleString()} />
        <Stat label="New users (7 days)" value={o.new_users_7d.toLocaleString()} />
        <Stat label="Workspaces" value={o.workspaces.toLocaleString()} />
        <Stat label="Active workspaces (7 days)" value={o.active_workspaces_7d.toLocaleString()} />
        <Stat label="Emails sent (24 hours)" value={o.emails_sent_24h.toLocaleString()} />
        <Stat label="Emails sent (7 days)" value={o.emails_sent_7d.toLocaleString()} />
        <Stat label="Replies (7 days)" value={o.replies_7d.toLocaleString()} />
        <Stat label="Suspended workspaces" value={o.suspended_workspaces} tone={o.suspended_workspaces ? "bad" : undefined} />
      </div>
      <SettingsCard title="Workspaces by plan">
        <ul className="flex flex-wrap gap-2">
          {Object.entries(o.workspaces_by_plan).map(([plan, count]) => (
            <li key={plan} className="rounded-full bg-[var(--surface-container)] px-3 py-1 text-[13px] capitalize">
              {plan}: <span className="font-semibold">{count}</span>
            </li>
          ))}
        </ul>
      </SettingsCard>
      <SettingsCard title="System health" description="Refreshes every 30 seconds.">
        {health.data ? (
          <div className="space-y-4">
            <ul className="flex flex-wrap gap-2">
              {Object.entries(health.data.checks).map(([name, check]) => (
                <li
                  key={name}
                  className={`rounded-full px-3 py-1 text-[13px] capitalize ${check.ok ? "bg-[var(--primary-fixed)] text-[var(--on-primary-fixed)]" : "bg-[var(--error-container)] text-[var(--on-error-container)]"}`}
                  title={check.detail ?? undefined}
                >
                  {name}: {check.ok ? "OK" : (check.detail ?? "Down")}
                </li>
              ))}
            </ul>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
              <Stat label="Queued emails" value={health.data.queued_emails} />
              <Stat label="Failed emails (24 hours)" value={health.data.failed_emails_24h} tone={health.data.failed_emails_24h ? "bad" : undefined} />
              <Stat label="Providers in error" value={health.data.provider_errors} tone={health.data.provider_errors ? "bad" : undefined} />
              <Stat label="Webhooks pending" value={health.data.webhooks_pending} />
              <Stat label="Webhooks failed (24 hours)" value={health.data.webhooks_failed_24h} tone={health.data.webhooks_failed_24h ? "bad" : undefined} />
              <Stat label="Open data requests" value={health.data.data_requests_open} />
            </div>
          </div>
        ) : (
          <LoadingState />
        )}
      </SettingsCard>
    </div>
  );
}

export function AdminWorkspacesPage() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const workspaces = useQuery({
    queryKey: ["admin", "workspaces", search, page],
    queryFn: () => adminApi.workspaces({ search: search.trim() || undefined, skip: page * 50, limit: 50 }),
    placeholderData: (previous) => previous,
  });
  const total = workspaces.data?.total ?? 0;
  return (
    <div className="space-y-4">
      <h1 className="text-[22px] font-semibold">Workspaces</h1>
      <SearchBox id="admin-workspace-search" label="Search by name or member email" value={search} onChange={(v) => { setSearch(v); setPage(0); }} />
      {workspaces.isLoading ? (
        <LoadingState />
      ) : (
        <Table caption="Workspaces" head={["Workspace", "Plan", "Owner", "Members", "Leads", "Sent (30d)", "Bounce", "Complaints", "Status", "Created"]}>
          {workspaces.data?.items.map((w) => (
            <tr key={w.id}>
              <th scope="row" className="px-3 py-2 font-medium">
                <Link href={`/admin/workspaces/${w.id}`} className="text-[var(--primary)] underline-offset-2 hover:underline">
                  {w.name}
                </Link>
              </th>
              <td className="px-3 py-2 capitalize">{w.plan}</td>
              <td className="px-3 py-2">{w.owner_email ?? "—"}</td>
              <td className="px-3 py-2">{w.members}</td>
              <td className="px-3 py-2">{w.leads.toLocaleString()}</td>
              <td className="px-3 py-2">{w.sent_30d.toLocaleString()}</td>
              <td className={`px-3 py-2 ${w.bounce_rate_30d >= 0.05 ? "font-semibold text-[var(--error)]" : ""}`}>{percent(w.bounce_rate_30d)}</td>
              <td className={`px-3 py-2 ${w.complaint_rate_30d >= 0.003 ? "font-semibold text-[var(--error)]" : ""}`}>{percent(w.complaint_rate_30d)}</td>
              <td className="px-3 py-2">{w.deleted_at ? "Deleted" : w.sending_suspended_at ? "Suspended" : "Active"}</td>
              <td className="px-3 py-2 whitespace-nowrap">{formatDate(w.created_at)}</td>
            </tr>
          ))}
        </Table>
      )}
      <div className="flex items-center justify-between text-[13px] text-[var(--on-surface-variant)]">
        <span>{total.toLocaleString()} workspaces</span>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</Button>
          <Button size="sm" variant="outline" disabled={(page + 1) * 50 >= total} onClick={() => setPage(page + 1)}>Next</Button>
        </div>
      </div>
    </div>
  );
}

export function AdminUsersPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const users = useQuery({
    queryKey: ["admin", "users", search],
    queryFn: () => adminApi.users({ search: search.trim() || undefined, limit: 100 }),
    placeholderData: (previous) => previous,
  });
  const toggle = useMutation({
    mutationFn: ({ id, active }: { id: number; active: boolean }) => adminApi.setUserActive(id, active),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
      toast.success(result.is_active ? "Account enabled" : "Account disabled and signed out everywhere");
    },
  });
  return (
    <div className="space-y-4">
      <h1 className="text-[22px] font-semibold">Users</h1>
      <SearchBox id="admin-user-search" label="Search by name or email" value={search} onChange={setSearch} />
      {users.isLoading ? (
        <LoadingState />
      ) : (
        <Table caption="Users" head={["Name", "Email", "Workspaces", "2FA", "Verified", "Joined", "Status", ""]}>
          {users.data?.items.map((u) => (
            <tr key={u.id}>
              <th scope="row" className="px-3 py-2 font-medium">
                {u.name}
                {u.is_superuser ? <span className="ml-2 rounded bg-[var(--surface-container)] px-1.5 text-[11px]">Admin</span> : null}
              </th>
              <td className="px-3 py-2">{u.email}</td>
              <td className="px-3 py-2">{u.workspaces}</td>
              <td className="px-3 py-2">{u.mfa_enabled ? "On" : "Off"}</td>
              <td className="px-3 py-2">{u.email_verified_at ? "Yes" : "No"}</td>
              <td className="px-3 py-2 whitespace-nowrap">{formatDate(u.created_at)}</td>
              <td className="px-3 py-2">{u.is_active ? "Active" : "Disabled"}</td>
              <td className="px-3 py-2 text-right">
                {!u.is_superuser ? (
                  <Button size="sm" variant="outline" disabled={toggle.isPending} onClick={() => toggle.mutate({ id: u.id, active: !u.is_active })}>
                    {u.is_active ? "Disable" : "Enable"}
                  </Button>
                ) : null}
              </td>
            </tr>
          ))}
        </Table>
      )}
    </div>
  );
}

export function AdminAbusePage() {
  const abuse = useQuery({ queryKey: ["admin", "abuse"], queryFn: adminApi.abuse });
  if (abuse.isLoading) return <LoadingState />;
  const data = abuse.data!;
  return (
    <div className="space-y-6">
      <h1 className="text-[22px] font-semibold">Abuse review</h1>
      <SettingsCard
        title="Sending reputation"
        description="Workspaces with at least 20 sends in 7 days and a bounce rate of 5% or a complaint rate of 0.3% or more."
      >
        {data.sending.length ? (
          <ul className="divide-y divide-[var(--outline-variant)]">
            {data.sending.map((w) => (
              <li key={w.workspace_id} className="flex flex-col gap-1 py-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <Link href={`/admin/workspaces/${w.workspace_id}`} className="font-medium text-[var(--primary)] hover:underline">
                    {w.name}
                  </Link>
                  <p className="text-[12px] text-[var(--on-surface-variant)]">
                    {w.reasons.join(" · ")} · {w.sent_7d} sent, {w.bounced_7d} bounced, {w.complained_7d} complaints
                  </p>
                </div>
                <span className="text-[12px] font-semibold">{w.suspended ? "Suspended" : "Sending"}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[13px] text-[var(--on-surface-variant)]">Nothing to review.</p>
        )}
      </SettingsCard>
      <SettingsCard title="Suspicious sign-ups" description="Last 14 days: disposable email domains, or not verified after 3 days.">
        {data.signups.length ? (
          <ul className="divide-y divide-[var(--outline-variant)]">
            {data.signups.map((u) => (
              <li key={u.user_id} className="py-3">
                <p className="font-medium">
                  {u.name} <span className="font-normal text-[var(--on-surface-variant)]">{u.email}</span>
                </p>
                <p className="text-[12px] text-[var(--on-surface-variant)]">
                  {u.reasons.join(" · ")} · Joined {formatDate(u.created_at)} · {u.is_active ? "Active" : "Disabled"}
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[13px] text-[var(--on-surface-variant)]">Nothing to review.</p>
        )}
      </SettingsCard>
    </div>
  );
}

export function AdminSuppressionsPage() {
  const queryClient = useQueryClient();
  const [value, setValue] = useState("");
  const [reason, setReason] = useState("");
  const list = useQuery({ queryKey: ["admin", "suppressions"], queryFn: () => adminApi.suppressions() });
  const add = useMutation({
    mutationFn: () => {
      const v = value.trim();
      return adminApi.addSuppression(v.includes("@") && !v.startsWith("@") ? { email: v, reason: reason || null } : { domain: v, reason: reason || null });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "suppressions"] });
      setValue("");
      setReason("");
      toast.success("Blocked for every workspace");
    },
  });
  const remove = useMutation({
    mutationFn: (id: number) => adminApi.removeSuppression(id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["admin", "suppressions"] }),
  });
  return (
    <div className="space-y-6">
      <h1 className="text-[22px] font-semibold">Global suppressions</h1>
      <SettingsCard title="Block for every workspace" description="Hard bounces and complaints seen by the platform are added automatically. Use this for spam traps and legal requests.">
        <form
          className="flex flex-col gap-2 sm:flex-row sm:items-end"
          onSubmit={(e) => {
            e.preventDefault();
            if (value.trim()) add.mutate();
          }}
        >
          <div className="grid flex-1 gap-1.5">
            <label htmlFor="global-suppression" className="text-[13px] font-medium">Email or domain</label>
            <Input id="global-suppression" className="bg-white" value={value} onChange={(e) => setValue(e.target.value)} placeholder="trap@example.org or example.org" />
          </div>
          <div className="grid flex-1 gap-1.5">
            <label htmlFor="global-suppression-reason" className="text-[13px] font-medium">Reason</label>
            <Input id="global-suppression-reason" className="bg-white" value={reason} maxLength={500} onChange={(e) => setReason(e.target.value)} />
          </div>
          <Button type="submit" disabled={!value.trim() || add.isPending}>Block</Button>
        </form>
      </SettingsCard>
      {list.isLoading ? (
        <LoadingState />
      ) : (
        <Table caption="Global suppressions" head={["Blocked", "Reason", "Source", "Added", ""]}>
          {list.data?.map((s) => (
            <tr key={s.id}>
              <th scope="row" className="px-3 py-2 font-medium">{s.email ?? s.domain}</th>
              <td className="px-3 py-2">{s.reason ?? "—"}</td>
              <td className="px-3 py-2">{s.source ?? "—"}</td>
              <td className="px-3 py-2 whitespace-nowrap">{formatDate(s.created_at)}</td>
              <td className="px-3 py-2 text-right">
                <Button variant="ghost" size="icon-sm" aria-label={`Remove ${s.email ?? s.domain}`} onClick={() => remove.mutate(s.id)}>
                  <Trash2 aria-hidden />
                </Button>
              </td>
            </tr>
          ))}
        </Table>
      )}
    </div>
  );
}

export function AdminAuditPage() {
  const logs = useQuery({ queryKey: ["admin", "audit"], queryFn: adminApi.auditLogs });
  if (logs.isLoading) return <LoadingState />;
  return (
    <div className="space-y-4">
      <h1 className="text-[22px] font-semibold">Admin audit trail</h1>
      <p className="text-[13px] text-[var(--on-surface-variant)]">
        Every action taken in this admin area. Actions on a workspace also appear in that workspace&apos;s own audit log.
      </p>
      <Table caption="Admin audit trail" head={["When", "Admin", "Action", "Target", "Details"]}>
        {logs.data?.map((row) => (
          <tr key={row.id}>
            <td className="px-3 py-2 whitespace-nowrap">{new Date(row.created_at).toLocaleString()}</td>
            <td className="px-3 py-2">{row.actor_email ?? "CLI"}</td>
            <th scope="row" className="px-3 py-2 font-medium">{describeAction(row.action.replace(/^admin\./, ""))}</th>
            <td className="px-3 py-2">
              {row.workspace_id ? <Link className="text-[var(--primary)] hover:underline" href={`/admin/workspaces/${row.workspace_id}`}>Workspace #{row.workspace_id}</Link> : `${row.entity_type} #${row.entity_id ?? ""}`}
            </td>
            <td className="max-w-[360px] px-3 py-2 font-mono text-[12px] text-[var(--on-surface-variant)]">
              <span className="line-clamp-2 break-all">{row.metadata ? JSON.stringify(row.metadata) : "—"}</span>
            </td>
          </tr>
        ))}
      </Table>
    </div>
  );
}
