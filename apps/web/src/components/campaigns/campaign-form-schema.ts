import { z } from "zod";
import type { Campaign, CampaignCreate, CampaignStepInput, CampaignUpdate } from "@/lib/api/types";

/** Variables the API can fill in. `GET /templates/variables` is the source; this is the fallback. */
export const DEFAULT_VARIABLES = [
  "first_name",
  "company",
  "role",
  "industry",
  "pain_point",
  "sender_name",
  "sender_company",
  "unsubscribe_link",
] as const;

export const UNSUBSCRIBE_VARIABLE = "{{unsubscribe_link}}";
const VARIABLE_PATTERN = /{{\s*([^{}]*?)\s*}}/g;
const HHMM = /^([01]\d|2[0-3]):[0-5]\d$/;

export function hasUnsubscribeLink(body: string): boolean {
  return body.replace(/\s/g, "").includes(UNSUBSCRIBE_VARIABLE);
}

export function unknownVariables(text: string, allowed: readonly string[]): string[] {
  const found = new Set<string>();
  for (const match of text.matchAll(VARIABLE_PATTERN)) {
    if (!allowed.includes(match[1])) found.add(match[1]);
  }
  return [...found];
}

export const stepSchema = z
  .object({
    source: z.enum(["template", "custom"]),
    template_id: z.string(),
    subject_template: z.string(),
    body_template: z.string(),
    delay_days: z
      .number({ error: "Enter the number of days to wait" })
      .int("Use whole days")
      .min(0, "Days can't be negative")
      .max(365, "Wait at most 365 days"),
    use_ai: z.boolean(),
    ai_instructions: z.string().max(2000, "Keep instructions under 2,000 characters"),
    thread_with_previous: z.boolean(),
  })
  .superRefine((step, ctx) => {
    if (step.source === "template") {
      if (!step.template_id) {
        ctx.addIssue({ code: "custom", path: ["template_id"], message: "Choose a template" });
      }
      return;
    }
    const subject = step.subject_template.trim();
    const body = step.body_template.trim();
    if (!subject) {
      ctx.addIssue({ code: "custom", path: ["subject_template"], message: "Write a subject line" });
    } else if (subject.length > 500) {
      ctx.addIssue({
        code: "custom",
        path: ["subject_template"],
        message: "Keep the subject under 500 characters",
      });
    }
    if (!body) {
      ctx.addIssue({ code: "custom", path: ["body_template"], message: "Write the email body" });
    } else if (!hasUnsubscribeLink(body)) {
      ctx.addIssue({
        code: "custom",
        path: ["body_template"],
        message: `The body must include ${UNSUBSCRIBE_VARIABLE} so recipients can opt out`,
      });
    } else if (body.length > 20000) {
      ctx.addIssue({
        code: "custom",
        path: ["body_template"],
        message: "Keep the body under 20,000 characters",
      });
    }
    const unknown = unknownVariables(`${subject}\n${body}`, DEFAULT_VARIABLES);
    if (unknown.length) {
      ctx.addIssue({
        code: "custom",
        path: ["body_template"],
        message: `Unknown variables: ${unknown.join(", ")}. Use the chips below to insert valid ones.`,
      });
    }
  });

export const campaignFormSchema = z
  .object({
    name: z
      .string()
      .trim()
      .min(1, "Give the campaign a name")
      .max(255, "Keep the name under 255 characters"),
    niche_id: z.string().min(1, "Choose the niche this campaign targets"),
    steps: z.array(stepSchema).min(1, "Add at least one step").max(20, "A sequence has at most 20 steps"),
    timezone: z.string().min(1, "Choose a timezone"),
    sending_days: z.array(z.number().int().min(0).max(6)).min(1, "Pick at least one sending day"),
    sending_window_start: z.string().regex(HHMM, "Use a time like 09:00"),
    sending_window_end: z.string().regex(HHMM, "Use a time like 17:00"),
    daily_send_limit: z
      .number({ error: "Enter a daily limit" })
      .int("Use a whole number")
      .min(1, "Send at least 1 email a day")
      .max(10000, "The daily limit is at most 10,000"),
    per_domain_limit: z
      .number({ error: "Enter a whole number or leave it empty" })
      .int("Use a whole number")
      .min(1, "Use at least 1, or leave it empty for no limit")
      .max(1000, "The per-domain limit is at most 1,000")
      .nullable(),
    sender_credential_id: z.string(),
    stop_on_reply: z.boolean(),
  })
  .refine((values) => values.sending_window_start !== values.sending_window_end, {
    path: ["sending_window_end"],
    message: "The window must end at a different time than it starts",
  });

