"use client";

import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { z } from "zod";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { providerSettingsApi } from "@/lib/api/endpoints";
import type { ProviderCredential, ProviderName, ProviderType } from "@/lib/api/types";

type ProviderDefinition = {
  provider_name: ProviderName;
  label: string;
  description: string;
};

const SEARCH_PROVIDERS: ProviderDefinition[] = [
  { provider_name: "mock", label: "Mock", description: "Local test results — no API key required." },
  {
    provider_name: "google_cse",
    label: "Google CSE",
    description: "Google Programmable Search JSON API.",
  },
  { provider_name: "bing", label: "Bing Search", description: "Microsoft Bing Web Search API." },
  { provider_name: "serpapi", label: "SerpAPI", description: "SerpAPI search results." },
];

const EMAIL_PROVIDERS: ProviderDefinition[] = [
  { provider_name: "mock", label: "Mock", description: "Simulated sends for local testing." },
  { provider_name: "smtp", label: "SMTP", description: "Direct SMTP delivery." },
  { provider_name: "resend", label: "Resend", description: "Resend transactional email API." },
  { provider_name: "sendgrid", label: "SendGrid", description: "SendGrid email API." },
  { provider_name: "mailgun", label: "Mailgun", description: "Mailgun email API." },
];

const configureSchema = z.record(z.string(), z.union([z.string(), z.boolean()]));

type ConfigureValues = z.infer<typeof configureSchema>;

function statusBadge(credential: ProviderCredential | undefined) {
  if (!credential) {
    return <Badge variant="outline">Not configured</Badge>;
  }
  if (credential.is_active) {
    return <Badge>Active</Badge>;
  }
  if (credential.status === "error") {
    return <Badge variant="destructive">Error</Badge>;
  }
  if (credential.status === "configured") {
    return <Badge variant="secondary">Configured</Badge>;
  }
  return <Badge variant="outline">Not configured</Badge>;
}

function SecretInput({
  label,
  placeholder,
  register,
  name,
}: {
  label: string;
  placeholder?: string;
  register: ReturnType<typeof useForm<ConfigureValues>>["register"];
  name: string;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium">{label}</label>
      <div className="flex gap-2">
        <Input
          type={visible ? "text" : "password"}
          placeholder={placeholder}
          autoComplete="off"
          {...register(name)}
        />
        <Button type="button" variant="outline" onClick={() => setVisible((v) => !v)}>
          {visible ? "Hide" : "Show"}
        </Button>
      </div>
    </div>
  );
}

function ProviderFields({
  providerName,
  register,
  isEditing,
}: {
  providerName: ProviderName;
  register: ReturnType<typeof useForm<ConfigureValues>>["register"];
  isEditing: boolean;
}) {
  const secretPlaceholder = isEditing ? "Leave blank to keep existing key" : undefined;

  if (providerName === "google_cse") {
    return (
      <>
        <SecretInput label="API key" placeholder={secretPlaceholder} register={register} name="api_key" />
        <SecretInput
          label="Search engine ID"
          placeholder={secretPlaceholder}
          register={register}
          name="search_engine_id"
        />
      </>
    );
  }
  if (providerName === "bing") {
    return (
      <>
        <SecretInput label="API key" placeholder={secretPlaceholder} register={register} name="api_key" />
        <div className="space-y-2">
          <label className="text-sm font-medium">Endpoint</label>
          <Input
            placeholder="https://api.bing.microsoft.com/v7.0/search"
            {...register("endpoint")}
          />
        </div>
      </>
    );
  }
  if (providerName === "serpapi") {
    return <SecretInput label="API key" placeholder={secretPlaceholder} register={register} name="api_key" />;
  }
  if (providerName === "smtp") {
    return (
      <>
        <div className="space-y-2">
          <label className="text-sm font-medium">Host</label>
          <Input {...register("host")} />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium">Port</label>
          <Input type="number" {...register("port")} />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium">Username</label>
          <Input {...register("username")} />
        </div>
        <SecretInput label="Password" placeholder={secretPlaceholder} register={register} name="password" />
        <div className="space-y-2">
          <label className="text-sm font-medium">From email</label>
          <Input {...register("from_email")} />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium">From name</label>
          <Input {...register("from_name")} />
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" {...register("use_tls")} className="rounded border" />
          Use TLS
        </label>
      </>
    );
  }
  if (providerName === "resend" || providerName === "sendgrid") {
    return (
      <>
        <SecretInput label="API key" placeholder={secretPlaceholder} register={register} name="api_key" />
        <div className="space-y-2">
          <label className="text-sm font-medium">From email</label>
          <Input {...register("from_email")} />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium">From name</label>
          <Input {...register("from_name")} />
        </div>
      </>
    );
  }
  if (providerName === "mailgun") {
    return (
      <>
        <SecretInput label="API key" placeholder={secretPlaceholder} register={register} name="api_key" />
        <div className="space-y-2">
          <label className="text-sm font-medium">Domain</label>
          <Input {...register("domain")} />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium">From email</label>
          <Input {...register("from_email")} />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium">From name</label>
          <Input {...register("from_name")} />
        </div>
      </>
    );
  }
  return <p className="text-sm text-muted-foreground">No credentials required for mock provider.</p>;
}

