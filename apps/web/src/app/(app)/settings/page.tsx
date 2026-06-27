"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  AlertTriangle,
  Building2,
  CheckCircle2,
  Lock,
  Mail,
  Plus,
  Server,
  Settings,
  Shield,
  Trash2,
  User,
} from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { ProviderSettingsPanel } from "@/components/settings/provider-settings-panel";
import { settingsApi } from "@/lib/api/endpoints";
import { settingsSchema, type SettingsFormValues } from "@/lib/validations/forms";

const COMPLIANCE_POLICIES = [
  {
    icon: Shield,
    title: "No LinkedIn Automation",
    description:
      "LinkedIn login, scraping, profile crawling, messaging, and connection automation are permanently disabled.",
  },
  {
    icon: Shield,
    title: "No Google SERP Scraping",
    description:
      "Direct scraping of Google search result HTML is not permitted. Use approved API providers only.",
  },
  {
    icon: CheckCircle2,
    title: "Manual Approval Before Send",
    description:
      "Every email message must be manually approved before it can be queued. No one-click mass sending.",
  },
  {
    icon: CheckCircle2,
    title: "Suppression Check on Every Send",
    description: "Email and domain suppression lists are checked before every send attempt.",
  },
  {
    icon: CheckCircle2,
    title: "Source URL Required",
    description:
      "Every lead and contact must have a recorded source URL before email can be generated.",
  },
  {
    icon: CheckCircle2,
    title: "Compliance Note Required",
    description:
      "A compliance/source note documenting data origin must exist before email can be generated.",
  },
  {
    icon: Mail,
    title: "Opt-Out Line in Every Email",
    description:
      "All outreach emails must include a compliant opt-out line. Sending is blocked without it.",
  },
  {
    icon: AlertTriangle,
    title: "Unsubscribe Adds Suppression",
    description:
      "Clicking the unsubscribe link automatically adds the contact to the suppression list.",
  },
  {
    icon: Server,
    title: "Per-Domain Send Throttle",
    description:
      "Multiple sends to the same domain within a period are rate-limited to avoid appearing as spam.",
  },
  {
    icon: Lock,
    title: "Audit Trail on All Sends",
    description: "Every email send attempt is logged with timestamp, status, and outcome.",
  },
];

const TABS = [
  { id: "sender", label: "Sender Profile", icon: User },
  { id: "providers", label: "Providers", icon: Settings },
  { id: "suppressions", label: "Suppressions", icon: Shield },
  { id: "compliance", label: "Compliance Policy", icon: Lock },
];

