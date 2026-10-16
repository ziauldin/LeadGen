"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { SettingsCard } from "@/components/settings/settings-card";
import { useWorkspace } from "@/hooks/use-workspace";
import { settingsApi } from "@/lib/api/endpoints";

/** Workspace policy for addresses that verification can't fully confirm. */
export function VerificationSettingsCard() {
  const queryClient = useQueryClient();
  const { can } = useWorkspace();
  const settings = useQuery({ queryKey: ["settings"], queryFn: settingsApi.get });
  const save = useMutation({
    mutationFn: (block: boolean) => settingsApi.update({ block_risky_emails: block }),
    onSuccess: (data) => {
      queryClient.setQueryData(["settings"], data);
      toast.success("Saved");
    },
  });
  return (
    <SettingsCard
      id="verification-policy"
      title="Address verification"
      description="Invalid addresses are never emailed. Connect ZeroBounce or NeverBounce under Providers to check new contacts automatically, or select leads and choose Verify emails."
    >
      <label className="flex items-start gap-3 text-[13px]">
        <input
          type="checkbox"
          className="mt-0.5 size-4 accent-[var(--primary)]"
          checked={Boolean(settings.data?.block_risky_emails)}
          disabled={!can("settings.manage") || save.isPending || !settings.data}
          onChange={(event) => save.mutate(event.target.checked)}
        />
        <span>
          <span className="block font-medium">Don&apos;t send to risky addresses</span>
          <span className="text-[var(--on-surface-variant)]">
            Catch-all domains and disposable addresses often bounce or never reach a person. Blocking them protects
            your sender reputation.
          </span>
        </span>
      </label>
    </SettingsCard>
  );
}
