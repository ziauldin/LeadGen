"use client";

import { useQuery } from "@tanstack/react-query";
import { Clock, CornerDownRight, FileText, Pencil, PenLine, Sparkles } from "lucide-react";
import { ButtonLink } from "@/components/ui/button-link";
import { HighlightedTemplate } from "@/components/campaigns/form-controls";
import { formatSendingDays } from "@/components/campaigns/format";
import { providerSettingsApi, templatesApi } from "@/lib/api/endpoints";
import type { Campaign } from "@/lib/api/types";

function Chip({ icon: Icon, children }: { icon: typeof Clock; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-[var(--outline-variant)] bg-white px-2 py-0.5 text-[12px] text-[var(--on-surface-variant)]">
      <Icon className="size-3" aria-hidden />
      {children}
    </span>
  );
}

/** Read-only view of a campaign's steps and schedule. */
export function CampaignSequenceView({ campaign }: { campaign: Campaign }) {
  const templates = useQuery({
    queryKey: ["templates", { includeArchived: true }],
    queryFn: () => templatesApi.list(true),
  });
  const credentials = useQuery({
    queryKey: ["provider-settings"],
    queryFn: providerSettingsApi.list,
    enabled: campaign.sender_credential_id !== null,
  });
  const templateName = (id: string) => templates.data?.find((template) => template.id === id)?.name ?? id;
  const sender = credentials.data?.items.find((item) => item.id === campaign.sender_credential_id);
  const steps = [...campaign.steps].sort((a, b) => a.step_number - b.step_number);

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
      <section aria-labelledby="sequence-steps-title" className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <h3 id="sequence-steps-title" className="text-[16px] font-semibold text-[var(--on-surface)]">
            {steps.length} {steps.length === 1 ? "step" : "steps"}
          </h3>
          <ButtonLink variant="outline" size="sm" href={`/campaigns/${campaign.id}/edit`}>
            <Pencil aria-hidden />
            Edit sequence
          </ButtonLink>
        </div>
        {steps.length === 0 ? (
          <p className="rounded-lg border border-dashed p-6 text-center text-[13px] text-[var(--on-surface-variant)]">
            This campaign has no steps. Edit it to add the first email.
          </p>
        ) : (
          <ol className="relative space-y-3">
            {steps.map((step, index) => (
              <li key={step.id} className="rounded-lg border border-[var(--outline-variant)] bg-white p-4 shadow-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className="flex size-6 items-center justify-center rounded-full bg-[var(--primary)] text-[12px] font-bold text-white"
                    aria-hidden
                  >
                    {step.step_number}
                  </span>
                  <h4 className="mr-1 text-[14px] font-semibold text-[var(--on-surface)]">Step {step.step_number}</h4>
                  <Chip icon={Clock}>
                    {index === 0
                      ? "Sends once approved"
                      : `${step.delay_days} day${step.delay_days === 1 ? "" : "s"} after step ${step.step_number - 1}`}
                  </Chip>
                  {step.template_id ? (
                    <Chip icon={FileText}>Template: {templateName(step.template_id)}</Chip>
                  ) : (
                    <Chip icon={PenLine}>Custom email</Chip>
                  )}
                  {step.use_ai ? <Chip icon={Sparkles}>AI draft</Chip> : null}
                  {index > 0 && step.thread_with_previous ? <Chip icon={CornerDownRight}>Same thread</Chip> : null}
                </div>
                <div className="mt-3 rounded-md bg-[var(--surface-container-low)] p-3">
                  <p className="text-[13px] font-medium text-[var(--on-surface)]">
                    <HighlightedTemplate text={step.subject_template} />
                  </p>
                  <details className="group mt-1">
                    <summary className="cursor-pointer rounded text-[12px] font-medium text-[var(--primary)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)]">
                      Show body
                    </summary>
                    <div className="mt-2 max-h-72 overflow-y-auto whitespace-pre-wrap break-words text-[13px] leading-[20px] text-[var(--on-surface)]">
                      <HighlightedTemplate text={step.body_template} />
                    </div>
                  </details>
                </div>
                {step.use_ai ? (
                  <p className="mt-2 text-[12px] text-[var(--on-surface-variant)]">
                    {step.ai_instructions ? (
                      <>
                        <span className="font-medium">AI instructions:</span> {step.ai_instructions}
                      </>
                    ) : (
                      "AI personalises this email; the text above is the fallback."
                    )}
                  </p>
                ) : null}
              </li>
            ))}
          </ol>
        )}
      </section>

      <aside
        aria-labelledby="sequence-schedule-title"
        className="h-fit rounded-lg border border-[var(--outline-variant)] bg-white p-4 shadow-sm"
      >
        <h3 id="sequence-schedule-title" className="mb-3 text-[14px] font-semibold text-[var(--on-surface)]">
          Schedule & limits
        </h3>
        <dl className="space-y-2.5 text-[13px]">
          {[
            ["Timezone", campaign.timezone ?? "Workspace default"],
            ["Sending days", formatSendingDays(campaign.sending_days)],
            [
              "Window",
              campaign.sending_window_start && campaign.sending_window_end
                ? `${campaign.sending_window_start} – ${campaign.sending_window_end}`
                : "Workspace default",
            ],
            ["Daily limit", `${campaign.daily_send_limit} emails`],
            ["Per domain", campaign.per_domain_limit ? `${campaign.per_domain_limit} a day` : "No limit"],
            [
              "Sending account",
              campaign.sender_credential_id
                ? (sender?.display_name ?? `Account #${campaign.sender_credential_id}`)
                : "Workspace default",
            ],
            ["On reply", campaign.stop_on_reply ? "Stop follow-ups" : "Keep sending"],
          ].map(([label, value]) => (
            <div key={label} className="flex justify-between gap-3">
              <dt className="text-[var(--on-surface-variant)]">{label}</dt>
              <dd className="text-right font-medium text-[var(--on-surface)]">{value}</dd>
            </div>
          ))}
        </dl>
      </aside>
    </div>
  );
}
