"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlertTriangle, ListChecks, Plug, RefreshCw, Trash2 } from "lucide-react";
import { Switch } from "@/components/campaigns/form-controls";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { LoadingState } from "@/components/shared/loading-error";
import { Button } from "@/components/ui/button";
import { ButtonLink } from "@/components/ui/button-link";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { AdminOnlyNotice, SettingsCard, formatDate } from "@/components/settings/settings-card";
import { useWorkspace } from "@/hooks/use-workspace";
import { integrationsApi } from "@/lib/api/endpoints";
import type { components } from "@/lib/api/schema";

type Connection = components["schemas"]["IntegrationConnectionRead"];
type SettingKey = keyof Connection["settings"];

const SETTINGS: { key: SettingKey; label: string; description: string }[] = [
  {
    key: "push_contacts",
    label: "Send interested leads as contacts",
    description: "When a lead replies with interest, create or update them as a contact.",
  },
  {
    key: "push_deals",
    label: "Send deals",
    description: "New and updated deals go across, linked to their contact. Won and lost are sent too.",
  },
  {
    key: "pull_status",
    label: "Bring back won and lost",
    description: "Every 15 minutes, deals closed in the CRM are closed here as well.",
  },
];

export function IntegrationsSettings() {
  const queryClient = useQueryClient();
  const { can } = useWorkspace();
  const canEdit = can("providers.manage");
  const overview = useQuery({ queryKey: ["integrations"], queryFn: integrationsApi.overview });
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["integrations"] });
  const [domain, setDomain] = useState("");
  const [token, setToken] = useState("");
  const [removing, setRemoving] = useState<Connection | null>(null);
  const [logsFor, setLogsFor] = useState<Connection | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const result = params.get("integration");
    if (result === "connected") toast.success("HubSpot connected.");
    if (result === "error") toast.error(params.get("detail") || "We couldn't connect HubSpot. Please try again.");
    if (result === "cancelled") toast("HubSpot connection cancelled.");
  }, []);

  const hubspot = useMutation({
    mutationFn: integrationsApi.connectHubspot,
    onSuccess: (result) => window.location.assign(result.url),
  });
  const pipedrive = useMutation({
    mutationFn: () => integrationsApi.connectPipedrive({ api_token: token.trim(), company_domain: domain.trim() }),
    onSuccess: () => {
      setToken("");
      setDomain("");
      toast.success("Pipedrive connected.");
      refresh();
    },
  });
  const update = useMutation({
    mutationFn: ({ id, key, value }: { id: number; key: SettingKey; value: boolean }) =>
      integrationsApi.update(id, { [key]: value }),
    onSuccess: refresh,
  });
  const sync = useMutation({
    mutationFn: (id: number) => integrationsApi.sync(id),
    onSuccess: () => toast.success("Sync started. Check the log in a minute."),
  });
  const remove = useMutation({
    mutationFn: (id: number) => integrationsApi.remove(id),
    onSuccess: () => {
      setRemoving(null);
      refresh();
    },
  });

  if (overview.isPending) return <LoadingState />;
  if (!overview.data) return null;
  const data = overview.data;
  if (!data.enabled) {
    return (
      <SettingsCard title="Integrations" description="Sync leads and deals with HubSpot or Pipedrive.">
        <p className="text-[13px] text-[var(--on-surface-variant)]">CRM integrations aren&apos;t turned on for this workspace yet.</p>
      </SettingsCard>
    );
  }
  const connected = new Map(data.connections.map((c) => [c.provider, c]));
  const providers = new Map(data.providers.map((p) => [p.key, p]));

  return (
    <div className="space-y-6">
      {!data.in_plan ? (
        <p className="flex items-start gap-2 rounded-lg border border-[var(--outline-variant)] bg-white p-4 text-[13px]">
          <Plug className="mt-0.5 size-4 shrink-0 text-[var(--primary)]" aria-hidden />
          <span>
            CRM integrations are part of the Pro and Enterprise plans.{" "}
            <ButtonLink href="/settings/usage" variant="link" className="h-auto p-0 text-[13px]">
              See plans
            </ButtonLink>
          </span>
        </p>
      ) : null}
      {!canEdit ? <AdminOnlyNotice what="connect or change integrations" /> : null}

      {data.connections.map((connection) => (
        <SettingsCard
          key={connection.id}
          title={connection.label}
          description={
            <>
              Connected to <strong>{connection.account_label ?? connection.label}</strong> on {formatDate(connection.created_at)}.
              {connection.last_synced_at ? ` Last synced ${new Date(connection.last_synced_at).toLocaleString()}.` : ""}
            </>
          }
          actions={
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="outline" onClick={() => setLogsFor(connection)}>
                <ListChecks aria-hidden />
                Sync log
              </Button>
              {canEdit ? (
                <>
                  <Button size="sm" variant="outline" disabled={connection.status !== "active" || sync.isPending} onClick={() => sync.mutate(connection.id)}>
                    <RefreshCw aria-hidden />
                    Sync now
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => setRemoving(connection)} aria-label={`Disconnect ${connection.label}`}>
                    <Trash2 aria-hidden />
                  </Button>
                </>
              ) : null}
            </div>
          }
        >
          {connection.status !== "active" ? (
            <p role="alert" className="mb-4 flex items-start gap-2 rounded-md bg-[var(--error-container)] px-3 py-2 text-[13px] text-[var(--on-error-container)]">
              <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
              {connection.last_error || "This connection stopped working."} Reconnect it below.
            </p>
          ) : connection.last_error ? (
            <p className="mb-4 text-[12px] text-[var(--on-surface-variant)]">Last problem: {connection.last_error}</p>
          ) : null}
          <div className="space-y-4">
            {SETTINGS.map((setting) => (
              <Switch
                key={setting.key}
                label={setting.label}
                description={setting.description}
                checked={connection.settings[setting.key]}
                disabled={!canEdit || update.isPending}
                onChange={(event) => update.mutate({ id: connection.id, key: setting.key, value: event.target.checked })}
              />
            ))}
          </div>
        </SettingsCard>
      ))}

      {canEdit && data.in_plan ? (
        <>
          <SettingsCard
            title={connected.has("hubspot") ? "Reconnect HubSpot" : "HubSpot"}
            description="Sign in to HubSpot and choose the account to sync with. Contacts and deals use HubSpot's default pipeline."
          >
            {providers.get("hubspot")?.available ? (
              <Button onClick={() => hubspot.mutate()} disabled={hubspot.isPending}>
                {connected.has("hubspot") ? "Reconnect HubSpot" : "Connect HubSpot"}
              </Button>
            ) : (
              <p className="text-[13px] text-[var(--on-surface-variant)]">HubSpot isn&apos;t set up on this server yet.</p>
            )}
          </SettingsCard>

          <SettingsCard
            title={connected.has("pipedrive") ? "Reconnect Pipedrive" : "Pipedrive"}
            description="Paste a Pipedrive API token (Personal preferences → API) and your company domain. The token is stored encrypted."
          >
            <form
              className="grid gap-3 sm:grid-cols-2"
              onSubmit={(event) => {
                event.preventDefault();
                pipedrive.mutate();
              }}
            >
              <div>
                <label htmlFor="pipedrive-domain" className="mb-1 block text-[13px] font-medium">
                  Company domain
                </label>
                <Input id="pipedrive-domain" placeholder="acme (for acme.pipedrive.com)" value={domain} onChange={(event) => setDomain(event.target.value)} required />
              </div>
              <div>
                <label htmlFor="pipedrive-token" className="mb-1 block text-[13px] font-medium">
                  API token
                </label>
                <Input id="pipedrive-token" type="password" autoComplete="off" value={token} onChange={(event) => setToken(event.target.value)} required minLength={10} />
              </div>
              <div className="sm:col-span-2">
                <Button type="submit" disabled={pipedrive.isPending || !domain.trim() || token.trim().length < 10}>
                  {pipedrive.isPending ? "Checking…" : connected.has("pipedrive") ? "Reconnect Pipedrive" : "Connect Pipedrive"}
                </Button>
              </div>
            </form>
          </SettingsCard>
        </>
      ) : null}

      <ConfirmDialog
        open={removing !== null}
        onOpenChange={(open) => !open && setRemoving(null)}
        title={`Disconnect ${removing?.label ?? ""}?`}
        description="Nothing more is sent, and records already in the CRM stay there. You can connect again at any time."
        confirmLabel="Disconnect"
        destructive
        loading={remove.isPending}
        onConfirm={() => removing && remove.mutate(removing.id)}
      />
      <SyncLogSheet connection={logsFor} onClose={() => setLogsFor(null)} />
    </div>
  );
}

