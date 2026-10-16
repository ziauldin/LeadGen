"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { LoadingState } from "@/components/shared/loading-error";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AdminOnlyNotice, SettingsCard } from "@/components/settings/settings-card";
import { useWorkspace } from "@/hooks/use-workspace";
import { notificationsApi } from "@/lib/api/endpoints";

function PreferencesCard() {
  const queryClient = useQueryClient();
  const prefs = useQuery({ queryKey: ["notification-preferences"], queryFn: notificationsApi.preferences });
  const save = useMutation({
    mutationFn: (settings: Record<string, Record<string, boolean>>) => notificationsApi.savePreferences(settings),
    onSuccess: (data) => {
      queryClient.setQueryData(["notification-preferences"], data);
      toast.success("Notification settings saved");
    },
  });

  return (
    <SettingsCard id="notification-preferences" title="Your notifications" description="Choose what you hear about, and where. These settings are just for you.">
      {prefs.isLoading ? (
        <LoadingState />
      ) : (
        <div className="overflow-x-auto" tabIndex={0}>
          <table className="w-full min-w-[420px] text-[13px]">
            <caption className="sr-only">Notification preferences</caption>
            <thead>
              <tr className="text-left text-[12px] text-[var(--on-surface-variant)]">
                <th scope="col" className="py-2 font-medium">Tell me when…</th>
                <th scope="col" className="w-24 py-2 text-center font-medium">In the app</th>
                <th scope="col" className="w-24 py-2 text-center font-medium">By email</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--outline-variant)]">
              {prefs.data?.map((pref) => (
                <tr key={pref.key}>
                  <th scope="row" className="py-2.5 text-left font-normal">{pref.label}</th>
                  {(["in_app", "email"] as const).map((channel) => (
                    <td key={channel} className="py-2.5 text-center">
                      {pref.key === "weekly_digest" && channel === "in_app" ? (
                        <span className="text-[var(--on-surface-variant)]" aria-label="Not available">—</span>
                      ) : (
                        <input
                          type="checkbox"
                          className="size-4 cursor-pointer accent-[var(--primary)]"
                          aria-label={`${pref.label}: ${channel === "email" ? "email" : "in the app"}`}
                          checked={pref[channel]}
                          disabled={save.isPending}
                          onChange={(event) => save.mutate({ [pref.key]: { [channel]: event.target.checked } })}
                        />
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SettingsCard>
  );
}

function SlackCard() {
  const queryClient = useQueryClient();
  const { can } = useWorkspace();
  const canEdit = can("settings.manage");
  const slack = useQuery({ queryKey: ["slack"], queryFn: notificationsApi.slack });
  const [url, setUrl] = useState("");
  const update = useMutation({
    mutationFn: notificationsApi.updateSlack,
    onSuccess: (data) => {
      queryClient.setQueryData(["slack"], data);
      setUrl("");
      toast.success(data.connected ? "Slack settings saved" : "Slack disconnected");
    },
  });
  const test = useMutation({
    mutationFn: notificationsApi.testSlack,
    onSuccess: () => toast.success("Test message sent. Check your Slack channel."),
  });
  const data = slack.data;

  return (
    <SettingsCard
      id="slack"
      title="Slack"
      description="Post interested replies and important alerts to a Slack channel for the whole team."
    >
      {!canEdit ? <AdminOnlyNotice what="connect Slack" /> : null}
      {!data ? (
        <LoadingState />
      ) : (
        <div className="space-y-4">
          {data.connected ? (
            <p className="text-[13px]">
              <span className="font-semibold text-[var(--primary)]">Connected.</span> Messages go to the channel you chose when
              creating the webhook.
            </p>
          ) : (
            <p className="text-[13px] text-[var(--on-surface-variant)]">
              In Slack, add the <strong>Incoming Webhooks</strong> app to a channel and paste its webhook URL here.
            </p>
          )}
          {canEdit ? (
            <form
              className="flex flex-col gap-2 sm:flex-row sm:items-end"
              onSubmit={(event) => {
                event.preventDefault();
                if (url.trim()) update.mutate({ webhook_url: url.trim() });
              }}
            >
              <div className="grid flex-1 gap-1.5">
                <label htmlFor="slack-webhook" className="text-[13px] font-medium">
                  {data.connected ? "Replace webhook URL" : "Webhook URL"}
                </label>
                <Input
                  id="slack-webhook"
                  type="url"
                  className="bg-white"
                  placeholder="https://hooks.slack.com/services/…"
                  value={url}
                  onChange={(event) => setUrl(event.target.value)}
                />
              </div>
              <Button type="submit" disabled={!url.trim() || update.isPending}>
                {data.connected ? "Replace" : "Connect"}
              </Button>
            </form>
          ) : null}
          {data.connected ? (
            <>
              <fieldset className="grid gap-1.5">
                <legend className="mb-1 text-[13px] font-medium">Post to Slack when…</legend>
                {data.available_events.map((event) => (
                  <label key={event.key} className="flex items-center gap-2 text-[13px]">
                    <input
                      type="checkbox"
                      className="size-4 accent-[var(--primary)]"
                      disabled={!canEdit || update.isPending}
                      checked={data.events.includes(event.key)}
                      onChange={(e) =>
                        update.mutate({
                          events: e.target.checked
                            ? [...data.events, event.key]
                            : data.events.filter((key) => key !== event.key),
                        })
                      }
                    />
                    {event.label}
                  </label>
                ))}
              </fieldset>
              {canEdit ? (
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" disabled={test.isPending} onClick={() => test.mutate()}>
                    Send a test message
                  </Button>
                  <Button variant="ghost" size="sm" disabled={update.isPending} onClick={() => update.mutate({ disconnect: true })}>
                    Disconnect
                  </Button>
                </div>
              ) : null}
            </>
          ) : null}
        </div>
      )}
    </SettingsCard>
  );
}

export function NotificationSettings() {
  return (
    <div className="space-y-6">
      <PreferencesCard />
      <SlackCard />
    </div>
  );
}
