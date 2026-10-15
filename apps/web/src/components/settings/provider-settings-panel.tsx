"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { ErrorState } from "@/components/shared/loading-error";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AdminOnlyNotice } from "@/components/settings/settings-card";
import {
  PROVIDER_TYPES,
  type ProviderDefinition,
} from "@/components/settings/providers/provider-catalog";
import { ProviderCard } from "@/components/settings/providers/provider-card";
import { ProviderConfigDialog } from "@/components/settings/providers/provider-config-dialog";
import { useWorkspace } from "@/hooks/use-workspace";
import { providerSettingsApi } from "@/lib/api/endpoints";
import type { ProviderCredential, ProviderType } from "@/lib/api/types";

type ConfigureTarget = {
  providerType: ProviderType;
  definition: ProviderDefinition;
  credential?: ProviderCredential;
};

/** Provider credentials by type: set up, test, activate and remove. Secrets are never shown. */
export function ProviderSettingsPanel() {
  const queryClient = useQueryClient();
  const { hasRole } = useWorkspace();
  const canEdit = hasRole("admin");
  const [tab, setTab] = useState<ProviderType>("email");
  const [configureTarget, setConfigureTarget] = useState<ConfigureTarget | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ProviderCredential | null>(null);
  const [busy, setBusy] = useState<{ id: number; action: "test" | "activate" } | null>(null);

  const credentials = useQuery({ queryKey: ["provider-settings"], queryFn: providerSettingsApi.list });

  const byKey = useMemo(() => {
    const map = new Map<string, ProviderCredential>();
    for (const item of credentials.data?.items ?? []) {
      map.set(`${item.provider_type}:${item.provider_name}`, item);
    }
    return map;
  }, [credentials.data]);

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["provider-settings"] });
    void queryClient.invalidateQueries({ queryKey: ["onboarding"] });
  };

  const test = useMutation({
    mutationFn: (id: number) => providerSettingsApi.test(id),
    onMutate: (id) => setBusy({ id, action: "test" }),
    onSettled: () => setBusy(null),
    onSuccess: (result) => {
      invalidate();
      if (result.success) toast.success(result.message || "Connection works");
      else toast.error(result.message || "The test failed. Check the details and try again.");
    },
  });

  const activate = useMutation({
    mutationFn: (id: number) => providerSettingsApi.activate(id),
    onMutate: (id) => setBusy({ id, action: "activate" }),
    onSettled: () => setBusy(null),
    onSuccess: (credential) => {
      invalidate();
      toast.success(`${credential.display_name} is now active`);
    },
  });

  const remove = useMutation({
    mutationFn: (id: number) => providerSettingsApi.delete(id),
    onSuccess: () => {
      invalidate();
      toast.success(`${deleteTarget?.display_name ?? "Credentials"} deleted`);
      setDeleteTarget(null);
    },
  });

  const activeLabel = (type: ProviderType) =>
    credentials.data?.items.find((item) => item.provider_type === type && item.is_active)
      ?.display_name;

  return (
    <div className="space-y-4">
      {!canEdit ? <AdminOnlyNotice what="add, test or change provider accounts" /> : null}

      {credentials.error ? (
        <ErrorState error={credentials.error} onRetry={() => void credentials.refetch()} />
      ) : (
        <Tabs value={tab} onValueChange={(value) => setTab(value as ProviderType)} className="gap-4">
          <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
            <TabsList aria-label="Provider types" className="w-max">
              {PROVIDER_TYPES.map((group) => {
                const Icon = group.icon;
                return (
                  <TabsTrigger key={group.type} value={group.type} className="px-3 text-[13px]">
                    <Icon aria-hidden />
                    {group.label}
                  </TabsTrigger>
                );
              })}
            </TabsList>
          </div>

          {PROVIDER_TYPES.map((group) => (
            <TabsContent key={group.type} value={group.type} className="space-y-4">
              <div className="rounded-lg border border-[var(--outline-variant)] bg-white px-4 py-3">
                <p className="text-[13px] text-[var(--on-surface-variant)]">{group.description}</p>
                <p className="mt-1 text-[12px] text-[var(--on-surface)]">
                  {activeLabel(group.type) ? (
                    <>
                      Active: <span className="font-semibold">{activeLabel(group.type)}</span>
                    </>
                  ) : (
                    <span className="text-[var(--on-surface-variant)]">Nothing active yet.</span>
                  )}
                </p>
              </div>

              {credentials.isLoading ? (
                <div className="grid gap-4 md:grid-cols-2" role="status" aria-label="Loading providers">
                  {[0, 1].map((key) => (
                    <div key={key} className="h-40 animate-pulse rounded-lg bg-[var(--surface-container-high)]" />
                  ))}
                </div>
              ) : (
                <div className="grid gap-4 md:grid-cols-2">
                  {group.providers.map((definition) => {
                    const credential = byKey.get(`${group.type}:${definition.name}`);
                    return (
                      <ProviderCard
                        key={definition.name}
                        providerType={group.type}
                        definition={definition}
                        credential={credential}
                        canEdit={canEdit}
                        actions={{
                          busy: credential && busy?.id === credential.id ? busy.action : null,
                          onConfigure: () =>
                            setConfigureTarget({ providerType: group.type, definition, credential }),
                          onTest: () => credential && test.mutate(credential.id),
                          onActivate: () => credential && activate.mutate(credential.id),
                          onDelete: () => credential && setDeleteTarget(credential),
                        }}
                      />
                    );
                  })}
                </div>
              )}
            </TabsContent>
          ))}
        </Tabs>
      )}

      <ProviderConfigDialog
        target={configureTarget}
        onOpenChange={(open) => !open && setConfigureTarget(null)}
      />

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title={`Delete ${deleteTarget?.display_name ?? "these"} credentials?`}
        description={
          deleteTarget?.is_active
            ? "This account is active. Anything that depends on it stops working until you activate another one."
            : "The saved keys are removed permanently. You can set it up again later."
        }
        confirmLabel="Delete"
        destructive
        loading={remove.isPending}
        onConfirm={() => deleteTarget && remove.mutate(deleteTarget.id)}
      />
    </div>
  );
}
