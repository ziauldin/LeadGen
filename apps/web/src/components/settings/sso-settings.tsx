"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Clock, Copy, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { ErrorState, LoadingState } from "@/components/shared/loading-error";
import { AdminOnlyNotice, SettingsCard } from "@/components/settings/settings-card";
import { useWorkspace } from "@/hooks/use-workspace";
import { billingApi, ssoApi } from "@/lib/api/endpoints";
import type { components } from "@/lib/api/schema";

type Connection = components["schemas"]["ConnectionRead"];
type ConnectionWrite = components["schemas"]["ConnectionWrite"];

function CopyField({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-1">
      <p className="text-[12px] font-medium text-[var(--on-surface-variant)]">{label}</p>
      <div className="flex items-center gap-2">
        <code className="min-w-0 flex-1 truncate rounded border border-[var(--outline-variant)] bg-[var(--surface-container-low)] px-2 py-1.5 font-mono text-[12px]">
          {value}
        </code>
        <Button
          variant="outline"
          size="icon-sm"
          aria-label={`Copy ${label}`}
          onClick={() => void navigator.clipboard.writeText(value).then(() => toast.success("Copied"))}
        >
          <Copy aria-hidden />
        </Button>
      </div>
    </div>
  );
}

function DomainsCard({ canEdit }: { canEdit: boolean }) {
  const queryClient = useQueryClient();
  const domains = useQuery({ queryKey: ["sso", "domains"], queryFn: ssoApi.domains });
  const [domain, setDomain] = useState("");
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["sso", "domains"] });
  const add = useMutation({
    mutationFn: () => ssoApi.addDomain(domain.trim()),
    onSuccess: () => {
      setDomain("");
      void refresh();
    },
  });
  const verify = useMutation({
    mutationFn: ssoApi.verifyDomain,
    onSuccess: (record) => {
      toast.success(`${record.domain} is verified`);
      void refresh();
    },
  });
  const remove = useMutation({ mutationFn: ssoApi.deleteDomain, onSuccess: () => void refresh() });

  return (
    <SettingsCard
      title="Verified domains"
      description="Prove you own your company's email domain by adding a DNS TXT record. Only people with an email at a verified domain can sign in through your identity provider."
    >
      {domains.isLoading ? (
        <LoadingState />
      ) : domains.error ? (
        <ErrorState error={domains.error} onRetry={() => domains.refetch()} />
      ) : (
        <div className="space-y-4">
          <ul className="space-y-3">
            {(domains.data ?? []).map((record) => (
              <li key={record.id} className="rounded-lg border border-[var(--outline-variant)] p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[14px] font-medium">{record.domain}</span>
                  {record.verified ? (
                    <span className="inline-flex items-center gap-1 text-[12px] font-medium text-emerald-700">
                      <CheckCircle2 className="size-3.5" aria-hidden /> Verified
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-[12px] font-medium text-amber-700">
                      <Clock className="size-3.5" aria-hidden /> Waiting for DNS
                    </span>
                  )}
                  <span className="flex-1" />
                  {canEdit && !record.verified && (
                    <Button size="sm" onClick={() => verify.mutate(record.id)} disabled={verify.isPending}>
                      Check now
                    </Button>
                  )}
                  {canEdit && (
                    <Button variant="ghost" size="icon-sm" aria-label={`Remove ${record.domain}`} onClick={() => remove.mutate(record.id)}>
                      <Trash2 aria-hidden />
                    </Button>
                  )}
                </div>
                {!record.verified && (
                  <div className="mt-3">
                    <CopyField label={`Add this TXT record to ${record.domain}`} value={record.txt_record} />
                  </div>
                )}
              </li>
            ))}
          </ul>
          {canEdit && (
            <form
              className="flex max-w-md gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                add.mutate();
              }}
            >
              <Input aria-label="Domain" placeholder="yourcompany.com" value={domain} onChange={(e) => setDomain(e.target.value)} />
              <Button type="submit" disabled={domain.trim().length < 3 || add.isPending}>
                Add domain
              </Button>
            </form>
          )}
        </div>
      )}
    </SettingsCard>
  );
}

