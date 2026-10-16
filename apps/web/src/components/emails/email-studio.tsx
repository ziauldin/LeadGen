"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlertTriangle, FileText, Send, ShieldCheck, Sparkles, UserRound, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ScoreBadge } from "@/components/shared/score-badge";
import { EmailPreview } from "@/components/emails/email-preview";
import { LeadCombobox, useDebouncedValue } from "@/components/emails/lead-combobox";
import { TemplateSelect } from "@/components/templates/template-select";
import { getErrorMessage } from "@/lib/api/client";
import { campaignsApi, emailsApi, leadsApi } from "@/lib/api/endpoints";
import type { GenerationMode, Lead } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const NO_CAMPAIGN = "none";

function Field({
  label,
  htmlFor,
  hint,
  children,
}: {
  label: string;
  htmlFor?: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid gap-1.5">
      <label htmlFor={htmlFor} className="text-[13px] font-medium text-[var(--on-surface)]">
        {label}
      </label>
      {children}
      {hint ? <p className="text-xs text-[var(--on-surface-variant)]">{hint}</p> : null}
    </div>
  );
}

function InlineError({ message }: { message: string }) {
  return (
    <p
      role="alert"
      className="flex gap-2 rounded-md border border-[var(--error)]/30 bg-[var(--error-container)]/60 px-3 py-2 text-[13px] text-[var(--on-error-container)]"
    >
      <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
      {message}
    </p>
  );
}

function SelectedLead({ lead, onClear }: { lead: Lead; onClear: () => void }) {
  return (
    <div className="flex items-start gap-3 rounded-lg bg-[var(--surface-container-low)] p-3">
      <div
        aria-hidden
        className="flex size-9 shrink-0 items-center justify-center rounded-full bg-[var(--primary)] text-[11px] font-bold text-white"
      >
        {lead.full_name.slice(0, 2).toUpperCase()}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <Link
            href={`/leads/${lead.id}`}
            className="truncate text-[13px] font-semibold text-[var(--on-surface)] hover:text-[var(--primary)] hover:underline"
          >
            {lead.full_name}
          </Link>
          <ScoreBadge score={Math.round(lead.score)} />
        </div>
        <p className="truncate text-xs text-[var(--on-surface-variant)]">
          {[lead.job_title, lead.company?.name].filter(Boolean).join(" · ") || "No title or company"}
        </p>
        <p className="truncate text-xs text-[var(--on-surface-variant)]">
          {lead.primary_email ?? "No email address"}
        </p>
      </div>
      <Button variant="ghost" size="icon-sm" aria-label="Change lead" onClick={onClear}>
        <X aria-hidden />
      </Button>
    </div>
  );
}

