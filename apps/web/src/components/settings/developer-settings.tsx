"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Check, Copy, KeyRound, ListChecks, Plus, RefreshCw, RotateCw, Send, Trash2, Webhook } from "lucide-react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { AdminOnlyNotice, SettingsCard, formatDate } from "@/components/settings/settings-card";
import { useWorkspace } from "@/hooks/use-workspace";
import { billingApi, developerApi } from "@/lib/api/endpoints";
import type { components } from "@/lib/api/schema";

type S = components["schemas"];
type Option = S["OptionRead"];

const EXPIRY_OPTIONS: Record<string, string> = {
  never: "Never",
  "30": "30 days",
  "90": "90 days",
  "365": "1 year",
};

function CopyField({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex items-center gap-2">
      <code className="min-w-0 flex-1 break-all rounded-md bg-[var(--surface-container-low)] px-3 py-2 font-mono text-[12px]">
        {value}
      </code>
      <Button
        type="button"
        variant="outline"
        size="icon-sm"
        aria-label={`Copy ${label}`}
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(value);
            setCopied(true);
            toast.success(`${label} copied`);
            window.setTimeout(() => setCopied(false), 2000);
          } catch {
            toast.error("Couldn't copy. Select it and copy it by hand.");
          }
        }}
      >
        {copied ? <Check aria-hidden /> : <Copy aria-hidden />}
      </Button>
    </div>
  );
}

