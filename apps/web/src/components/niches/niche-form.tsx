"use client";

import { useId } from "react";
import { useForm, type UseFormRegisterReturn } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  nicheFormToPayload,
  nicheSchema,
  type NicheFormValues,
} from "@/lib/validations/forms";
import type { Niche, NicheCreate } from "@/lib/api/types";

function nicheToDefaults(niche?: Niche): NicheFormValues {
  return {
    name: niche?.name ?? "",
    country: niche?.country ?? "UK",
    industry: niche?.industry ?? "",
    target_roles: niche?.target_roles.join(", ") ?? "",
    keywords: niche?.keywords.join(", ") ?? "",
    exclusion_keywords: niche?.exclusion_keywords.join(", ") ?? "",
    company_size_min: niche?.company_size_min?.toString() ?? "",
    company_size_max: niche?.company_size_max?.toString() ?? "",
  };
}

function FormField({
  id,
  label,
  hint,
  error,
  multiline,
  rows = 3,
  registration,
  ...inputProps
}: {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  multiline?: boolean;
  rows?: number;
  registration: UseFormRegisterReturn;
} & Omit<React.ComponentProps<"input">, "id">) {
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-[13px] font-medium text-[var(--on-surface)]">
        {label}
      </label>
      {multiline ? (
        <Textarea
          id={id}
          rows={rows}
          placeholder={inputProps.placeholder}
          aria-invalid={Boolean(error)}
          aria-describedby={describedBy}
          className="text-[13px]"
          {...registration}
        />
      ) : (
        <Input
          id={id}
          aria-invalid={Boolean(error)}
          aria-describedby={describedBy}
          className="h-9 text-[13px]"
          {...inputProps}
          {...registration}
        />
      )}
      {error ? (
        <p id={`${id}-error`} className="text-[12px] text-destructive">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="text-[12px] text-[var(--on-surface-variant)]">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

export function NicheForm({
  niche,
  submitLabel,
  onSubmit,
  loading = false,
}: {
  niche?: Niche;
  submitLabel: string;
  onSubmit: (payload: NicheCreate) => void | Promise<void>;
  loading?: boolean;
}) {
  const uid = useId();
  const {
    register,
    handleSubmit,
    formState: { errors, isDirty },
  } = useForm<NicheFormValues>({
    resolver: zodResolver(nicheSchema),
    // Editing follows the saved niche (resetting after a save); creating starts blank.
    ...(niche ? { values: nicheToDefaults(niche) } : { defaultValues: nicheToDefaults() }),
  });
  const fid = (name: string) => `${uid}-${name}`;

  return (
    <form
      onSubmit={handleSubmit((values) => onSubmit(nicheFormToPayload(values)))}
      noValidate
      className="flex flex-col gap-5"
    >
      <FormField
        id={fid("name")}
        label="Niche name"
        placeholder="e.g. UK SaaS founders"
        error={errors.name?.message}
        registration={register("name")}
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <FormField
          id={fid("country")}
          label="Country"
          placeholder="e.g. UK"
          error={errors.country?.message}
          registration={register("country")}
        />
        <FormField
          id={fid("industry")}
          label="Industry"
          placeholder="e.g. Software"
          error={errors.industry?.message}
          registration={register("industry")}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <FormField
          id={fid("size-min")}
          label="Smallest company (people)"
          type="number"
          min={0}
          inputMode="numeric"
          placeholder="e.g. 10"
          registration={register("company_size_min")}
        />
        <FormField
          id={fid("size-max")}
          label="Largest company (people)"
          type="number"
          min={0}
          inputMode="numeric"
          placeholder="e.g. 200"
          registration={register("company_size_max")}
        />
      </div>

      <FormField
        id={fid("roles")}
        label="Target roles"
        hint="Separate with commas."
        placeholder="e.g. CEO, Founder, Head of Sales"
        registration={register("target_roles")}
      />

      <FormField
        id={fid("keywords")}
        label="Keywords"
        hint="Separate with commas. Used to build search queries and score leads."
        placeholder="e.g. B2B SaaS, workflow automation"
        multiline
        error={errors.keywords?.message}
        registration={register("keywords")}
      />

      <FormField
        id={fid("exclusions")}
        label="Exclude keywords"
        hint="Separate with commas. Results mentioning these are left out."
        placeholder="e.g. agency, recruitment"
        multiline
        rows={2}
        registration={register("exclusion_keywords")}
      />

      <Button type="submit" disabled={loading || (Boolean(niche) && !isDirty)} className="self-start">
        {loading ? "Saving…" : submitLabel}
      </Button>
    </form>
  );
}
