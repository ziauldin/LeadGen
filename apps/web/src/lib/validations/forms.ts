import { z } from "zod";

export const loginSchema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(8, "Password must be at least 8 characters"),
});

export const registerSchema = z.object({
  name: z.string().min(1, "Name is required"),
  email: z.string().email("Enter a valid email"),
  password: z.string().min(8, "Password must be at least 8 characters"),
});

export const nicheSchema = z.object({
  name: z.string().min(1, "Name is required"),
  country: z.string().min(1, "Country is required"),
  industry: z.string().min(1, "Industry is required"),
  target_roles: z.string(),
  keywords: z.string().min(1, "Add at least one keyword"),
  exclusion_keywords: z.string(),
  company_size_min: z.string().optional(),
  company_size_max: z.string().optional(),
});

export const settingsSchema = z.object({
  sender_name: z.string(),
  sender_company: z.string(),
  business_address: z.string(),
});

export type LoginFormValues = z.infer<typeof loginSchema>;
export type RegisterFormValues = z.infer<typeof registerSchema>;
export type NicheFormValues = z.infer<typeof nicheSchema>;
export type SettingsFormValues = z.infer<typeof settingsSchema>;

export function parseCommaList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function toOptionalInt(value: string | undefined): number | null {
  if (!value?.trim()) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function nicheFormToPayload(values: NicheFormValues) {
  return {
    name: values.name,
    country: values.country,
    industry: values.industry,
    target_roles: parseCommaList(values.target_roles),
    keywords: parseCommaList(values.keywords),
    exclusion_keywords: parseCommaList(values.exclusion_keywords),
    company_size_min: toOptionalInt(values.company_size_min),
    company_size_max: toOptionalInt(values.company_size_max),
  };
}