function SyncLogSheet({ connection, onClose }: { connection: Connection | null; onClose: () => void }) {
  const logs = useQuery({
    queryKey: ["integration-logs", connection?.id],
    queryFn: () => integrationsApi.logs(connection!.id),
    enabled: connection !== null,
  });
  return (
    <Sheet open={connection !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>{connection?.label} sync log</SheetTitle>
          <SheetDescription>The latest 50 pushes and pulls.</SheetDescription>
        </SheetHeader>
        <div className="px-4 pb-4">
          {logs.isPending ? (
            <LoadingState />
          ) : logs.data?.length ? (
            <ul className="divide-y divide-[var(--outline-variant)] text-[13px]">
              {logs.data.map((row) => (
                <li key={row.id} className="py-2">
                  <p className="font-medium">
                    {row.direction === "push" ? "Sent" : "Received"} {row.object_type} {row.local_id ? `#${row.local_id}` : ""}
                    <span className={row.status === "error" ? "ml-2 text-[var(--error)]" : "ml-2 text-[var(--on-surface-variant)]"}>{row.status}</span>
                  </p>
                  {row.message ? <p className="text-[12px] text-[var(--on-surface-variant)]">{row.message}</p> : null}
                  <p className="text-[12px] text-[var(--on-surface-variant)]">{new Date(row.created_at).toLocaleString()}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[13px] text-[var(--on-surface-variant)]">Nothing synced yet.</p>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
