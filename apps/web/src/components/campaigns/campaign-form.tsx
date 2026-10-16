"use client";

import { useId } from "react";
import Link from "next/link";
import { Controller, FormProvider, useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { CircleAlert, ShieldCheck } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ButtonLink } from "@/components/ui/button-link";
import { Input } from "@/components/ui/input";
import { CampaignStepEditor } from "@/components/campaigns/campaign-step-editor";
import {
  DEFAULT_VARIABLES,
  campaignFormSchema,
  type CampaignFormValues,
} from "@/components/campaigns/campaign-form-schema";
import {
  FieldError,
  FieldHint,
  FieldLabel,
  FormSection,
  NativeSelect,
  Switch,
} from "@/components/campaigns/form-controls";
import { TimezoneCombobox } from "@/components/campaigns/timezone-combobox";
import { WEEKDAYS } from "@/components/campaigns/format";
import { nichesApi, providerSettingsApi, templatesApi } from "@/lib/api/endpoints";
import { cn } from "@/lib/utils";

type Props = {
  defaultValues: CampaignFormValues;
  /** Edit mode: the niche can't change and the step editor explains removal limits. */
  editing?: boolean;
  submitLabel: string;
  submitting?: boolean;
  serverError?: string | null;
  cancelHref: string;
  onSubmit: (values: CampaignFormValues) => void;
};

