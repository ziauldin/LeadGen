"use client";

import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { z } from "zod";
import {
  CheckCircle2,
  Eye,
  EyeOff,
  Mail,
  RefreshCw,
  Search,
  Settings,
  Trash2,
  XCircle,
} from "lucide-react";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { providerSettingsApi } from "@/lib/api/endpoints";
import type { ProviderCredential, ProviderName, ProviderType } from "@/lib/api/types";

type ProviderDefinition = {
  provider_name: ProviderName;
  label: string;
  description: string;
};

const SEARCH_PROVIDERS: ProviderDefinition[] = [
  { provider_name: "mock", label: "Mock Search", description: "Local test results — no API key required." },
  {
    provider_name: "google_cse",
    label: "Google CSE",
    description: "Google Programmable Search JSON API.",
  },
  { provider_name: "bing", label: "Bing Search", description: "Microsoft Bing Web Search API." },
  { provider_name: "serpapi", label: "SerpAPI", description: "SerpAPI search results." },
];

const EMAIL_PROVIDERS: ProviderDefinition[] = [
  { provider_name: "mock", label: "Mock Sender", description: "Simulated sends for local testing." },
  { provider_name: "smtp", label: "SMTP Server", description: "Direct SMTP delivery." },
  { provider_name: "resend", label: "Resend", description: "Resend transactional email API." },
  { provider_name: "sendgrid", label: "SendGrid", description: "SendGrid email API." },
  { provider_name: "mailgun", label: "Mailgun", description: "Mailgun email API." },
];

const configureSchema = z.record(z.string(), z.union([z.string(), z.boolean()]));

type ConfigureValues = z.infer<typeof configureSchema>;

function ProviderStatusBadge({ credential }: { credential: ProviderCredential | undefined }) {
  if (!credential) {
    return (
      <span
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold"
        style={{ background: "var(--surface-container)", color: "var(--on-surface-variant)" }}
      >
        Not configured
      </span>
    );
  }
  if (credential.is_active) {
    return (
      <span
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold"
        style={{ background: "var(--secondary-fixed)", color: "var(--on-secondary-fixed)" }}
      >
        <CheckCircle2 className="w-3 h-3" />
        Active
      </span>
    );
  }
  if (credential.status === "error") {
    return (
      <span
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold"
        style={{ background: "var(--error-container)", color: "var(--on-error-container)" }}
      >
        <XCircle className="w-3 h-3" />
        Error
      </span>
    );
  }
  if (credential.status === "configured") {
    return (
      <span
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold"
        style={{ background: "var(--primary-fixed)", color: "var(--on-primary-fixed)" }}
      >
        Configured
      </span>
    );
  }
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold"
      style={{ background: "var(--surface-container)", color: "var(--on-surface-variant)" }}
    >
      Not configured
    </span>
  );
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
    <div>
      <label className="block text-[12px] font-semibold mb-1" style={{ color: "var(--on-surface)" }}>
        {label}
      </label>
      <div className="relative">
        <input
          type={visible ? "text" : "password"}
          placeholder={placeholder}
          autoComplete="off"
          {...register(name)}
          className="w-full pl-3 pr-10 py-2 border rounded text-[13px] outline-none"
          style={{
            borderColor: "var(--outline-variant)",
            color: "var(--on-surface)",
            background: "var(--surface-container-lowest)",
          }}
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          className="absolute right-3 top-1/2 -translate-y-1/2 opacity-70 hover:opacity-100"
          style={{ color: "var(--on-surface-variant)" }}
        >
          {visible ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
        </button>
      </div>
    </div>
  );
}