function ProviderCard({
  definition,
  providerType,
  credential,
  onConfigure,
  onTest,
  onActivate,
  onDelete,
  busyId,
}: {
  definition: ProviderDefinition;
  providerType: ProviderType;
  credential?: ProviderCredential;
  onConfigure: () => void;
  onTest: (id: number) => void;
  onActivate: (id: number) => void;
  onDelete: (id: number) => void;
  busyId: number | null;
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base">{definition.label}</CardTitle>
            <p className="text-muted-foreground mt-1 text-sm">{definition.description}</p>
          </div>
          <div className="flex flex-col items-end gap-1">
            {statusBadge(credential)}
            {credential?.is_active ? <Badge variant="secondary">In use</Badge> : null}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {credential?.masked_summary ? (
          <p className="text-muted-foreground">{credential.masked_summary}</p>
        ) : (
          <p className="text-muted-foreground">No saved configuration yet.</p>
        )}
        {credential?.last_tested_at ? (
          <p className="text-muted-foreground text-xs">
            Last tested: {new Date(credential.last_tested_at).toLocaleString()} —{" "}
            {credential.last_test_status}
            {credential.last_test_message ? `: ${credential.last_test_message}` : ""}
          </p>
        ) : null}
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={onConfigure}>
            Configure
          </Button>
          {credential ? (
            <>
              <Button
                size="sm"
                variant="outline"
                disabled={busyId === credential.id}
                onClick={() => onTest(credential.id)}
              >
                Test connection
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={credential.is_active || busyId === credential.id}
                onClick={() => onActivate(credential.id)}
              >
                Set active
              </Button>
              {definition.provider_name !== "mock" ? (
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={busyId === credential.id}
                  onClick={() => onDelete(credential.id)}
                >
                  Delete
                </Button>
              ) : null}
            </>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

export function ProviderSettingsPanel() {
  const queryClient = useQueryClient();
  const [configureTarget, setConfigureTarget] = useState<{
    providerType: ProviderType;
    definition: ProviderDefinition;
    credential?: ProviderCredential;
  } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ProviderCredential | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["provider-settings"],
    queryFn: providerSettingsApi.list,
  });

  const credentialsByKey = useMemo(() => {
    const map = new Map<string, ProviderCredential>();
    for (const item of data?.items ?? []) {
      map.set(`${item.provider_type}:${item.provider_name}`, item);
    }
    return map;
  }, [data?.items]);

  const {
    register,
    handleSubmit,
    reset,
    formState: { isSubmitting },
  } = useForm<ConfigureValues>({
    resolver: zodResolver(configureSchema),
    defaultValues: {},
  });

  const saveMutation = useMutation({
    mutationFn: (values: ConfigureValues) => {
      if (!configureTarget) throw new Error("No provider selected");
      const config: Record<string, string | boolean> = {};
      for (const [key, value] of Object.entries(values)) {
        if (typeof value === "boolean") {
          config[key] = value;
        } else if (typeof value === "string" && value.trim()) {
          config[key] = value.trim();
        }
      }
      return providerSettingsApi.upsert({
        provider_type: configureTarget.providerType,
        provider_name: configureTarget.definition.provider_name,
        config,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["provider-settings"] });
      toast.success("Provider settings saved");
      setConfigureTarget(null);
      reset({});
    },
    onError: (error: Error) => toast.error(error.message || "Could not save provider settings"),
  });

  const testMutation = useMutation({
    mutationFn: (id: number) => providerSettingsApi.test(id),
    onMutate: (id) => setBusyId(id),
    onSettled: () => setBusyId(null),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["provider-settings"] });
      if (result.success) toast.success(result.message);
      else toast.error(result.message);
    },
    onError: () => toast.error("Connection test failed"),
  });

  const activateMutation = useMutation({
    mutationFn: (id: number) => providerSettingsApi.activate(id),
    onMutate: (id) => setBusyId(id),
    onSettled: () => setBusyId(null),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["provider-settings"] });
      toast.success("Provider activated");
    },
    onError: (error: Error) => toast.error(error.message || "Could not activate provider"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => providerSettingsApi.delete(id),
    onMutate: (id) => setBusyId(id),
    onSettled: () => setBusyId(null),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["provider-settings"] });
      toast.success("Provider credentials deleted");
      setDeleteTarget(null);
    },
    onError: () => toast.error("Could not delete provider credentials"),
  });

  const openConfigure = (
    providerType: ProviderType,
    definition: ProviderDefinition,
    credential?: ProviderCredential,
  ) => {
    reset({});
    setConfigureTarget({ providerType, definition, credential });
  };

  const renderGrid = (providerType: ProviderType, definitions: ProviderDefinition[]) => (
    <div className="grid gap-4 md:grid-cols-2">
      {definitions.map((definition) => {
        const credential = credentialsByKey.get(`${providerType}:${definition.provider_name}`);
        return (
          <ProviderCard
            key={definition.provider_name}
            definition={definition}
            providerType={providerType}
            credential={credential}
            busyId={busyId}
            onConfigure={() => openConfigure(providerType, definition, credential)}
            onTest={(id) => testMutation.mutate(id)}
            onActivate={(id) => activateMutation.mutate(id)}
            onDelete={(id) => {
              const target = data?.items.find((item) => item.id === id);
              if (target) setDeleteTarget(target);
            }}
          />
        );
      })}
    </div>
  );

  return (
    <Card className="lg:col-span-2">
      <CardHeader>
        <CardTitle>Provider configuration</CardTitle>
        <p className="text-muted-foreground text-sm">
          Configure search and email providers. API keys are encrypted and stored securely on the
          backend. Full secrets are never shown after saving.
        </p>
      </CardHeader>
      <CardContent>
        {isLoading ? <p className="text-muted-foreground text-sm">Loading providers…</p> : null}
        <Tabs defaultValue="search">
          <TabsList>
            <TabsTrigger value="search">Search providers</TabsTrigger>
            <TabsTrigger value="email">Email providers</TabsTrigger>
          </TabsList>
          <TabsContent value="search" className="mt-4">
            {renderGrid("search", SEARCH_PROVIDERS)}
          </TabsContent>
          <TabsContent value="email" className="mt-4">
            {renderGrid("email", EMAIL_PROVIDERS)}
          </TabsContent>
        </Tabs>
      </CardContent>

      <Dialog
        open={configureTarget !== null}
        onOpenChange={(open) => {
          if (!open) setConfigureTarget(null);
        }}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Configure {configureTarget?.definition.label}</DialogTitle>
            <DialogDescription>
              Credentials are encrypted on the server. Leave secret fields blank when updating to
              keep the existing value.
            </DialogDescription>
          </DialogHeader>
          {configureTarget ? (
            <form
              onSubmit={handleSubmit((values) => saveMutation.mutate(values))}
              className="space-y-4"
            >
              <ProviderFields
                providerName={configureTarget.definition.provider_name}
                register={register}
                isEditing={Boolean(configureTarget.credential)}
              />
              <DialogFooter>
                <Button type="submit" disabled={isSubmitting || saveMutation.isPending}>
                  Save configuration
                </Button>
              </DialogFooter>
            </form>
          ) : null}
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        title="Delete provider credentials?"
        description={`Remove saved credentials for ${deleteTarget?.display_name}? This cannot be undone.`}
        confirmLabel="Delete"
        destructive
        loading={deleteMutation.isPending}
        onConfirm={() => {
          if (deleteTarget) deleteMutation.mutate(deleteTarget.id);
        }}
      />
    </Card>
  );
}