export function CampaignForm({
  defaultValues,
  editing = false,
  submitLabel,
  submitting = false,
  serverError,
  cancelHref,
  onSubmit,
}: Props) {
  const uid = useId();
  const form = useForm<CampaignFormValues>({
    resolver: zodResolver(campaignFormSchema),
    defaultValues,
    mode: "onSubmit",
    reValidateMode: "onChange",
  });
  const {
    register,
    control,
    handleSubmit,
    formState: { errors },
  } = form;

  const niches = useQuery({
    queryKey: ["niches", { limit: 200 }],
    queryFn: () => nichesApi.list({ limit: 200 }),
  });
  const templates = useQuery({
    queryKey: ["templates", { includeArchived: true }],
    queryFn: () => templatesApi.list(true),
  });
  const variables = useQuery({
    queryKey: ["templates", "variables"],
    queryFn: templatesApi.variables,
    staleTime: 60 * 60_000,
  });
  const credentials = useQuery({
    queryKey: ["provider-settings"],
    queryFn: providerSettingsApi.list,
  });

  const nicheId = useWatch({ control, name: "niche_id" });
  const windowStart = useWatch({ control, name: "sending_window_start" });
  const windowEnd = useWatch({ control, name: "sending_window_end" });
  const senderId = useWatch({ control, name: "sender_credential_id" });

  const nicheItems = niches.data?.items ?? [];
  const currentNiche = nicheItems.find((niche) => String(niche.id) === nicheId);
  const emailAccounts = (credentials.data?.items ?? []).filter(
    (credential) =>
      credential.provider_type === "email" &&
      (credential.is_active || String(credential.id) === senderId),
  );
  const overnight = Boolean(windowStart && windowEnd && windowEnd < windowStart);

  const ids = {
    name: `${uid}-name`,
    niche: `${uid}-niche`,
    timezone: `${uid}-timezone`,
    timezoneHint: `${uid}-timezone-hint`,
    start: `${uid}-start`,
    end: `${uid}-end`,
    daily: `${uid}-daily`,
    perDomain: `${uid}-per-domain`,
    sender: `${uid}-sender`,
  };

  const firstError = Object.keys(errors).length > 0;

  return (
    <FormProvider {...form}>
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-6">
        {serverError ? (
          <Alert variant="destructive">
            <CircleAlert aria-hidden />
            <AlertTitle>We couldn&apos;t save this campaign</AlertTitle>
            <AlertDescription>{serverError}</AlertDescription>
          </Alert>
        ) : null}

        <FormSection id={`${uid}-basics`} title="Basics" description="Name the campaign and pick who it targets.">
          <div className="grid gap-5 md:grid-cols-2">
            <div>
              <FieldLabel htmlFor={ids.name}>Campaign name</FieldLabel>
              <Input
                id={ids.name}
                placeholder="e.g. Q3 – UK SaaS founders"
                className="h-9 bg-white text-[13px]"
                aria-invalid={Boolean(errors.name)}
                {...register("name")}
              />
              <FieldError message={errors.name?.message} />
            </div>
            <div>
              <FieldLabel htmlFor={ids.niche}>Niche</FieldLabel>
              {editing ? (
                <>
                  <Input
                    id={ids.niche}
                    readOnly
                    disabled
                    value={currentNiche?.name ?? (niches.isLoading ? "Loading…" : `Niche #${nicheId}`)}
                    className="h-9 text-[13px]"
                  />
                  <FieldHint>A campaign stays with the niche it was created for.</FieldHint>
                </>
              ) : (
                <>
                  <NativeSelect
                    id={ids.niche}
                    disabled={niches.isLoading}
                    aria-invalid={Boolean(errors.niche_id)}
                    {...register("niche_id")}
                  >
                    <option value="">{niches.isLoading ? "Loading niches…" : "Choose a niche"}</option>
                    {nicheItems.map((niche) => (
                      <option key={niche.id} value={String(niche.id)}>
                        {niche.name}
                      </option>
                    ))}
                  </NativeSelect>
                  <FieldError message={errors.niche_id?.message} />
                  {niches.isError ? (
                    <FieldError message="We couldn't load your niches. Refresh the page to try again." />
                  ) : null}
                  {!niches.isLoading && !niches.isError && nicheItems.length === 0 ? (
                    <FieldHint>
                      You don&apos;t have any niches yet.{" "}
                      <Link href="/niches/new" className="font-medium text-[var(--primary)] underline">
                        Create a niche
                      </Link>{" "}
                      first, then come back.
                    </FieldHint>
                  ) : (
                    <FieldHint>Only leads from this niche can be added to the campaign.</FieldHint>
                  )}
                </>
              )}
            </div>
          </div>
        </FormSection>

        <FormSection
          id={`${uid}-sequence`}
          title="Sequence"
          description={
            <span className="inline-flex items-start gap-1.5">
              <ShieldCheck className="mt-0.5 size-4 shrink-0 text-[var(--secondary)]" aria-hidden />
              Every email is created as a draft and only sends after someone approves it in
              Approvals. Follow-ups are drafted when they come due.
            </span>
          }
        >
          <CampaignStepEditor
            templates={templates.data ?? []}
            templatesLoading={templates.isLoading}
            variables={variables.data?.variables ?? DEFAULT_VARIABLES}
            editing={editing}
          />
          {templates.isError ? (
            <FieldError message="We couldn't load your templates. You can still write custom steps." />
          ) : null}
        </FormSection>

        <FormSection
          id={`${uid}-schedule`}
          title="Schedule & limits"
          description="Approved emails go out only on these days and inside this window."
        >
          <div className="grid gap-5 md:grid-cols-2">
            <div className="md:col-span-2 md:max-w-md">
              <FieldLabel htmlFor={ids.timezone}>Timezone</FieldLabel>
              <Controller
                control={control}
                name="timezone"
                render={({ field, fieldState }) => (
                  <TimezoneCombobox
                    id={ids.timezone}
                    value={field.value}
                    onChange={field.onChange}
                    invalid={Boolean(fieldState.error)}
                    describedBy={ids.timezoneHint}
                  />
                )}
              />
              <FieldError message={errors.timezone?.message} />
              <FieldHint id={ids.timezoneHint}>The sending window and days use this timezone.</FieldHint>
            </div>

            <fieldset className="md:col-span-2">
              <legend className="mb-1.5 text-[13px] font-semibold text-[var(--on-surface)]">
                Sending days
              </legend>
              <Controller
                control={control}
                name="sending_days"
                render={({ field }) => (
                  <div className="flex flex-wrap gap-1.5">
                    {WEEKDAYS.map((day) => {
                      const on = field.value.includes(day.value);
                      return (
                        <button
                          key={day.value}
                          type="button"
                          aria-pressed={on}
                          title={day.long}
                          onClick={() =>
                            field.onChange(
                              on
                                ? field.value.filter((value) => value !== day.value)
                                : [...field.value, day.value].sort(),
                            )
                          }
                          className={cn(
                            "h-9 min-w-12 rounded-lg border px-3 text-[13px] font-medium transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
                            on
                              ? "border-[var(--primary)] bg-[var(--primary)] text-white"
                              : "border-[var(--outline-variant)] bg-white text-[var(--on-surface-variant)] hover:border-[var(--primary)] hover:text-[var(--primary)]",
                          )}
                        >
                          {day.short}
                        </button>
                      );
                    })}
                  </div>
                )}
              />
              <FieldError message={errors.sending_days?.message} />
            </fieldset>

            <div className="grid grid-cols-2 gap-3 md:col-span-2 md:max-w-md">
              <div>
                <FieldLabel htmlFor={ids.start}>Window starts</FieldLabel>
                <Input
                  id={ids.start}
                  type="time"
                  className="h-9 bg-white text-[13px]"
                  aria-invalid={Boolean(errors.sending_window_start)}
                  {...register("sending_window_start")}
                />
                <FieldError message={errors.sending_window_start?.message} />
              </div>
              <div>
                <FieldLabel htmlFor={ids.end}>Window ends</FieldLabel>
                <Input
                  id={ids.end}
                  type="time"
                  className="h-9 bg-white text-[13px]"
                  aria-invalid={Boolean(errors.sending_window_end)}
                  {...register("sending_window_end")}
                />
                <FieldError message={errors.sending_window_end?.message} />
              </div>
              {overnight ? (
                <p className="col-span-2 text-[12px] text-[var(--on-surface-variant)]">
                  This window runs overnight, from {windowStart} until {windowEnd} the next day.
                </p>
              ) : null}
            </div>

            <div>
              <FieldLabel htmlFor={ids.daily}>Daily send limit</FieldLabel>
              <Input
                id={ids.daily}
                type="number"
                inputMode="numeric"
                min={1}
                max={10000}
                className="h-9 bg-white text-[13px]"
                aria-invalid={Boolean(errors.daily_send_limit)}
                {...register("daily_send_limit", { valueAsNumber: true })}
              />
              <FieldError message={errors.daily_send_limit?.message} />
              <FieldHint>Start low (20–50 a day) to protect your sending reputation.</FieldHint>
            </div>
            <div>
              <FieldLabel htmlFor={ids.perDomain} optional>
                Per-domain daily limit
              </FieldLabel>
              <Input
                id={ids.perDomain}
                type="number"
                inputMode="numeric"
                min={1}
                max={1000}
                placeholder="No limit"
                className="h-9 bg-white text-[13px]"
                aria-invalid={Boolean(errors.per_domain_limit)}
                {...register("per_domain_limit", {
                  setValueAs: (value: unknown) =>
                    value === "" || value === null || value === undefined ? null : Number(value),
                })}
              />
              <FieldError message={errors.per_domain_limit?.message} />
              <FieldHint>Caps emails per day to any one company domain.</FieldHint>
            </div>

            <div>
              <FieldLabel htmlFor={ids.sender} optional>
                Sending account
              </FieldLabel>
              <NativeSelect id={ids.sender} disabled={credentials.isLoading} {...register("sender_credential_id")}>
                <option value="">Workspace default</option>
                {emailAccounts.map((credential) => (
                  <option key={credential.id} value={String(credential.id)}>
                    {credential.display_name}
                    {credential.masked_summary ? ` – ${credential.masked_summary}` : ""}
                    {credential.is_active ? "" : " (inactive)"}
                  </option>
                ))}
              </NativeSelect>
              <FieldHint>
                {credentials.isError
                  ? "We couldn't load your email accounts; the workspace default will be used."
                  : emailAccounts.length === 0 && !credentials.isLoading
                    ? "No active email account yet. Connect one in Settings before sending."
                    : "Leave as default to use the workspace's active email account."}
              </FieldHint>
            </div>

            <div className="flex items-start md:pt-6">
              <Switch
                label="Stop when they reply"
                description="Cancel remaining follow-ups for a lead as soon as they reply."
                {...register("stop_on_reply")}
              />
            </div>
          </div>
        </FormSection>

        <div className="sticky bottom-0 z-[5] -mx-4 flex flex-col-reverse gap-2 border-t border-[var(--outline-variant)] bg-white/95 px-4 py-3 backdrop-blur sm:mx-0 sm:flex-row sm:items-center sm:justify-end sm:rounded-lg sm:border">
          {firstError ? (
            <p role="status" className="text-[12px] font-medium text-[var(--error)] sm:mr-auto">
              Fix the highlighted fields to continue.
            </p>
          ) : null}
          <ButtonLink
            variant="outline"
            href={cancelHref}
            aria-disabled={submitting}
            className={submitting ? "pointer-events-none opacity-50" : undefined}
          >
            Cancel
          </ButtonLink>
          <Button type="submit" disabled={submitting}>
            {submitting ? "Saving…" : submitLabel}
          </Button>
        </div>
      </form>
    </FormProvider>
  );
}
