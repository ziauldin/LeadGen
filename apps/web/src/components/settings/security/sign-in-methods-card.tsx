"use client";

import { useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ErrorState, LoadingState } from "@/components/shared/loading-error";
import { SettingsCard } from "@/components/settings/settings-card";
import { ssoApi } from "@/lib/api/endpoints";

const LABELS: Record<string, string> = { google: "Google", microsoft: "Microsoft" };

function label(provider: string) {
  if (provider.startsWith("sso:")) return "Company single sign-on";
  return LABELS[provider] ?? provider;
}

/** Google / Microsoft / company SSO identities linked to the signed-in account. */
export function SignInMethodsCard() {
  const queryClient = useQueryClient();
  const params = useSearchParams();
  const providers = useQuery({ queryKey: ["auth-providers"], queryFn: ssoApi.providers });
  const identities = useQuery({ queryKey: ["identities"], queryFn: ssoApi.identities });

  useEffect(() => {
    const linked = params.get("linked");
    if (linked) toast.success(`${label(linked)} is now connected`);
  }, [params]);

  const connect = useMutation({
    mutationFn: ssoApi.linkProvider,
    onSuccess: ({ url }) => {
      const target = new URL(url);
      window.location.assign(target.pathname + target.search);
    },
  });
  const unlink = useMutation({
    mutationFn: ssoApi.unlinkIdentity,
    onSuccess: () => {
      toast.success("Disconnected");
      void queryClient.invalidateQueries({ queryKey: ["identities"] });
    },
  });

  const linkedProviders = new Set((identities.data ?? []).map((identity) => identity.provider));
  const available = (["google", "microsoft"] as const).filter(
    (provider) => providers.data?.[provider] && !linkedProviders.has(provider),
  );
  if (providers.data && !providers.data.google && !providers.data.microsoft && !identities.data?.length) {
    return null;
  }

  return (
    <SettingsCard
      title="Sign-in methods"
      description="Connect Google or Microsoft to sign in without your password. You can always reset your password by email."
    >
      {identities.isLoading ? (
        <LoadingState />
      ) : identities.error ? (
        <ErrorState error={identities.error} onRetry={() => identities.refetch()} />
      ) : (
        <div className="space-y-4">
          {(identities.data ?? []).length > 0 && (
            <ul className="divide-y divide-[var(--outline-variant)]">
              {(identities.data ?? []).map((identity) => (
                <li key={identity.id} className="flex items-center gap-3 py-2.5">
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] font-medium">{label(identity.provider)}</p>
                    <p className="truncate text-[12px] text-[var(--on-surface-variant)]">{identity.email}</p>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => unlink.mutate(identity.id)} disabled={unlink.isPending}>
                    Disconnect
                  </Button>
                </li>
              ))}
            </ul>
          )}
          {available.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {available.map((provider) => (
                <Button key={provider} variant="outline" onClick={() => connect.mutate(provider)} disabled={connect.isPending}>
                  Connect {LABELS[provider]}
                </Button>
              ))}
            </div>
          )}
        </div>
      )}
    </SettingsCard>
  );
}
