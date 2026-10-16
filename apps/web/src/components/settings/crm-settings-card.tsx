"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SettingsCard } from "@/components/settings/settings-card";
import { useFlags } from "@/hooks/use-flags";
import { useWorkspace } from "@/hooks/use-workspace";
import { settingsApi } from "@/lib/api/endpoints";

export function CrmSettingsCard() {
  const queryClient = useQueryClient();
  const { can } = useWorkspace();
  const flags = useFlags();
  const canEdit = can("settings.manage");
  const settings = useQuery({ queryKey: ["settings"], queryFn: settingsApi.get });
  const [link, setLink] = useState("");
  useEffect(() => setLink(settings.data?.meeting_link ?? ""), [settings.data?.meeting_link]);
  const save = useMutation({
    mutationFn: (data: { meeting_link?: string | null; auto_create_deals?: boolean }) => settingsApi.update(data),
    onSuccess: (data) => {
      queryClient.setQueryData(["settings"], data);
      toast.success("Saved");
    },
  });

  return (
    <SettingsCard
      id="meetings-and-deals"
      title="Meetings and deals"
      description="Your booking link fills the {{meeting_link}} template variable, so prospects can pick a time straight from your email."
    >
      <form
        className="flex flex-col gap-2 sm:flex-row sm:items-end"
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate({ meeting_link: link.trim() || null });
        }}
      >
        <div className="grid flex-1 gap-1.5">
          <label htmlFor="meeting-link" className="text-[13px] font-medium">Booking link</label>
          <Input
            id="meeting-link"
            type="url"
            pattern="https://.*"
            placeholder="https://cal.com/you/intro"
            value={link}
            disabled={!canEdit}
            onChange={(event) => setLink(event.target.value)}
            className="bg-white"
          />
        </div>
        <Button type="submit" disabled={!canEdit || save.isPending}>Save</Button>
      </form>
      {flags.crm ? (
        <label className="mt-4 flex items-start gap-3 text-[13px]">
          <input
            type="checkbox"
            className="mt-0.5 size-4 accent-[var(--primary)]"
            checked={settings.data?.auto_create_deals ?? true}
            disabled={!canEdit || save.isPending || !settings.data}
            onChange={(event) => save.mutate({ auto_create_deals: event.target.checked })}
          />
          <span>
            <span className="block font-medium">Open a deal when someone replies with interest</span>
            <span className="text-[var(--on-surface-variant)]">New deals start in the first stage of your board.</span>
          </span>
        </label>
      ) : null}
    </SettingsCard>
  );
}