/** Shows a secret exactly once. */
function RevealDialog({
  title,
  label,
  value,
  onClose,
}: {
  title: string;
  label: string;
  value: string | null;
  onClose: () => void;
}) {
  return (
    <Dialog open={value !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            Copy it now and store it somewhere safe. For your security it won&apos;t be shown again.
          </DialogDescription>
        </DialogHeader>
        {value ? <CopyField value={value} label={label} /> : null}
        <DialogFooter>
          <Button onClick={onClose}>Done</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function OptionChecklist({
  legend,
  options,
  selected,
  onChange,
}: {
  legend: string;
  options: Option[];
  selected: Set<string>;
  onChange: (next: Set<string>) => void;
}) {
  return (
    <fieldset className="grid gap-1">
      <legend className="mb-1 text-[13px] font-medium">{legend}</legend>
      {options.map((option) => (
        <label
          key={option.key}
          className="flex items-start gap-2 rounded-md px-2 py-1.5 text-[13px] hover:bg-[var(--surface-container-low)]"
        >
          <input
            type="checkbox"
            className="mt-0.5 size-4 cursor-pointer accent-[var(--primary)]"
            checked={selected.has(option.key)}
            onChange={(event) => {
              const next = new Set(selected);
              if (event.target.checked) next.add(option.key);
              else next.delete(option.key);
              onChange(next);
            }}
          />
          <span>
            <code className="font-mono text-[12px]">{option.key}</code>
            <span className="block text-[12px] text-[var(--on-surface-variant)]">{option.description}</span>
          </span>
        </label>
      ))}
    </fieldset>
  );
}

function ErrorNote({ message }: { message: string | null }) {
  return message ? (
    <p role="alert" className="rounded-md bg-[var(--error-container)] px-3 py-2 text-[13px] text-[var(--on-error-container)]">
      {message}
    </p>
  ) : null;
}

// --- API keys ------------------------------------------------------------------------------------

function CreateKeyDialog({
  open,
  scopes,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  scopes: Option[];
  onOpenChange: (open: boolean) => void;
  onCreated: (key: string) => void;
}) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set(["leads:read"]));
  const [expiry, setExpiry] = useState("never");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      developerApi.createKey({
        name: name.trim(),
        scopes: [...selected],
        expires_in_days: expiry === "never" ? null : Number(expiry),
      }),
    meta: { silent: true },
    onSuccess: (created) => {
      void queryClient.invalidateQueries({ queryKey: ["api-keys"] });
      setName("");
      setSelected(new Set(["leads:read"]));
      setExpiry("never");
      onOpenChange(false);
      onCreated(created.key);
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
            create.mutate();
          }}
        >
          <DialogHeader>
            <DialogTitle>New API key</DialogTitle>
            <DialogDescription>
              Keys act with your permissions, limited to the scopes you choose. They stop working if you
              leave the workspace.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-1.5">
            <label htmlFor="key-name" className="text-[13px] font-medium">
              Name
            </label>
            <Input
              id="key-name"
              required
              maxLength={100}
              value={name}
              placeholder="e.g. Zapier, HubSpot sync"
              onChange={(event) => setName(event.target.value)}
            />
          </div>
          <div className="max-h-[260px] overflow-y-auto pr-1" tabIndex={0}>
            <OptionChecklist legend="Scopes" options={scopes} selected={selected} onChange={setSelected} />
          </div>
          <div className="grid gap-1.5">
            <label id="key-expiry-label" className="text-[13px] font-medium">
              Expires
            </label>
            <Select value={expiry} items={EXPIRY_OPTIONS} onValueChange={(value) => setExpiry(String(value ?? "never"))}>
              <SelectTrigger className="w-full bg-white sm:w-[200px]" aria-labelledby="key-expiry-label">
                <SelectValue />
              </SelectTrigger>
              <SelectContent alignItemWithTrigger={false}>
                {Object.entries(EXPIRY_OPTIONS).map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <ErrorNote message={error} />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={create.isPending}>
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending || !name.trim() || selected.size === 0}>
              {create.isPending ? "Creating…" : "Create key"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ApiKeysCard({ scopes }: { scopes: Option[] }) {
  const queryClient = useQueryClient();
  const keys = useQuery({ queryKey: ["api-keys"], queryFn: developerApi.keys });
  const [creating, setCreating] = useState(false);
  const [revealed, setRevealed] = useState<string | null>(null);
  const [revokeTarget, setRevokeTarget] = useState<S["ApiKeyRead"] | null>(null);

  const revoke = useMutation({
    mutationFn: (id: number) => developerApi.revokeKey(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["api-keys"] });
      toast.success(`Revoked ${revokeTarget?.name ?? "key"}`);
      setRevokeTarget(null);
    },
  });

  return (
    <SettingsCard
      id="api-keys"
      title="API keys"
      description={
        <>
          Use the REST API at <code className="font-mono">/v1</code> with{" "}
          <code className="font-mono">Authorization: Bearer &lt;key&gt;</code>. The{" "}
          <a className="underline" href="/api/v1/openapi.json" target="_blank" rel="noreferrer">
            OpenAPI schema
          </a>{" "}
          describes every endpoint.
        </>
      }
      actions={
        <Button size="sm" onClick={() => setCreating(true)}>
          <Plus aria-hidden /> New key
        </Button>
      }
    >
      {keys.isLoading ? (
        <LoadingState />
      ) : keys.data?.length ? (
        <ul aria-label="API keys" className="divide-y divide-[var(--outline-variant)]">
          {keys.data.map((key) => {
            const expired = key.expires_at ? new Date(key.expires_at) < new Date() : false;
            const inactive = Boolean(key.revoked_at) || expired;
            return (
              <li key={key.id} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <p className="flex flex-wrap items-center gap-2 text-[14px] font-medium">
                    <KeyRound className="size-4 text-[var(--on-surface-variant)]" aria-hidden />
                    {key.name}
                    <code className="font-mono text-[12px] text-[var(--on-surface-variant)]">{key.prefix}…</code>
                    {inactive ? (
                      <span className="rounded-full bg-[var(--surface-container)] px-2 py-0.5 text-[11px] font-semibold text-[var(--on-surface-variant)]">
                        {key.revoked_at ? "Revoked" : "Expired"}
                      </span>
                    ) : null}
                  </p>
                  <p className="text-[12px] text-[var(--on-surface-variant)]">
                    {key.scopes.join(", ")}
                  </p>
                  <p className="text-[12px] text-[var(--on-surface-variant)]">
                    Created {formatDate(key.created_at)}
                    {key.created_by ? ` by ${key.created_by}` : ""} · Last used{" "}
                    {key.last_used_at ? formatDate(key.last_used_at) : "never"}
                    {key.expires_at && !key.revoked_at ? ` · Expires ${formatDate(key.expires_at)}` : ""}
                  </p>
                </div>
                {!inactive ? (
                  <Button variant="outline" size="sm" onClick={() => setRevokeTarget(key)}>
                    Revoke
                  </Button>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="text-[13px] text-[var(--on-surface-variant)]">No API keys yet.</p>
      )}

      <CreateKeyDialog open={creating} scopes={scopes} onOpenChange={setCreating} onCreated={setRevealed} />
      <RevealDialog title="Your new API key" label="API key" value={revealed} onClose={() => setRevealed(null)} />
      <ConfirmDialog
        open={revokeTarget !== null}
        onOpenChange={(open) => !open && setRevokeTarget(null)}
        title={`Revoke ${revokeTarget?.name ?? "this key"}?`}
        description="Anything using this key stops working straight away. This can't be undone."
        confirmLabel="Revoke key"
        destructive
        loading={revoke.isPending}
        onConfirm={() => revokeTarget && revoke.mutate(revokeTarget.id)}
      />
    </SettingsCard>
  );
}

// --- webhooks ------------------------------------------------------------------------------------

function CreateEndpointDialog({
  open,
  events,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  events: Option[];
  onOpenChange: (open: boolean) => void;
  onCreated: (secret: string) => void;
}) {
  const queryClient = useQueryClient();
  const [url, setUrl] = useState("");
  const [description, setDescription] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set(["reply.received"]));
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      developerApi.createEndpoint({
        url: url.trim(),
        description: description.trim() || null,
        events: [...selected],
      }),
    meta: { silent: true },
    onSuccess: (created) => {
      void queryClient.invalidateQueries({ queryKey: ["webhook-endpoints"] });
      setUrl("");
      setDescription("");
      setSelected(new Set(["reply.received"]));
      onOpenChange(false);
      onCreated(created.secret);
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
            create.mutate();
          }}
        >
          <DialogHeader>
            <DialogTitle>New webhook endpoint</DialogTitle>
            <DialogDescription>
              We POST signed JSON to this URL when the events you choose happen. Failed deliveries are
              retried for about two days.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-1.5">
            <label htmlFor="endpoint-url" className="text-[13px] font-medium">
              URL
            </label>
            <Input
              id="endpoint-url"
              type="url"
              required
              value={url}
              placeholder="https://hooks.zapier.com/…"
              onChange={(event) => setUrl(event.target.value)}
            />
          </div>
          <div className="grid gap-1.5">
            <label htmlFor="endpoint-description" className="text-[13px] font-medium">
              Description <span className="font-normal text-muted-foreground">(optional)</span>
            </label>
            <Input
              id="endpoint-description"
              maxLength={255}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </div>
          <OptionChecklist legend="Events" options={events} selected={selected} onChange={setSelected} />
          <ErrorNote message={error} />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={create.isPending}>
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending || !url.trim() || selected.size === 0}>
              {create.isPending ? "Saving…" : "Add endpoint"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

const DELIVERY_STYLES: Record<string, string> = {
  succeeded: "bg-[var(--primary-fixed)] text-[var(--on-primary-fixed)]",
  pending: "bg-[var(--secondary-fixed)] text-[var(--on-secondary-fixed)]",
  failed: "bg-[var(--error-container)] text-[var(--on-error-container)]",
};

function DeliveriesSheet({ endpoint, onClose }: { endpoint: S["EndpointRead"] | null; onClose: () => void }) {
  const queryClient = useQueryClient();
  const deliveries = useQuery({
    queryKey: ["webhook-deliveries", endpoint?.id],
    queryFn: () => developerApi.deliveries(endpoint!.id),
    enabled: endpoint !== null,
  });
  const replay = useMutation({
    mutationFn: (id: number) => developerApi.replay(id),
    onSuccess: (delivery) => {
      void queryClient.invalidateQueries({ queryKey: ["webhook-deliveries", endpoint?.id] });
      toast.success(delivery.status === "succeeded" ? "Delivered again" : "Queued for delivery");
    },
  });

  return (
    <Sheet open={endpoint !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>Recent deliveries</SheetTitle>
          <SheetDescription className="break-all">{endpoint?.url}</SheetDescription>
        </SheetHeader>
        <div className="px-4 pb-4">
          {deliveries.isLoading ? (
            <LoadingState />
          ) : deliveries.data?.items.length ? (
            <ul aria-label="Deliveries" className="divide-y divide-[var(--outline-variant)]">
              {deliveries.data.items.map((delivery) => (
                <li key={delivery.id} className="flex items-start justify-between gap-3 py-3">
                  <div className="min-w-0 text-[13px]">
                    <p className="flex flex-wrap items-center gap-2 font-medium">
                      <code className="font-mono text-[12px]">{delivery.event_type}</code>
                      <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold capitalize ${DELIVERY_STYLES[delivery.status] ?? ""}`}>
                        {delivery.status}
                      </span>
                    </p>
                    <p className="text-[12px] text-[var(--on-surface-variant)]">
                      {new Date(delivery.created_at).toLocaleString()} · {delivery.attempts}{" "}
                      {delivery.attempts === 1 ? "attempt" : "attempts"}
                      {delivery.response_status ? ` · HTTP ${delivery.response_status}` : ""}
                    </p>
                    {delivery.error ? <p className="text-[12px] text-[var(--error)]">{delivery.error}</p> : null}
                  </div>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`Send ${delivery.event_type} again`}
                    disabled={replay.isPending}
                    onClick={() => replay.mutate(delivery.id)}
                  >
                    <RotateCw aria-hidden />
                  </Button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[13px] text-[var(--on-surface-variant)]">No deliveries yet. Send a test event.</p>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}

function WebhooksCard({ events }: { events: Option[] }) {
  const queryClient = useQueryClient();
  const endpoints = useQuery({ queryKey: ["webhook-endpoints"], queryFn: developerApi.endpoints });
  const [creating, setCreating] = useState(false);
  const [revealed, setRevealed] = useState<string | null>(null);
  const [viewing, setViewing] = useState<S["EndpointRead"] | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<S["EndpointRead"] | null>(null);
  const [rotateTarget, setRotateTarget] = useState<S["EndpointRead"] | null>(null);
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["webhook-endpoints"] });

  const test = useMutation({
    mutationFn: (id: number) => developerApi.testEndpoint(id),
    onSuccess: (delivery) => {
      refresh();
      if (delivery.status === "succeeded") toast.success("Test event delivered");
      else toast.error(delivery.error ?? "The endpoint didn't accept the test event");
    },
  });
  const toggle = useMutation({
    mutationFn: (endpoint: S["EndpointRead"]) =>
      developerApi.updateEndpoint(endpoint.id, { is_active: !endpoint.is_active }),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: (id: number) => developerApi.deleteEndpoint(id),
    onSuccess: () => {
      refresh();
      setDeleteTarget(null);
      toast.success("Endpoint deleted");
    },
  });
  const rotate = useMutation({
    mutationFn: (id: number) => developerApi.rotateSecret(id),
    onSuccess: (result) => {
      setRotateTarget(null);
      setRevealed(result.secret);
    },
  });

  return (
    <SettingsCard
      id="webhooks"
      title="Webhooks"
      description={
        <>
          Each request carries a <code className="font-mono">LeadsGen-Signature</code> header:{" "}
          <code className="font-mono">t=&lt;unix time&gt;,v1=&lt;HMAC-SHA256 of &quot;t.body&quot;&gt;</code> using
          the endpoint&apos;s signing secret. Works with Zapier, Make and your own servers.
        </>
      }
      actions={
        <Button size="sm" onClick={() => setCreating(true)}>
          <Plus aria-hidden /> New endpoint
        </Button>
      }
    >
      {endpoints.isLoading ? (
        <LoadingState />
      ) : endpoints.data?.length ? (
        <ul aria-label="Webhook endpoints" className="divide-y divide-[var(--outline-variant)]">
          {endpoints.data.map((endpoint) => (
            <li key={endpoint.id} className="flex flex-col gap-2 py-3 lg:flex-row lg:items-center lg:justify-between">
              <div className="min-w-0">
                <p className="flex flex-wrap items-center gap-2 text-[14px] font-medium">
                  <Webhook className="size-4 text-[var(--on-surface-variant)]" aria-hidden />
                  <span className="break-all">{endpoint.url}</span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                      endpoint.is_active
                        ? "bg-[var(--primary-fixed)] text-[var(--on-primary-fixed)]"
                        : "bg-[var(--surface-container)] text-[var(--on-surface-variant)]"
                    }`}
                  >
                    {endpoint.is_active ? "Active" : "Disabled"}
                  </span>
                </p>
                {endpoint.description ? (
                  <p className="text-[12px] text-[var(--on-surface-variant)]">{endpoint.description}</p>
                ) : null}
                <p className="text-[12px] text-[var(--on-surface-variant)]">{endpoint.events.join(", ")}</p>
                {endpoint.disabled_reason ? (
                  <p className="text-[12px] text-[var(--error)]">{endpoint.disabled_reason}</p>
                ) : null}
              </div>
              <div className="flex shrink-0 flex-wrap gap-1">
                <Button variant="outline" size="sm" disabled={test.isPending || !endpoint.is_active} onClick={() => test.mutate(endpoint.id)}>
                  <Send aria-hidden /> Test
                </Button>
                <Button variant="outline" size="sm" onClick={() => setViewing(endpoint)}>
                  <ListChecks aria-hidden /> Deliveries
                </Button>
                <Button variant="ghost" size="sm" disabled={toggle.isPending} onClick={() => toggle.mutate(endpoint)}>
                  {endpoint.is_active ? "Disable" : "Enable"}
                </Button>
                <Button variant="ghost" size="icon-sm" aria-label={`Rotate signing secret for ${endpoint.url}`} onClick={() => setRotateTarget(endpoint)}>
                  <RefreshCw aria-hidden />
                </Button>
                <Button variant="ghost" size="icon-sm" aria-label={`Delete ${endpoint.url}`} onClick={() => setDeleteTarget(endpoint)}>
                  <Trash2 aria-hidden />
                </Button>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-[13px] text-[var(--on-surface-variant)]">No webhook endpoints yet.</p>
      )}

      <CreateEndpointDialog open={creating} events={events} onOpenChange={setCreating} onCreated={setRevealed} />
      <RevealDialog title="Signing secret" label="Signing secret" value={revealed} onClose={() => setRevealed(null)} />
      <DeliveriesSheet endpoint={viewing} onClose={() => setViewing(null)} />
      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title="Delete this endpoint?"
        description="It stops receiving events and its delivery history is deleted."
        confirmLabel="Delete endpoint"
        destructive
        loading={remove.isPending}
        onConfirm={() => deleteTarget && remove.mutate(deleteTarget.id)}
      />
      <ConfirmDialog
        open={rotateTarget !== null}
        onOpenChange={(open) => !open && setRotateTarget(null)}
        title="Rotate the signing secret?"
        description="The old secret stops working immediately. Update your receiver with the new one."
        confirmLabel="Rotate secret"
        loading={rotate.isPending}
        onConfirm={() => rotateTarget && rotate.mutate(rotateTarget.id)}
      />
    </SettingsCard>
  );
}

export function DeveloperSettings() {
  const { can, permissionsLoading } = useWorkspace();
  const options = useQuery({ queryKey: ["developer-options"], queryFn: developerApi.options, staleTime: Infinity });
  const billing = useQuery({ queryKey: ["billing"], queryFn: billingApi.summary });
  if (permissionsLoading || options.isLoading || billing.isLoading) return <LoadingState />;

  if (!options.data?.enabled) {
    return (
      <SettingsCard title="API & webhooks" description="Connect LeadsGen to your other tools.">
        <p className="text-[13px] text-[var(--on-surface-variant)]">
          The public API isn&apos;t turned on for this installation yet.
        </p>
      </SettingsCard>
    );
  }
  const features = (billing.data?.features ?? {}) as Record<string, boolean | number>;
  if (!features.api_access) {
    return (
      <SettingsCard title="API & webhooks" description="Connect LeadsGen to your other tools.">
        <p className="text-[13px] text-[var(--on-surface)]">
          API keys and webhooks are included on the Starter plan and above. Your plan:{" "}
          <span className="font-medium capitalize">{billing.data?.plan ?? "free"}</span>.
        </p>
      </SettingsCard>
    );
  }
  if (!can("api_keys.manage")) {
    return (
      <SettingsCard title="API & webhooks" description="Connect LeadsGen to your other tools.">
        <AdminOnlyNotice what="create API keys or webhooks" />
      </SettingsCard>
    );
  }
  return (
    <div className="space-y-6">
      <ApiKeysCard scopes={options.data.scopes} />
      <WebhooksCard events={options.data.events} />
    </div>
  );
}