export type CampaignStepFormValues = z.infer<typeof stepSchema>;
export type CampaignFormValues = z.infer<typeof campaignFormSchema>;

export function newStep(overrides: Partial<CampaignStepFormValues> = {}): CampaignStepFormValues {
  return {
    source: "template",
    template_id: "system:follow-up",
    subject_template: "",
    body_template: "",
    delay_days: 3,
    use_ai: false,
    ai_instructions: "",
    thread_with_previous: true,
    ...overrides,
  };
}

export const DEFAULT_STEPS: CampaignStepFormValues[] = [
  newStep({ template_id: "system:intro", delay_days: 0, thread_with_previous: false }),
  newStep({ template_id: "system:follow-up", delay_days: 3 }),
];

export function browserTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

export function defaultCampaignValues(nicheId?: number | null): CampaignFormValues {
  return {
    name: "",
    niche_id: nicheId ? String(nicheId) : "",
    steps: DEFAULT_STEPS.map((step) => ({ ...step })),
    timezone: browserTimezone(),
    sending_days: [0, 1, 2, 3, 4],
    sending_window_start: "09:00",
    sending_window_end: "17:00",
    daily_send_limit: 20,
    per_domain_limit: null,
    sender_credential_id: "",
    stop_on_reply: true,
  };
}

export function campaignToFormValues(campaign: Campaign): CampaignFormValues {
  const steps = [...campaign.steps].sort((a, b) => a.step_number - b.step_number);
  return {
    name: campaign.name,
    niche_id: String(campaign.niche_id),
    steps: steps.map((step) => ({
      source: step.template_id ? "template" : "custom",
      template_id: step.template_id ?? "",
      subject_template: step.subject_template ?? "",
      body_template: step.body_template ?? "",
      delay_days: step.delay_days,
      use_ai: step.use_ai,
      ai_instructions: step.ai_instructions ?? "",
      thread_with_previous: step.thread_with_previous,
    })),
    timezone: campaign.timezone || browserTimezone(),
    sending_days: campaign.sending_days?.length ? campaign.sending_days : [0, 1, 2, 3, 4],
    sending_window_start: campaign.sending_window_start || "09:00",
    sending_window_end: campaign.sending_window_end || "17:00",
    daily_send_limit: campaign.daily_send_limit,
    per_domain_limit: campaign.per_domain_limit ?? null,
    sender_credential_id: campaign.sender_credential_id ? String(campaign.sender_credential_id) : "",
    stop_on_reply: campaign.stop_on_reply,
  };
}

export function stepsToPayload(steps: CampaignStepFormValues[]): CampaignStepInput[] {
  return steps.map((step, index) => {
    const custom = step.source === "custom";
    const instructions = step.ai_instructions.trim();
    return {
      step_number: index + 1,
      delay_days: index === 0 ? 0 : step.delay_days,
      template_id: custom ? null : step.template_id,
      subject_template: custom ? step.subject_template.trim() : null,
      body_template: custom ? step.body_template.trim() : null,
      use_ai: step.use_ai,
      ai_instructions: step.use_ai && instructions ? instructions : null,
      thread_with_previous: index === 0 ? false : step.thread_with_previous,
    };
  });
}

function schedulePayload(values: CampaignFormValues) {
  return {
    name: values.name.trim(),
    timezone: values.timezone,
    sending_days: [...values.sending_days].sort(),
    sending_window_start: values.sending_window_start,
    sending_window_end: values.sending_window_end,
    daily_send_limit: values.daily_send_limit,
    per_domain_limit: values.per_domain_limit,
    sender_credential_id: values.sender_credential_id ? Number(values.sender_credential_id) : null,
    stop_on_reply: values.stop_on_reply,
    steps: stepsToPayload(values.steps),
  };
}

export function toCreatePayload(values: CampaignFormValues): CampaignCreate {
  return { niche_id: Number(values.niche_id), ...schedulePayload(values) };
}

export function toUpdatePayload(values: CampaignFormValues): CampaignUpdate {
  return schedulePayload(values);
}
