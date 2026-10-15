import { z } from "zod";

/** Used until `/templates/variables` loads; the API is the source of truth. */
export const DEFAULT_VARIABLES = [
  "first_name",
  "company",
  "role",
  "industry",
  "pain_point",
  "sender_name",
  "sender_company",
  "unsubscribe_link",
];
export const DEFAULT_REQUIRED = ["unsubscribe_link"];

export const LIMITS = { name: 255, description: 500, subject: 200, body: 10_000 } as const;

const VARIABLE = /{{\s*([^{}]*?)\s*}}/g;

/** Every `{{variable}}` name used in the text, in order of first use. */
export function findVariables(text: string): string[] {
  const names: string[] = [];
  for (const match of text.matchAll(VARIABLE)) {
    if (!names.includes(match[1])) names.push(match[1]);
  }
  return names;
}

export function unknownVariables(text: string, allowed: readonly string[]): string[] {
  return findVariables(text).filter((name) => !allowed.includes(name));
}

/** Mirrors the API, which ignores spaces when looking for a required variable. */
export function containsVariable(text: string, name: string): boolean {
  return text.replace(/ /g, "").includes(`{{${name}}}`);
}

function unknownMessage(unknown: string[]) {
  const list = unknown.map((name) => `{{${name}}}`).join(", ");
  return unknown.length === 1
    ? `${list} isn't a variable we can fill in. Pick one from the list.`
    : `${list} aren't variables we can fill in. Pick from the list.`;
}

export function templateSchema(
  variables: readonly string[] = DEFAULT_VARIABLES,
  required: readonly string[] = DEFAULT_REQUIRED,
) {
  return z
    .object({
      name: z
        .string()
        .trim()
        .min(1, "Give the template a name.")
        .max(LIMITS.name, `Keep the name under ${LIMITS.name} characters.`),
      description: z
        .string()
        .max(LIMITS.description, `Keep the description under ${LIMITS.description} characters.`),
      subject: z
        .string()
        .refine((value) => value.trim().length > 0, "Add a subject line.")
        .refine(
          (value) => value.length <= LIMITS.subject,
          `Keep the subject under ${LIMITS.subject} characters.`,
        ),
      body: z
        .string()
        .refine((value) => value.trim().length > 0, "Write the email body.")
        .refine(
          (value) => value.length <= LIMITS.body,
          `Keep the body under ${LIMITS.body.toLocaleString()} characters.`,
        ),
    })
    .superRefine((values, ctx) => {
      const subjectUnknown = unknownVariables(values.subject, variables);
      if (subjectUnknown.length) {
        ctx.addIssue({ code: "custom", path: ["subject"], message: unknownMessage(subjectUnknown) });
      }
      const bodyUnknown = unknownVariables(values.body, variables);
      if (bodyUnknown.length) {
        ctx.addIssue({ code: "custom", path: ["body"], message: unknownMessage(bodyUnknown) });
      }
      for (const name of required) {
        if (containsVariable(values.body, name)) continue;
        ctx.addIssue({
          code: "custom",
          path: ["body"],
          message:
            name === "unsubscribe_link"
              ? "Include {{unsubscribe_link}} in the body so every recipient can opt out."
              : `Include {{${name}}} in the body.`,
        });
      }
    });
}

export type TemplateFormValues = z.infer<ReturnType<typeof templateSchema>>;

/** Example values for the live preview; the real ones come from each lead and your settings. */
export const SAMPLE_VALUES: Record<string, string> = {
  first_name: "Alex",
  company: "Northwind Health",
  role: "Head of Operations",
  industry: "healthcare",
  pain_point: "patient scheduling",
  sender_name: "Sam Carter",
  sender_company: "Your company",
  unsubscribe_link: "https://example.com/unsubscribe/sample",
};

export function renderSample(text: string, samples: Record<string, string> = SAMPLE_VALUES) {
  return text.replace(VARIABLE, (whole, name: string) => samples[name] ?? whole);
}