export function EmailStudio() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  const urlLeadId = Number(searchParams.get("lead_id")) || null;
  const [leadId, setLeadId] = useState<number | null>(urlLeadId);
  const [changingLead, setChangingLead] = useState(false);
  const [templateId, setTemplateId] = useState("system:intro");
  const [mode, setMode] = useState<GenerationMode>("template");
  const [instructions, setInstructions] = useState("");
  const [campaignId, setCampaignId] = useState<string>(NO_CAMPAIGN);
  const ai = mode === "ai";

  const lead = useQuery({
    queryKey: ["lead", leadId],
    queryFn: () => leadsApi.get(leadId!),
    enabled: leadId !== null,
  });
  const campaigns = useQuery({
    queryKey: ["campaigns", { limit: 200 }],
    queryFn: () => campaignsApi.list({ limit: 200 }),
    staleTime: 60_000,
  });

  function chooseLead(next: Lead | null) {
    setLeadId(next?.id ?? null);
    setChangingLead(false);
    if (next) queryClient.setQueryData(["lead", next.id], next);
    aiPreview.reset();
    const params = new URLSearchParams(searchParams.toString());
    if (next) params.set("lead_id", String(next.id));
    else params.delete("lead_id");
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }

  // Template previews are cheap: refresh them (debounced) whenever the inputs change.
  const debouncedKey = useDebouncedValue(`${leadId ?? ""}|${templateId}`, 400);
  const templateInputs = useMemo(() => {
    const [lead, template] = debouncedKey.split("|");
    return { leadId: lead ? Number(lead) : null, templateId: template };
  }, [debouncedKey]);
  const templatePreview = useQuery({
    queryKey: ["email-preview", templateInputs.leadId, templateInputs.templateId],
    queryFn: () =>
      emailsApi.preview(templateInputs.leadId!, {
        templateId: templateInputs.templateId,
        mode: "template",
      }),
    enabled: !ai && templateInputs.leadId !== null,
  });

  // AI previews cost tokens, so they only run when asked.
  const aiPreview = useMutation({
    mutationFn: () => emailsApi.preview(leadId!, { templateId, mode: "ai", instructions }),
    meta: { silent: true },
  });

  const generate = useMutation({
    mutationFn: () =>
      emailsApi.generate(leadId!, campaignId === NO_CAMPAIGN ? null : Number(campaignId), {
        templateId,
        mode,
        instructions: ai ? instructions : undefined,
      }),
    meta: { silent: true },
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: ["approvals"] });
      const open = { label: "Open approvals", onClick: () => router.push("/approvals") };
      if (data.message.generation_mode === "template_fallback") {
        toast.warning("Draft created from the template", {
          description: data.message.generation_note ?? "AI couldn't write this one.",
          action: open,
        });
      } else {
        toast.success("Draft created", {
          description: "It's waiting in Approvals. Nothing is sent until someone approves it.",
          action: open,
        });
      }
    },
  });

  const campaignItems = useMemo(
    () => ({
      [NO_CAMPAIGN]: "No campaign (one-off email)",
      ...Object.fromEntries((campaigns.data?.items ?? []).map((c) => [String(c.id), c.name])),
    }),
    [campaigns.data],
  );

  const preview = ai ? aiPreview.data : templatePreview.data;
  const previewStale =
    !ai && (templateInputs.leadId !== leadId || templateInputs.templateId !== templateId);
  const showLeadPicker = leadId === null || changingLead;

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(320px,380px)_1fr]">
      {/* Setup */}
      <form
        aria-label="Draft settings"
        className="grid content-start gap-5 rounded-lg border border-[var(--outline-variant)] bg-white p-4 sm:p-5"
        onSubmit={(event) => {
          event.preventDefault();
          if (leadId !== null) generate.mutate();
        }}
      >
        <Field label="Lead" htmlFor="studio-lead">
          {showLeadPicker ? (
            <LeadCombobox
              id="studio-lead"
              onSelect={chooseLead}
              autoFocus={changingLead}
            />
          ) : lead.data ? (
            <SelectedLead lead={lead.data} onClear={() => setChangingLead(true)} />
          ) : lead.isError ? (
            <div className="grid gap-2">
              <InlineError message={getErrorMessage(lead.error)} />
              <Button type="button" variant="outline" size="sm" onClick={() => chooseLead(null)}>
                Choose another lead
              </Button>
            </div>
          ) : (
            <div className="h-[68px] animate-pulse rounded-lg bg-[var(--surface-container-low)]" />
          )}
        </Field>

        <Field label="Template" htmlFor="studio-template">
          <TemplateSelect id="studio-template" value={templateId} onChange={setTemplateId} />
        </Field>

        <fieldset className="grid gap-1.5">
          <legend className="mb-1.5 text-[13px] font-medium text-[var(--on-surface)]">
            How to write it
          </legend>
          <div className="grid grid-cols-2 gap-1 rounded-lg bg-[var(--surface-container-low)] p-1">
            {(
              [
                { value: "template", label: "Template", Icon: FileText },
                { value: "ai", label: "Write with AI", Icon: Sparkles },
              ] as const
            ).map(({ value, label, Icon }) => (
              <label
                key={value}
                className={cn(
                  "flex cursor-pointer items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-[13px] font-medium transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-[var(--primary)]",
                  mode === value
                    ? "bg-white text-[var(--primary)] shadow-sm"
                    : "text-[var(--on-surface-variant)] hover:text-[var(--on-surface)]",
                )}
              >
                <input
                  type="radio"
                  name="studio-mode"
                  value={value}
                  checked={mode === value}
                  onChange={() => setMode(value)}
                  className="sr-only"
                />
                <Icon className="size-4" aria-hidden />
                {label}
              </label>
            ))}
          </div>
        </fieldset>

        {ai ? (
          <div className="grid gap-3">
            <Field
              label="Instructions (optional)"
              htmlFor="studio-instructions"
              hint="The template sets the structure; AI personalises it for this lead."
            >
              <Textarea
                id="studio-instructions"
                rows={4}
                maxLength={2000}
                value={instructions}
                placeholder="e.g. Mention their new London office and keep it under 90 words"
                onChange={(event) => setInstructions(event.target.value)}
              />
            </Field>
            <p className="flex gap-2 rounded-md bg-[var(--primary-fixed)]/60 px-3 py-2 text-xs text-[var(--on-primary-fixed)]">
              <ShieldCheck className="size-4 shrink-0" aria-hidden />
              AI only writes a draft. A person still reviews and approves every email before it
              is sent.
            </p>
            <Button
              type="button"
              variant="outline"
              onClick={() => aiPreview.mutate()}
              disabled={leadId === null || aiPreview.isPending}
            >
              <Sparkles aria-hidden />
              {aiPreview.isPending ? "Writing preview…" : aiPreview.data ? "Write a new preview" : "Generate preview"}
            </Button>
          </div>
        ) : null}

        <Field
          label="Campaign"
          htmlFor="studio-campaign"
          hint="Optional. Linking a campaign uses its sending window and limits."
        >
          <Select
            value={campaignId}
            items={campaignItems}
            onValueChange={(value) => setCampaignId(value ? String(value) : NO_CAMPAIGN)}
          >
            <SelectTrigger id="studio-campaign" className="w-full bg-white">
              <SelectValue />
            </SelectTrigger>
            <SelectContent alignItemWithTrigger={false}>
              <SelectItem value={NO_CAMPAIGN}>No campaign (one-off email)</SelectItem>
              {(campaigns.data?.items ?? []).map((campaign) => (
                <SelectItem key={campaign.id} value={String(campaign.id)}>
                  {campaign.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>

        {generate.error ? <InlineError message={getErrorMessage(generate.error)} /> : null}

        <div className="grid gap-2 border-t border-[var(--outline-variant)] pt-4">
          <Button type="submit" size="lg" disabled={leadId === null || generate.isPending}>
            <Send aria-hidden />
            {generate.isPending ? (ai ? "Writing draft…" : "Creating draft…") : "Create draft"}
          </Button>
          {generate.isSuccess ? (
            <p className="text-center text-xs text-[var(--on-surface-variant)]">
              Draft saved.{" "}
              <Link href="/approvals" className="font-medium text-[var(--primary)] hover:underline">
                Review it in Approvals
              </Link>
            </p>
          ) : (
            <p className="text-center text-xs text-[var(--on-surface-variant)]">
              Creates a draft in Approvals. Nothing is sent yet.
            </p>
          )}
        </div>
      </form>

      {/* Preview */}
      <section
        aria-label="Preview"
        className="min-w-0 self-start overflow-hidden rounded-lg border border-[var(--outline-variant)] bg-white"
      >
        <div className="flex items-center justify-between gap-2 border-b border-[var(--outline-variant)] px-4 py-3 sm:px-5">
          <h3 className="text-[14px] font-semibold text-[var(--on-surface)]">Preview</h3>
          {!ai && (templatePreview.isFetching || previewStale) && leadId !== null ? (
            <span role="status" className="text-xs text-[var(--on-surface-variant)]">
              Updating…
            </span>
          ) : null}
        </div>
        {leadId === null ? (
          <EmailPreview
            placeholder={
              <span className="inline-flex flex-col items-center gap-1">
                <UserRound className="size-4" aria-hidden />
                Choose a lead on the left to see the email they would receive.
              </span>
            }
          />
        ) : ai ? (
          aiPreview.error ? (
            <div className="p-5">
              <InlineError message={getErrorMessage(aiPreview.error)} />
            </div>
          ) : (
            <EmailPreview
              preview={preview}
              loading={aiPreview.isPending}
              placeholder="AI previews use credits, so they only run when you click “Generate preview”."
            />
          )
        ) : (
          <EmailPreview
            preview={preview}
            loading={templatePreview.isFetching || previewStale}
            error={templatePreview.error}
            onRetry={() => templatePreview.refetch()}
          />
        )}
      </section>
    </div>
  );
}