function TextInput({
  label,
  placeholder,
  register,
  name,
  type = "text",
}: {
  label: string;
  placeholder?: string;
  register: ReturnType<typeof useForm<ConfigureValues>>["register"];
  name: string;
  type?: string;
}) {
  return (
    <div>
      <label className="block text-[12px] font-semibold mb-1" style={{ color: "var(--on-surface)" }}>
        {label}
      </label>
      <input
        type={type}
        placeholder={placeholder}
        {...register(name)}
        className="w-full px-3 py-2 border rounded text-[13px] outline-none"
        style={{
          borderColor: "var(--outline-variant)",
          color: "var(--on-surface)",
          background: "var(--surface-container-lowest)",
        }}
      />
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
      <div className="space-y-4">
        <SecretInput label="API key" placeholder={secretPlaceholder} register={register} name="api_key" />
        <SecretInput
          label="Search engine ID"
          placeholder={secretPlaceholder}
          register={register}
          name="search_engine_id"
        />
      </div>
    );
  }
  if (providerName === "bing") {
    return (
      <div className="space-y-4">
        <SecretInput label="API key" placeholder={secretPlaceholder} register={register} name="api_key" />
        <TextInput
          label="Endpoint"
          placeholder="https://api.bing.microsoft.com/v7.0/search"
          register={register}
          name="endpoint"
        />
      </div>
    );
  }
  if (providerName === "serpapi") {
    return <SecretInput label="API key" placeholder={secretPlaceholder} register={register} name="api_key" />;
  }
  if (providerName === "smtp") {
    return (
      <div className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="sm:col-span-2">
            <TextInput label="Host" placeholder="smtp.mailtrap.io" register={register} name="host" />
          </div>
          <div>
            <TextInput label="Port" placeholder="587" register={register} name="port" type="number" />
          </div>
        </div>
        <TextInput label="Username" placeholder="username" register={register} name="username" />
        <SecretInput label="Password" placeholder={secretPlaceholder} register={register} name="password" />
        <div className="grid gap-4 sm:grid-cols-2">
          <TextInput label="From email" placeholder="sender@yourdomain.com" register={register} name="from_email" />
          <TextInput label="From name" placeholder="Jane Doe" register={register} name="from_name" />
        </div>
        <label className="flex items-center gap-2 text-[13px] cursor-pointer">
          <input type="checkbox" {...register("use_tls")} className="rounded" />
          <span style={{ color: "var(--on-surface)" }}>Use TLS / StartTLS</span>
        </label>
      </div>
    );
  }
  if (providerName === "resend" || providerName === "sendgrid") {
    return (
      <div className="space-y-4">
        <SecretInput label="API key" placeholder={secretPlaceholder} register={register} name="api_key" />
        <div className="grid gap-4 sm:grid-cols-2">
          <TextInput label="From email" placeholder="sender@yourdomain.com" register={register} name="from_email" />
          <TextInput label="From name" placeholder="Jane Doe" register={register} name="from_name" />
        </div>
      </div>
    );
  }
  if (providerName === "mailgun") {
    return (
      <div className="space-y-4">
        <SecretInput label="API key" placeholder={secretPlaceholder} register={register} name="api_key" />
        <TextInput label="Domain" placeholder="mg.yourdomain.com" register={register} name="domain" />
        <div className="grid gap-4 sm:grid-cols-2">
          <TextInput label="From email" placeholder="sender@yourdomain.com" register={register} name="from_email" />
          <TextInput label="From name" placeholder="Jane Doe" register={register} name="from_name" />
        </div>
      </div>
    );
  }
  return (
    <div
      className="p-3 rounded text-[13px]"
      style={{ background: "var(--surface-container-low)", color: "var(--on-surface-variant)" }}
    >
      No authentication key is required for mock simulated providers.
    </div>
  );
}

