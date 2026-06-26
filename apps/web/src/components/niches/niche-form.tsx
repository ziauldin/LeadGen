"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  nicheFormToPayload,
  nicheSchema,
  type NicheFormValues,
} from "@/lib/validations/forms";
import type { Niche } from "@/lib/api/types";

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

export function NicheForm({
  niche,
  submitLabel,
  onSubmit,
  loading = false,
}: {
  niche?: Niche;
  submitLabel: string;
  onSubmit: (payload: ReturnType<typeof nicheFormToPayload>) => void | Promise<void>;
  loading?: boolean;
}) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<NicheFormValues>({
    resolver: zodResolver(nicheSchema),
    defaultValues: nicheToDefaults(niche),
  });

  return (
    <form
      onSubmit={handleSubmit((values) => onSubmit(nicheFormToPayload(values)))}
      className="space-y-4"
    >
      <div className="space-y-2">
        <label className="text-sm font-medium">Name</label>
        <Input {...register("name")} />
        {errors.name ? <p className="text-sm text-destructive">{errors.name.message}</p> : null}
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <label className="text-sm font-medium">Country</label>
          <Input {...register("country")} />
          {errors.country ? (
            <p className="text-sm text-destructive">{errors.country.message}</p>
          ) : null}
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium">Industry</label>
          <Input {...register("industry")} />
          {errors.industry ? (
            <p className="text-sm text-destructive">{errors.industry.message}</p>
          ) : null}
        </div>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <label className="text-sm font-medium">Min company size</label>
          <Input type="number" min={0} {...register("company_size_min")} />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium">Max company size</label>
          <Input type="number" min={0} {...register("company_size_max")} />
        </div>
      </div>
      <div className="space-y-2">
        <label className="text-sm font-medium">Target roles (comma-separated)</label>
        <Input {...register("target_roles")} />
      </div>
      <div className="space-y-2">
        <label className="text-sm font-medium">Keywords</label>
        <Textarea rows={3} {...register("keywords")} />
        {errors.keywords ? (
          <p className="text-sm text-destructive">{errors.keywords.message}</p>
        ) : null}
      </div>
      <div className="space-y-2">
        <label className="text-sm font-medium">Exclusion keywords</label>
        <Textarea rows={2} {...register("exclusion_keywords")} />
      </div>
      <Button type="submit" disabled={loading}>
        {loading ? "Saving…" : submitLabel}
      </Button>
    </form>
  );
}