function ConnectionForm({ connection, samlAllowed, onSaved }: { connection: Connection | null; samlAllowed: boolean; onSaved: () => void }) {
  const [form, setForm] = useState<ConnectionWrite>({
    protocol: connection?.protocol ?? "oidc",
    display_name: connection?.display_name ?? "",
    oidc_issuer: connection?.oidc_issuer ?? "",
    oidc_client_id: connection?.oidc_client_id ?? "",
    oidc_client_secret: "",
    saml_idp_entity_id: connection?.saml_idp_entity_id ?? "",
    saml_idp_sso_url: connection?.saml_idp_sso_url ?? "",
    saml_idp_certificate: "",
    default_role: connection?.default_role ?? "member",
  });
  useEffect(() => setForm((f) => ({ ...f, oidc_client_secret: "", saml_idp_certificate: "" })), [connection]);
  const set = (key: keyof ConnectionWrite) => (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm((current) => ({ ...current, [key]: event.target.value }));
  const save = useMutation({
    mutationFn: () => {
      const payload: ConnectionWrite = { ...form };
      if (!payload.oidc_client_secret) delete payload.oidc_client_secret;
      if (!payload.saml_idp_certificate) delete payload.saml_idp_certificate;
      return connection ? ssoApi.updateConnection(connection.id, payload) : ssoApi.createConnection(payload);
    },
    onSuccess: () => {
      toast.success("Saved");
      onSaved();
    },
  });
  const oidcMode = form.protocol === "oidc";
  const field = "grid gap-1.5";
  const labelClass = "text-[13px] font-medium";

  return (
    <form
      className="grid gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        save.mutate();
      }}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <div className={field}>
          <label className={labelClass} htmlFor="sso-protocol">Protocol</label>
          <select id="sso-protocol" className="h-9 rounded-lg border border-input bg-white px-2 text-[13px]" value={form.protocol ?? "oidc"} onChange={set("protocol")} disabled={Boolean(connection)}>
            <option value="oidc">OpenID Connect (Okta, Auth0, Google Workspace, Entra ID)</option>
            <option value="saml" disabled={!samlAllowed}>SAML 2.0{samlAllowed ? "" : " (Enterprise plan)"}</option>
          </select>
        </div>
        <div className={field}>
          <label className={labelClass} htmlFor="sso-name">Name shown on the sign-in page</label>
          <Input id="sso-name" value={form.display_name ?? ""} onChange={set("display_name")} placeholder="Acme Okta" />
        </div>
      </div>
      {oidcMode ? (
        <div className="grid gap-4 sm:grid-cols-2">
          <div className={`${field} sm:col-span-2`}>
            <label className={labelClass} htmlFor="sso-issuer">Issuer URL</label>
            <Input id="sso-issuer" value={form.oidc_issuer ?? ""} onChange={set("oidc_issuer")} placeholder="https://yourcompany.okta.com" />
          </div>
          <div className={field}>
            <label className={labelClass} htmlFor="sso-client">Client ID</label>
            <Input id="sso-client" value={form.oidc_client_id ?? ""} onChange={set("oidc_client_id")} />
          </div>
          <div className={field}>
            <label className={labelClass} htmlFor="sso-secret">Client secret{connection?.has_client_secret ? " (saved; leave blank to keep)" : ""}</label>
            <Input id="sso-secret" type="password" value={form.oidc_client_secret ?? ""} onChange={set("oidc_client_secret")} autoComplete="off" />
          </div>
        </div>
      ) : (
        <div className="grid gap-4">
          <div className={field}>
            <label className={labelClass} htmlFor="saml-entity">Identity provider entity ID (issuer)</label>
            <Input id="saml-entity" value={form.saml_idp_entity_id ?? ""} onChange={set("saml_idp_entity_id")} />
          </div>
          <div className={field}>
            <label className={labelClass} htmlFor="saml-url">Single sign-on URL</label>
            <Input id="saml-url" value={form.saml_idp_sso_url ?? ""} onChange={set("saml_idp_sso_url")} />
          </div>
          <div className={field}>
            <label className={labelClass} htmlFor="saml-cert">Signing certificate (PEM){connection?.has_certificate ? " (saved; paste a new one to replace)" : ""}</label>
            <Textarea id="saml-cert" rows={5} className="font-mono text-[12px]" value={form.saml_idp_certificate ?? ""} onChange={set("saml_idp_certificate")} placeholder="-----BEGIN CERTIFICATE-----" />
          </div>
        </div>
      )}
      <div className={`${field} max-w-xs`}>
        <label className={labelClass} htmlFor="sso-role">Role for new members</label>
        <select id="sso-role" className="h-9 rounded-lg border border-input bg-white px-2 text-[13px]" value={form.default_role ?? "member"} onChange={set("default_role")}>
          <option value="member">Member</option>
          <option value="admin">Admin</option>
        </select>
      </div>
      <div>
        <Button type="submit" disabled={save.isPending || !form.display_name}>
          {save.isPending ? "Saving…" : connection ? "Save changes" : "Add identity provider"}
        </Button>
      </div>
    </form>
  );
}

