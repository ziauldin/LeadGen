"use client";

import { useEffect } from "react";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Scale, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ErrorState } from "@/components/shared/loading-error";
import { AdminOnlyNotice, Field, SettingsCard } from "@/components/settings/settings-card";
import { useWorkspace } from "@/hooks/use-workspace";
import { settingsApi } from "@/lib/api/endpoints";

const AI_MODES = {
  off: "Off",
  assist: "Assist (AI drafts and reply labelling on request)",
} as const;

const schema = z.object({
  sender_name: z.string().max(255, "Keep it under 255 characters"),
  sender_company: z.string().max(255, "Keep it under 255 characters"),
  business_address: z.string().max(500, "Keep it under 500 characters"),
  product_description: z.string().max(2000, "Keep it under 2,000 characters"),
  tone_guidelines: z.string().max(1000, "Keep it under 1,000 characters"),
  ai_mode: z.enum(["off", "assist"]),
});
type Values = z.infer<typeof schema>;

const EMPTY: Values = {
  sender_name: "",
  sender_company: "",
  business_address: "",
  product_description: "",
  tone_guidelines: "",
  ai_mode: "off",
};

function CharCount({ value, max }: { value: string; max: number }) {
  return (
    <span className="float-right text-[11px] text-[var(--on-surface-variant)]">
      {value.length.toLocaleString()}/{max.toLocaleString()}
    </span>
  );
}

export function SenderProfileForm() {
  const queryClient = useQueryClient();
  const { hasRole } = useWorkspace();
  const canEdit = hasRole("admin");
  const settings = useQuery({ queryKey: ["settings"], queryFn: settingsApi.get });

  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: EMPTY });
  const { reset, register, watch } = form;
  useEffect(() => {
    if (!settings.data) return;
    reset({
      sender_name: settings.data.sender_name ?? "",
      sender_company: settings.data.sender_company ?? "",
      business_address: settings.data.business_address ?? "",
      product_description: settings.data.product_description ?? "",
      tone_guidelines: settings.data.tone_guidelines ?? "",
      ai_mode: settings.data.ai_mode === "assist" ? "assist" : "off",
    });
  }, [settings.data, reset]);

  const save = useMutation({
    mutationFn: (values: Values) =>
      settingsApi.update({
        sender_name: values.sender_name.trim() || null,
        sender_company: values.sender_company.trim() || null,
        business_address: values.business_address.trim() || null,
        product_description: values.product_description.trim() || null,
        tone_guidelines: values.tone_guidelines.trim() || null,
        ai_mode: values.ai_mode,
      }),
    onSuccess: (data) => {
      queryClient.setQueryData(["settings"], data);
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
      void queryClient.invalidateQueries({ queryKey: ["onboarding"] });
      toast.success("Sender profile saved");
    },
  });

  const errors = form.formState.errors;
  const disabled = !canEdit || settings.isLoading;
  const productDescription = watch("product_description");
  const toneGuidelines = watch("tone_guidelines");
  const businessAddress = watch("business_address");

  return (
    <SettingsCard
      id="sender-profile"
      title="Sender profile & AI"
      description="Who your emails come from, and what AI drafts are allowed to say about you."
    >
      {settings.error ? (
        <ErrorState error={settings.error} onRetry={() => void settings.refetch()} />
      ) : (
        <form onSubmit={form.handleSubmit((values) => save.mutate(values))} className="space-y-5">
          {!canEdit ? <AdminOnlyNotice what="edit the sender profile" /> : null}

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Sender name" htmlFor="sender_name" error={errors.sender_name?.message}>
              <Input
                id="sender_name"
                placeholder="Jane Doe"
                className="h-9 bg-white"
                disabled={disabled}
                autoComplete="name"
                {...register("sender_name")}
              />
            </Field>
            <Field label="Company" htmlFor="sender_company" error={errors.sender_company?.message}>
              <Input
                id="sender_company"
                placeholder="Acme Ltd"
                className="h-9 bg-white"
                disabled={disabled}
                autoComplete="organization"
                {...register("sender_company")}
              />
            </Field>
          </div>

          <Field
            label="Business postal address"
            htmlFor="business_address"
            error={errors.business_address?.message}
            hint={
              <span className="flex items-start gap-1.5">
                <Scale className="mt-0.5 size-3.5 shrink-0" aria-hidden />
                <span>
                  Added to the footer of every email, next to your company name and the unsubscribe
                  link. Anti-spam laws such as CAN-SPAM require a valid postal address in
                  commercial email, so please fill this in before you send.
                </span>
              </span>
            }
          >
            <Textarea
              id="business_address"
              rows={2}
              placeholder="12 High Street, London, EC1A 1AA, United Kingdom"
              className="bg-white text-[13px]"
              disabled={disabled}
              aria-describedby="business_address-hint"
              {...register("business_address")}
            />
            <CharCount value={businessAddress} max={500} />
          </Field>

          <div className="border-t border-[var(--outline-variant)] pt-5">
            <h3 className="mb-3 flex items-center gap-2 text-[14px] font-semibold text-[var(--on-surface)]">
              <Sparkles className="size-4 text-[var(--primary)]" aria-hidden />
              AI writing
            </h3>
            <div className="space-y-4">
              <Field
                label="AI features"
                htmlFor="ai_mode"
                hint="With Assist on, you can ask for an AI draft or reply label. Every draft still needs a person to approve it before it's sent."
              >
                <Controller
                  control={form.control}
                  name="ai_mode"
                  render={({ field }) => (
                    <Select
                      value={field.value}
                      items={AI_MODES}
                      onValueChange={(value) => value && field.onChange(value)}
                      disabled={disabled}
                    >
                      <SelectTrigger
                        id="ai_mode"
                        className="h-9 w-full bg-white sm:max-w-md"
                        aria-describedby="ai_mode-hint"
                      >
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent alignItemWithTrigger={false}>
                        <SelectItem value="off">{AI_MODES.off}</SelectItem>
                        <SelectItem value="assist">{AI_MODES.assist}</SelectItem>
                      </SelectContent>
                    </Select>
                  )}
                />
              </Field>

              <Field
                label="What you offer (AI drafts only use facts from here)"
                htmlFor="product_description"
                error={errors.product_description?.message}
                hint="Describe your product or service, who it's for and any proof points. AI drafts never invent claims beyond this."
              >
                <Textarea
                  id="product_description"
                  rows={5}
                  placeholder="We help independent dental clinics fill last-minute cancellations with an automated waitlist. Used by 120 clinics in the UK; average clinic recovers 9 appointments a month."
                  className="bg-white text-[13px]"
                  disabled={disabled}
                  aria-describedby="product_description-hint"
                  {...register("product_description")}
                />
                <CharCount value={productDescription} max={2000} />
              </Field>

              <Field
                label="Tone guidelines"
                htmlFor="tone_guidelines"
                error={errors.tone_guidelines?.message}
                hint="How your emails should sound, e.g. 'Friendly and brief. No jargon. British spelling.'"
              >
                <Textarea
                  id="tone_guidelines"
                  rows={3}
                  className="bg-white text-[13px]"
                  disabled={disabled}
                  aria-describedby="tone_guidelines-hint"
                  {...register("tone_guidelines")}
                />
                <CharCount value={toneGuidelines} max={1000} />
              </Field>
            </div>
          </div>

          {canEdit ? (
            <div className="flex justify-end">
              <Button type="submit" disabled={!form.formState.isDirty || save.isPending}>
                {save.isPending ? "Saving…" : "Save sender profile"}
              </Button>
            </div>
          ) : null}
        </form>
      )}
    </SettingsCard>
  );
}
