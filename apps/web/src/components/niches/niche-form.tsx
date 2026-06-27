"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
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

  const labelClass = "block text-[13px] font-semibold mb-1.5";
  const inputClass = "w-full px-3 py-2.5 border rounded text-[13px] outline-none transition-all";
  const errorClass = "text-[12px] mt-1 text-red-500";

  const handleFocus = (e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    e.target.style.borderColor = "var(--primary)";
    e.target.style.boxShadow = "0 0 0 1px var(--primary)";
  };

  const handleBlur = (e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    e.target.style.borderColor = "var(--outline-variant)";
    e.target.style.boxShadow = "none";
  };

  const inputStyle: React.CSSProperties = {
    borderColor: "var(--outline-variant)",
    color: "var(--on-surface)",
    background: "var(--surface-container-lowest)",
  };

  return (
    <form
      onSubmit={handleSubmit((values) => onSubmit(nicheFormToPayload(values)))}
      className="flex flex-col gap-5"
    >
      <div>
        <label className={labelClass} style={{ color: "var(--on-surface)" }}>
          Niche Name
        </label>
        <input
          {...register("name")}
          className={inputClass}
          style={inputStyle}
          placeholder="e.g. UK Tech Founders"
          onFocus={handleFocus}
          onBlur={handleBlur}
        />
        {errors.name && <p className={errorClass}>{errors.name.message}</p>}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className={labelClass} style={{ color: "var(--on-surface)" }}>
            Country
          </label>
          <input
            {...register("country")}
            className={inputClass}
            style={inputStyle}
            placeholder="e.g. UK"
            onFocus={handleFocus}
            onBlur={handleBlur}
          />
          {errors.country && <p className={errorClass}>{errors.country.message}</p>}
        </div>
        <div>
          <label className={labelClass} style={{ color: "var(--on-surface)" }}>
            Industry
          </label>
          <input
            {...register("industry")}
            className={inputClass}
            style={inputStyle}
            placeholder="e.g. Software, E-commerce"
            onFocus={handleFocus}
            onBlur={handleBlur}
          />
          {errors.industry && <p className={errorClass}>{errors.industry.message}</p>}
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className={labelClass} style={{ color: "var(--on-surface)" }}>
            Min Company Size
          </label>
          <input
            type="number"
            min={0}
            {...register("company_size_min")}
            className={inputClass}
            style={inputStyle}
            placeholder="e.g. 10"
            onFocus={handleFocus}
            onBlur={handleBlur}
          />
        </div>
        <div>
          <label className={labelClass} style={{ color: "var(--on-surface)" }}>
            Max Company Size
          </label>
          <input
            type="number"
            min={0}
            {...register("company_size_max")}
            className={inputClass}
            style={inputStyle}
            placeholder="e.g. 200"
            onFocus={handleFocus}
            onBlur={handleBlur}
          />
        </div>
      </div>

      <div>
        <label className={labelClass} style={{ color: "var(--on-surface)" }}>
          Target Roles (comma-separated)
        </label>
        <input
          {...register("target_roles")}
          className={inputClass}
          style={inputStyle}
          placeholder="e.g. CEO, Founder, VP Sales"
          onFocus={handleFocus}
          onBlur={handleBlur}
        />
      </div>

      <div>
        <label className={labelClass} style={{ color: "var(--on-surface)" }}>
          Keywords (comma-separated)
        </label>
        <textarea
          rows={3}
          {...register("keywords")}
          className="w-full px-3 py-2 border rounded text-[13px] outline-none transition-all"
          style={inputStyle}
          placeholder="e.g. artificial intelligence, machinery, logistics"
          onFocus={handleFocus}
          onBlur={handleBlur}
        />
        {errors.keywords && <p className={errorClass}>{errors.keywords.message}</p>}
      </div>

      <div>
        <label className={labelClass} style={{ color: "var(--on-surface)" }}>
          Exclusion Keywords (comma-separated)
        </label>
        <textarea
          rows={2}
          {...register("exclusion_keywords")}
          className="w-full px-3 py-2 border rounded text-[13px] outline-none transition-all"
          style={inputStyle}
          placeholder="e.g. agency, consultant, recruitment"
          onFocus={handleFocus}
          onBlur={handleBlur}
        />
      </div>

      <button
        type="submit"
        disabled={loading}
        className="self-start flex items-center justify-center px-6 py-2.5 rounded text-[13px] font-medium text-white transition-opacity disabled:opacity-60 active:scale-[0.98] shadow-sm"
        style={{ background: "var(--primary)" }}
      >
        {loading ? "Saving niche…" : submitLabel}
      </button>
    </form>
  );
}
