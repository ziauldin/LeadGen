"use client";

import { useId, useMemo, useRef, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AlertTriangle, Braces, Eye } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { EmailBody } from "@/components/emails/email-parts";
import {
  DEFAULT_REQUIRED,
  DEFAULT_VARIABLES,
  LIMITS,
  renderSample,
  templateSchema,
  type TemplateFormValues,
} from "@/components/templates/template-validation";

export const EMPTY_TEMPLATE: TemplateFormValues = {
  name: "",
  description: "",
  subject: "",
  body: "Hi {{first_name}},\n\n\n\nRegards,\n{{sender_name}}\n\nTo opt out of future emails, use this link: {{unsubscribe_link}}",
};

type Field = "subject" | "body";

function FieldError({ id, message }: { id: string; message?: string }) {
  if (!message) return null;
  return (
    <p id={id} className="text-xs text-[var(--error)]">
      {message}
    </p>
  );
}

/**
 * Create or edit a template. Validates like the API does (known variables only, an opt-out
 * link in the body) so problems show up while typing, and still shows any API error.
 */
export function TemplateForm({
  defaultValues,
  variables = DEFAULT_VARIABLES,
  required = DEFAULT_REQUIRED,
  onSubmit,
  onCancel,
  submitting = false,
  serverError,
  submitLabel = "Save template",
}: {
  defaultValues: TemplateFormValues;
  variables?: string[];
  required?: string[];
  onSubmit: (values: TemplateFormValues) => void;
  onCancel: () => void;
  submitting?: boolean;
  serverError?: string | null;
  submitLabel?: string;
}) {
  const uid = useId();
  const fid = (name: string) => `${uid}-${name}`;
  const schema = useMemo(() => templateSchema(variables, required), [variables, required]);
  const {
    register,
    handleSubmit,
    setValue,
    control,
    formState: { errors },
  } = useForm<TemplateFormValues>({
    resolver: zodResolver(schema),
    defaultValues,
    mode: "onTouched",
    reValidateMode: "onChange",
  });

  const subjectRef = useRef<HTMLInputElement | null>(null);
  const bodyRef = useRef<HTMLTextAreaElement | null>(null);
  const [lastField, setLastField] = useState<Field>("body");
  const [showPreview, setShowPreview] = useState(false);
  const [subject, body] = useWatch({ control, name: ["subject", "body"] });

  const subjectField = register("subject");
  const bodyField = register("body");

  /** Put `{{name}}` where the cursor was in the subject or body, then return focus there. */
  function insertVariable(name: string) {
    const element = lastField === "subject" ? subjectRef.current : bodyRef.current;
    const token = `{{${name}}}`;
    const current = (lastField === "subject" ? subject : body) ?? "";
    const start = element?.selectionStart ?? current.length;
    const end = element?.selectionEnd ?? current.length;
    const next = current.slice(0, start) + token + current.slice(end);
    setValue(lastField, next, { shouldDirty: true, shouldValidate: true, shouldTouch: true });
    // setValue writes straight to the (uncontrolled) element, so the caret can move now.
    if (element) {
      element.focus();
      const caret = start + token.length;
      element.setSelectionRange(caret, caret);
    }
  }

  return (
    <form
      noValidate
      aria-label="Template"
      onSubmit={handleSubmit(onSubmit)}
      className="grid gap-5 lg:grid-cols-[1fr_260px]"
    >
      <div className="grid min-w-0 content-start gap-4">
        {serverError ? (
          <p
            role="alert"
            className="flex gap-2 rounded-md border border-[var(--error)]/30 bg-[var(--error-container)]/60 px-3 py-2 text-[13px] text-[var(--on-error-container)]"
          >
            <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
            {serverError}
          </p>
        ) : null}

        <div className="grid gap-1.5">
          <label htmlFor={fid("name")} className="text-[13px] font-medium">
            Name
          </label>
          <Input
            id={fid("name")}
            maxLength={LIMITS.name}
            placeholder="e.g. Intro for clinic managers"
            aria-invalid={Boolean(errors.name)}
            aria-describedby={errors.name ? fid("name-error") : undefined}
            {...register("name")}
          />
          <FieldError id={fid("name-error")} message={errors.name?.message} />
        </div>

        <div className="grid gap-1.5">
          <label htmlFor={fid("description")} className="text-[13px] font-medium">
            Description <span className="font-normal text-muted-foreground">(optional)</span>
          </label>
          <Input
            id={fid("description")}
            maxLength={LIMITS.description}
            placeholder="When your team should use this template"
            aria-invalid={Boolean(errors.description)}
            {...register("description")}
          />
          <FieldError id={fid("description-error")} message={errors.description?.message} />
        </div>

        <div className="grid gap-1.5">
          <label htmlFor={fid("subject")} className="text-[13px] font-medium">
            Subject
          </label>
          <Input
            id={fid("subject")}
            placeholder="Quick question about {{company}}"
            aria-invalid={Boolean(errors.subject)}
            aria-describedby={errors.subject ? fid("subject-error") : undefined}
            {...subjectField}
            ref={(element) => {
              subjectField.ref(element);
              subjectRef.current = element;
            }}
            onFocus={() => setLastField("subject")}
          />
          <FieldError id={fid("subject-error")} message={errors.subject?.message} />
        </div>

        <div className="grid gap-1.5">
          <div className="flex items-end justify-between gap-2">
            <label htmlFor={fid("body")} className="text-[13px] font-medium">
              Body
            </label>
            <span className="text-xs text-muted-foreground">
              {(body ?? "").length.toLocaleString()} / {LIMITS.body.toLocaleString()}
            </span>
          </div>
          <Textarea
            id={fid("body")}
            rows={14}
            className="min-h-64 font-mono text-[13px] leading-[20px]"
            aria-invalid={Boolean(errors.body)}
            aria-describedby={[fid("body-hint"), errors.body ? fid("body-error") : ""].join(" ").trim()}
            {...bodyField}
            ref={(element) => {
              bodyField.ref(element);
              bodyRef.current = element;
            }}
            onFocus={() => setLastField("body")}
          />
          <p id={fid("body-hint")} className="text-xs text-[var(--on-surface-variant)]">
            Plain text. Must include {"{{unsubscribe_link}}"} so recipients can opt out.
          </p>
          <FieldError id={fid("body-error")} message={errors.body?.message} />
        </div>
      </div>

      <aside className="grid content-start gap-4">
        <div className="rounded-lg border border-[var(--outline-variant)] bg-[var(--surface-container-low)]/60 p-3">
          <h4 className="flex items-center gap-1.5 text-[13px] font-semibold">
            <Braces className="size-4" aria-hidden />
            Variables
          </h4>
          <p className="mt-1 text-xs text-[var(--on-surface-variant)]">
            Inserted into the {lastField} at the cursor. Filled in for each lead.
          </p>
          <ul className="mt-2 flex flex-wrap gap-1.5">
            {variables.map((name) => (
              <li key={name}>
                <button
                  type="button"
                  // Keep the cursor where it is in the field we're inserting into.
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => insertVariable(name)}
                  aria-label={`Insert ${name}`}
                  className="rounded-md border border-[var(--outline-variant)] bg-white px-1.5 py-0.5 font-mono text-[11px] text-[var(--on-surface)] hover:border-[var(--primary)] hover:text-[var(--primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)]"
                >
                  {`{{${name}}}`}
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-lg border border-[var(--outline-variant)] bg-white">
          <button
            type="button"
            onClick={() => setShowPreview((open) => !open)}
            aria-expanded={showPreview}
            className="flex w-full items-center gap-1.5 rounded-lg px-3 py-2 text-left text-[13px] font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)]"
          >
            <Eye className="size-4" aria-hidden />
            {showPreview ? "Hide sample preview" : "Preview with sample data"}
          </button>
          {showPreview ? (
            <div className="border-t border-[var(--outline-variant)] px-3 py-3">
              <p className="text-[13px] font-semibold">{renderSample(subject ?? "") || "No subject"}</p>
              <EmailBody body={renderSample(body ?? "")} className="mt-2 text-[12px] leading-[18px]" />
            </div>
          ) : null}
        </div>
      </aside>

      <div className="-mx-4 -mb-4 flex flex-col-reverse gap-2 rounded-b-xl border-t bg-muted/50 p-4 sm:flex-row sm:justify-end lg:col-span-2">
        <Button type="button" variant="outline" onClick={onCancel} disabled={submitting}>
          Cancel
        </Button>
        <Button type="submit" disabled={submitting}>
          {submitting ? "Saving…" : submitLabel}
        </Button>
      </div>
    </form>
  );
}