function InputRow({
  label,
  id,
  ...props
}: { label: string; id: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div>
      <label
        htmlFor={id}
        className="block text-[13px] font-medium mb-1.5"
        style={{ color: "var(--on-surface)" }}
      >
        {label}
      </label>
      <input
        id={id}
        className="w-full px-3 py-2.5 border rounded text-[13px] outline-none"
        style={{
          borderColor: "var(--outline-variant)",
          color: "var(--on-surface)",
          background: "var(--surface-container-lowest)",
        }}
        onFocus={(e) => {
          e.target.style.borderColor = "var(--primary)";
          e.target.style.boxShadow = "0 0 0 1px var(--primary)";
        }}
        onBlur={(e) => {
          e.target.style.borderColor = "var(--outline-variant)";
          e.target.style.boxShadow = "none";
        }}
        {...props}
      />
    </div>
  );
}

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState("sender");
  const [suppressionEmail, setSuppressionEmail] = useState("");

  const { data: settingsData } = useQuery({
    queryKey: ["settings"],
    queryFn: settingsApi.get,
  });

  const { data: suppressions } = useQuery({
    queryKey: ["suppressions"],
    queryFn: settingsApi.listSuppressions,
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { isSubmitting },
  } = useForm<SettingsFormValues>({
    resolver: zodResolver(settingsSchema),
    defaultValues: {
      sender_name: "",
      sender_company: "",
      business_address: "",
    },
  });

  useEffect(() => {
    if (settingsData) {
      reset({
        sender_name: settingsData.sender_name ?? "",
        sender_company: settingsData.sender_company ?? "",
        business_address: settingsData.business_address ?? "",
      });
    }
  }, [settingsData, reset]);

  const saveMutation = useMutation({
    mutationFn: (values: SettingsFormValues) =>
      settingsApi.update({
        sender_name: values.sender_name || null,
        sender_company: values.sender_company || null,
        business_address: values.business_address || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      toast.success("Settings saved");
    },
    onError: () => toast.error("Failed to save settings"),
  });

  const addSuppressionMutation = useMutation({
    mutationFn: () =>
      settingsApi.createSuppression({ email: suppressionEmail, reason: "manual" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["suppressions"] });
      setSuppressionEmail("");
      toast.success("Suppression added");
    },
    onError: () => toast.error("Could not add suppression"),
  });

  const deleteSuppressionMutation = useMutation({
    mutationFn: (id: number) => settingsApi.deleteSuppression(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["suppressions"] });
      toast.success("Suppression removed");
    },
  });

  return (
    <div>
      <PageHeader
        title="Settings"
        description="Sender identity, provider credentials, suppression lists, and compliance policy."
      />

      {/* Tab bar */}
      <div
        className="flex items-center gap-1 border-b mb-6"
        style={{ borderColor: "var(--outline-variant)" }}
      >
        {TABS.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className="flex items-center gap-2 px-4 py-3 text-[13px] font-medium border-b-2 -mb-px transition-colors"
              style={{
                color: activeTab === tab.id ? "var(--primary)" : "var(--on-surface-variant)",
                borderColor: activeTab === tab.id ? "var(--primary)" : "transparent",
              }}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Sender Profile tab */}
      {activeTab === "sender" && (
        <div className="max-w-[520px]">
          <div
            className="bg-white border rounded-lg p-6 shadow-sm"
            style={{ borderColor: "var(--outline-variant)" }}
          >
            <div className="flex items-center gap-2 mb-6">
              <Building2 className="w-5 h-5" style={{ color: "var(--primary)" }} />
              <h3 className="text-[16px] font-semibold" style={{ color: "var(--on-surface)" }}>
                Sender Profile
              </h3>
            </div>
            <form
              onSubmit={handleSubmit((values) => saveMutation.mutate(values))}
              className="flex flex-col gap-5"
            >
              <InputRow
                label="Sender name"
                id="sender_name"
                placeholder="Jane Doe"
                {...register("sender_name")}
              />
              <InputRow
                label="Sender company"
                id="sender_company"
                placeholder="Acme Corp"
                {...register("sender_company")}
              />
              <InputRow
                label="Business address"
                id="business_address"
                placeholder="123 Main St, San Francisco, CA 94102"
                {...register("business_address")}
              />
              <button
                type="submit"
                disabled={isSubmitting || saveMutation.isPending}
                className="self-start flex items-center gap-2 px-5 py-2.5 rounded text-[13px] font-medium text-white transition-colors disabled:opacity-60"
                style={{ background: "var(--primary)" }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.background = "var(--surface-tint)")
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.background = "var(--primary)")
                }
              >
                {saveMutation.isPending ? "Saving…" : "Save Settings"}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Providers tab */}
      {activeTab === "providers" && <ProviderSettingsPanel />}

      {/* Suppressions tab */}
      {activeTab === "suppressions" && (
        <div className="space-y-4">
          {/* Add form */}
          <div
            className="bg-white border rounded-lg p-5 shadow-sm"
            style={{ borderColor: "var(--outline-variant)" }}
          >
            <h3
              className="text-[14px] font-semibold mb-3"
              style={{ color: "var(--on-surface)" }}
            >
              Add to Suppression List
            </h3>
            <div className="flex gap-3">
              <input
                type="text"
                placeholder="email@example.com or domain.com"
                value={suppressionEmail}
                onChange={(e) => setSuppressionEmail(e.target.value)}
                className="flex-1 px-3 py-2 border rounded text-[13px] outline-none"
                style={{
                  borderColor: "var(--outline-variant)",
                  color: "var(--on-surface)",
                }}
                onFocus={(e) => {
                  e.target.style.borderColor = "var(--primary)";
                  e.target.style.boxShadow = "0 0 0 1px var(--primary)";
                }}
                onBlur={(e) => {
                  e.target.style.borderColor = "var(--outline-variant)";
                  e.target.style.boxShadow = "none";
                }}
              />
              <button
                onClick={() => addSuppressionMutation.mutate()}
                disabled={!suppressionEmail || addSuppressionMutation.isPending}
                className="flex items-center gap-2 px-4 py-2 rounded text-[13px] font-medium text-white disabled:opacity-60"
                style={{ background: "var(--primary)" }}
              >
                <Plus className="w-4 h-4" />
                Add
              </button>
            </div>
          </div>

          {/* Suppressions table */}
          <div
            className="bg-white border rounded-lg shadow-sm overflow-hidden"
            style={{ borderColor: "var(--outline-variant)" }}
          >
            {(suppressions?.items ?? []).length === 0 ? (
              <div className="p-12 text-center">
                <Shield className="w-8 h-8 mx-auto mb-3" style={{ color: "var(--outline)" }} />
                <p className="text-[13px]" style={{ color: "var(--on-surface-variant)" }}>
                  No suppressions yet. Unsubscribes add contacts automatically.
                </p>
              </div>
            ) : (
              <table className="w-full text-left">
                <thead>
                  <tr
                    className="border-b"
                    style={{ background: "var(--surface)", borderColor: "var(--outline-variant)" }}
                  >
                    {["Email / Domain", "Reason", "Source", "Actions"].map((h) => (
                      <th
                        key={h}
                        className={`py-3 px-5 text-[11px] font-semibold uppercase tracking-wider ${
                          h === "Actions" ? "text-right" : ""
                        }`}
                        style={{ color: "var(--on-surface-variant)" }}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(suppressions?.items ?? []).map((item) => (
                    <tr
                      key={item.id}
                      className="border-b group transition-colors"
                      style={{ borderColor: "var(--outline-variant)" }}
                      onMouseEnter={(e) =>
                        (e.currentTarget.style.background = "var(--surface-container-low)")
                      }
                      onMouseLeave={(e) =>
                        (e.currentTarget.style.background = "transparent")
                      }
                    >
                      <td className="py-3.5 px-5 text-[13px]" style={{ color: "var(--on-surface)" }}>
                        {item.email ?? item.domain ?? "—"}
                      </td>
                      <td
                        className="py-3.5 px-5 text-[13px]"
                        style={{ color: "var(--on-surface-variant)" }}
                      >
                        {item.reason ?? "—"}
                      </td>
                      <td
                        className="py-3.5 px-5 text-[12px]"
                        style={{ color: "var(--on-surface-variant)" }}
                      >
                        Manual
                      </td>
                      <td className="py-3.5 px-5 text-right">
                        <button
                          onClick={() => deleteSuppressionMutation.mutate(item.id)}
                          className="opacity-0 group-hover:opacity-100 p-1.5 rounded transition-all"
                          title="Remove"
                          style={{ color: "var(--on-surface-variant)" }}
                          onMouseEnter={(e) => (e.currentTarget.style.color = "var(--error)")}
                          onMouseLeave={(e) =>
                            (e.currentTarget.style.color = "var(--on-surface-variant)")
                          }
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* Compliance Policy tab */}
      {activeTab === "compliance" && (
        <div>
          <div
            className="flex items-start gap-4 p-4 rounded-lg border mb-6"
            style={{
              background: "var(--primary-fixed)",
              borderColor: "var(--primary)",
              color: "var(--on-primary-fixed)",
            }}
          >
            <Lock className="w-5 h-5 mt-0.5 shrink-0" style={{ color: "var(--primary)" }} />
            <div>
              <p className="text-[13px] font-semibold mb-1" style={{ color: "var(--primary)" }}>
                Compliance Policy — Read Only
              </p>
              <p className="text-[13px]" style={{ color: "var(--on-primary-fixed)" }}>
                These rules are permanently enforced by the system and cannot be disabled.
                They apply to all accounts and cannot be overridden by user configuration.
              </p>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            {COMPLIANCE_POLICIES.map((policy) => {
              const Icon = policy.icon;
              return (
                <div
                  key={policy.title}
                  className="bg-white border rounded-lg p-5 shadow-sm flex items-start gap-4"
                  style={{ borderColor: "var(--outline-variant)" }}
                >
                  <div
                    className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
                    style={{ background: "var(--primary-fixed)" }}
                  >
                    <Icon className="w-4 h-4" style={{ color: "var(--primary)" }} />
                  </div>
                  <div>
                    <p
                      className="text-[13px] font-semibold mb-1 flex items-center gap-2"
                      style={{ color: "var(--on-surface)" }}
                    >
                      {policy.title}
                      <Lock className="w-3 h-3" style={{ color: "var(--outline)" }} />
                    </p>
                    <p className="text-[13px]" style={{ color: "var(--on-surface-variant)" }}>
                      {policy.description}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