export function ProviderSettingsPanel() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<"search" | "email">("search");
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
      toast.success("Provider credentials updated");
      setConfigureTarget(null);
      reset({});
    },
    onError: (error: Error) => toast.error(error.message || "Failed to save configuration"),
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
      toast.success("Provider set active successfully");
    },
    onError: (error: Error) => toast.error(error.message || "Could not set provider active"),
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
    onError: () => toast.error("Could not delete credentials"),
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
        const isActive = credential?.is_active ?? false;
        const Icon = providerType === "search" ? Search : Mail;

        return (
          <div
            key={definition.provider_name}
            className="bg-white border rounded-lg p-5 shadow-sm flex flex-col justify-between"
            style={{
              borderColor: isActive ? "var(--primary)" : "var(--outline-variant)",
              boxShadow: isActive ? "0px 4px 6px -1px rgba(53,37,205,0.08)" : "none",
            }}
          >
            <div>
              <div className="flex items-start justify-between gap-3 mb-2">
                <div className="flex items-center gap-2">
                  <div
                    className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
                    style={{ background: "var(--surface-container-low)" }}
                  >
                    <Icon className="w-4.5 h-4.5" style={{ color: "var(--primary)" }} />
                  </div>
                  <h4 className="text-[14px] font-semibold" style={{ color: "var(--on-surface)" }}>
                    {definition.label}
                  </h4>
                </div>
                <ProviderStatusBadge credential={credential} />
              </div>

              <p className="text-[13px] mb-4" style={{ color: "var(--on-surface-variant)" }}>
                {definition.description}
              </p>

              {credential?.masked_summary && (
                <div
                  className="mb-4 px-2.5 py-1.5 rounded font-mono text-[11px]"
                  style={{ background: "var(--surface-container-low)", color: "var(--on-surface)" }}
                >
                  {credential.masked_summary}
                </div>
              )}

              {credential?.last_tested_at && (
                <p className="text-[11px] mb-4" style={{ color: "var(--on-surface-variant)" }}>
                  Last test: {new Date(credential.last_tested_at).toLocaleDateString()} —{" "}
                  <span
                    style={{
                      color:
                        credential.last_test_status === "success"
                          ? "var(--secondary)"
                          : "var(--error)",
                    }}
                  >
                    {credential.last_test_status}
                  </span>
                </p>
              )}
            </div>

            <div
              className="flex items-center justify-between pt-4 border-t"
              style={{ borderColor: "var(--outline-variant)" }}
            >
              <div className="flex items-center gap-2">
                <button
                  onClick={() => openConfigure(providerType, definition, credential)}
                  className="px-3 py-1.5 border rounded text-[12px] font-semibold transition-colors bg-white"
                  style={{ borderColor: "var(--outline-variant)", color: "var(--on-surface)" }}
                >
                  Configure
                </button>
                {credential && (
                  <button
                    onClick={() => testMutation.mutate(credential.id)}
                    disabled={busyId === credential.id || testMutation.isPending}
                    className="px-3 py-1.5 border rounded text-[12px] font-semibold transition-colors bg-white disabled:opacity-50"
                    style={{ borderColor: "var(--outline-variant)", color: "var(--on-surface)" }}
                  >
                    {busyId === credential.id ? "Testing…" : "Test API"}
                  </button>
                )}
              </div>

              {credential && !isActive && (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => activateMutation.mutate(credential.id)}
                    disabled={busyId === credential.id}
                    className="px-3 py-1.5 rounded text-[12px] font-semibold text-white transition-colors disabled:opacity-50"
                    style={{ background: "var(--primary)" }}
                  >
                    Activate
                  </button>
                  {definition.provider_name !== "mock" && (
                    <button
                      onClick={() => setDeleteTarget(credential)}
                      disabled={busyId === credential.id}
                      className="p-1.5 rounded text-[13px] hover:text-red-500 transition-colors"
                      style={{ color: "var(--on-surface-variant)" }}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );

  return (
    <div className="flex flex-col gap-6 lg:col-span-2">
      <div
        className="bg-white border rounded-lg p-6 shadow-sm"
        style={{ borderColor: "var(--outline-variant)" }}
      >
        <div className="flex items-center gap-2.5 mb-2">
          <Settings className="w-5 h-5 text-indigo-600" />
          <h3 className="text-[16px] font-semibold" style={{ color: "var(--on-surface)" }}>
            Provider Credentials
          </h3>
        </div>
        <p className="text-[13px] mb-6" style={{ color: "var(--on-surface-variant)" }}>
          Manage search querying and email outreach servers. Credentials are AES-encrypted at rest and
          never revealed in plain-text after creation.
        </p>

        {/* Tab switcher */}
        <div
          className="flex items-center gap-2 p-1 rounded-lg w-fit mb-6"
          style={{ background: "var(--surface-container-low)" }}
        >
          <button
            onClick={() => setActiveTab("search")}
            className="px-4 py-1.5 rounded-md text-[13px] font-semibold transition-all"
            style={{
              background: activeTab === "search" ? "var(--surface-container-lowest)" : "transparent",
              color: activeTab === "search" ? "var(--primary)" : "var(--on-surface-variant)",
              boxShadow: activeTab === "search" ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
            }}
          >
            Search APIs
          </button>
          <button
            onClick={() => setActiveTab("email")}
            className="px-4 py-1.5 rounded-md text-[13px] font-semibold transition-all"
            style={{
              background: activeTab === "email" ? "var(--surface-container-lowest)" : "transparent",
              color: activeTab === "email" ? "var(--primary)" : "var(--on-surface-variant)",
              boxShadow: activeTab === "email" ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
            }}
          >
            Email Gateways
          </button>
        </div>

        {isLoading ? (
          <div className="p-8 text-center">
            <RefreshCw className="w-5 h-5 animate-spin mx-auto text-indigo-600" />
          </div>
        ) : activeTab === "search" ? (
          renderGrid("search", SEARCH_PROVIDERS)
        ) : (
          renderGrid("email", EMAIL_PROVIDERS)
        )}
      </div>

      {/* Configuration Dialog */}
      {configureTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-in fade-in duration-200">
          <div
            className="bg-white border rounded-xl w-full max-w-[500px] shadow-lg overflow-hidden flex flex-col"
            style={{ borderColor: "var(--outline-variant)" }}
          >
            <div
              className="px-6 py-4 border-b flex items-center justify-between"
              style={{ borderColor: "var(--outline-variant)" }}
            >
              <div>
                <h3 className="text-[16px] font-bold" style={{ color: "var(--on-surface)" }}>
                  Configure {configureTarget.definition.label}
                </h3>
                <p className="text-[12px] mt-0.5" style={{ color: "var(--on-surface-variant)" }}>
                  Encryption and secure key storage active.
                </p>
              </div>
              <button
                onClick={() => setConfigureTarget(null)}
                className="text-slate-400 hover:text-slate-600 font-semibold text-[18px]"
              >
                ×
              </button>
            </div>

            <form
              onSubmit={handleSubmit((values) => saveMutation.mutate(values))}
              className="p-6 flex flex-col gap-4 overflow-y-auto max-h-[70vh]"
            >
              <ProviderFields
                providerName={configureTarget.definition.provider_name}
                register={register}
                isEditing={Boolean(configureTarget.credential)}
              />

              <div
                className="flex items-center justify-end gap-3 pt-4 border-t mt-2"
                style={{ borderColor: "var(--outline-variant)" }}
              >
                <button
                  type="button"
                  onClick={() => setConfigureTarget(null)}
                  className="px-4 py-2 border rounded text-[13px] font-semibold bg-white"
                  style={{ borderColor: "var(--outline-variant)", color: "var(--on-surface)" }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || saveMutation.isPending}
                  className="px-5 py-2 rounded text-[13px] font-semibold text-white transition-opacity disabled:opacity-60"
                  style={{ background: "var(--primary)" }}
                >
                  Save Configuration
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirm */}
      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        title="Delete provider credentials?"
        description={`Are you sure you want to permanently delete saved credentials for ${deleteTarget?.display_name}? This cannot be undone.`}
        confirmLabel="Delete Credentials"
        destructive
        loading={deleteMutation.isPending}
        onConfirm={() => {
          if (deleteTarget) deleteMutation.mutate(deleteTarget.id);
        }}
      />
    </div>
  );
}