function ConnectionCard({ canEdit, samlAllowed }: { canEdit: boolean; samlAllowed: boolean }) {
  const queryClient = useQueryClient();
  const connections = useQuery({ queryKey: ["sso", "connections"], queryFn: ssoApi.connections });
  const connection = connections.data?.[0] ?? null;
  const [confirmDelete, setConfirmDelete] = useState(false);
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["sso", "connections"] });
  const toggle = useMutation({
    mutationFn: (data: ConnectionWrite) => ssoApi.updateConnection(connection!.id, data),
    onSuccess: () => void refresh(),
  });
  const remove = useMutation({
    mutationFn: () => ssoApi.deleteConnection(connection!.id),
    onSuccess: () => {
      setConfirmDelete(false);
      void refresh();
    },
  });

  return (
    <SettingsCard
      title="Identity provider"
      description="Let your team sign in with your company's identity provider. New people are added to this workspace the first time they sign in."
    >
      {connections.isLoading ? (
        <LoadingState />
      ) : connections.error ? (
        <ErrorState error={connections.error} onRetry={() => connections.refetch()} />
      ) : (
        <div className="space-y-6">
          {connection && (
            <div className="space-y-3 rounded-lg border border-[var(--outline-variant)] bg-[var(--surface-container-low)] p-4">
              <p className="text-[13px] font-medium">Give these values to your identity provider:</p>
              {connection.protocol === "saml" ? (
                <>
                  <CopyField label="Entity ID (audience)" value={connection.sp_entity_id} />
                  <CopyField label="Assertion consumer service (ACS) URL" value={connection.acs_url} />
                </>
              ) : (
                <CopyField label="Redirect URI" value={connection.oidc_redirect_uri} />
              )}
              {canEdit && (
                <div className="flex flex-wrap gap-2 pt-2">
                  <Button
                    variant={connection.is_active ? "outline" : "default"}
                    onClick={() => toggle.mutate({ is_active: !connection.is_active })}
                    disabled={toggle.isPending}
                  >
                    {connection.is_active ? "Turn off" : "Turn on"}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => toggle.mutate({ enforce: !connection.enforce })}
                    disabled={toggle.isPending || !connection.is_active}
                  >
                    {connection.enforce ? "Stop requiring SSO" : "Require SSO for verified domains"}
                  </Button>
                  <Button variant="destructive" onClick={() => setConfirmDelete(true)}>
                    Remove
                  </Button>
                </div>
              )}
              <p className="text-[12px] text-[var(--on-surface-variant)]">
                {connection.is_active ? "On" : "Off"}
                {connection.enforce ? " · password sign-in is blocked for verified domains (owners can still use a password)" : ""}
                {connection.last_login_at ? ` · last used ${new Date(connection.last_login_at).toLocaleString()}` : ""}
              </p>
            </div>
          )}
          {canEdit && <ConnectionForm connection={connection} samlAllowed={samlAllowed} onSaved={() => void refresh()} />}
        </div>
      )}
      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title="Remove this identity provider?"
        description="People will need to sign in with a password or Google/Microsoft instead."
        confirmLabel="Remove"
        destructive
        loading={remove.isPending}
        onConfirm={() => remove.mutate()}
      />
    </SettingsCard>
  );
}

export function SsoSettings() {
  const { hasRole } = useWorkspace();
  const billing = useQuery({ queryKey: ["billing"], queryFn: billingApi.summary });
  const canEdit = hasRole("admin");
  if (billing.isLoading) return <LoadingState />;
  const features = (billing.data?.features ?? {}) as Record<string, boolean | number>;
  if (!features.sso) {
    return (
      <SettingsCard title="Single sign-on" description="Sign in with your company's identity provider (Okta, Entra ID, Google Workspace…).">
        <p className="text-[13px] text-[var(--on-surface)]">
          Single sign-on is included on the Pro plan, and SAML on Enterprise. Your plan:{" "}
          <span className="font-medium capitalize">{billing.data?.plan ?? "free"}</span>.
        </p>
      </SettingsCard>
    );
  }
  return (
    <div className="space-y-6">
      {!canEdit && <AdminOnlyNotice />}
      <DomainsCard canEdit={canEdit} />
      <ConnectionCard canEdit={canEdit} samlAllowed={Boolean(features.saml)} />
    </div>
  );
}
