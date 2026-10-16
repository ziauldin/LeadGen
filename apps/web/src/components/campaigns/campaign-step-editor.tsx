"use client";

import { useId, useRef } from "react";
import { useFieldArray, useFormContext, useWatch } from "react-hook-form";
import {
  ArrowDown,
  ArrowUp,
  CheckCircle2,
  CircleAlert,
  Clock,
  CornerDownRight,
  FileText,
  PenLine,
  Plus,
  Sparkles,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  FieldError,
  FieldHint,
  FieldLabel,
  HighlightedTemplate,
  NativeSelect,
  Switch,
} from "@/components/campaigns/form-controls";
import {
  DEFAULT_VARIABLES,
  hasUnsubscribeLink,
  newStep,
  type CampaignFormValues,
} from "@/components/campaigns/campaign-form-schema";
import type { EmailTemplate } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const MAX_STEPS = 20;

type EditorProps = {
  templates: EmailTemplate[];
  templatesLoading?: boolean;
  /** Variable names offered as insert chips. */
  variables?: readonly string[];
  /** Editing an existing campaign: explain that steps with emails can't be removed. */
  editing?: boolean;
};

/**
 * Edits the `steps` array of the campaign form. Must be rendered inside a react-hook-form
 * `FormProvider` whose values match `CampaignFormValues`.
 */
export function CampaignStepEditor({
  templates,
  templatesLoading = false,
  variables = DEFAULT_VARIABLES,
  editing = false,
}: EditorProps) {
  const {
    control,
    formState: { errors },
  } = useFormContext<CampaignFormValues>();
  const { fields, append, remove, move } = useFieldArray({ control, name: "steps" });
  const rootError = errors.steps?.root?.message ?? errors.steps?.message;

  return (
    <div className="space-y-4">
      {editing ? (
        <p className="rounded-lg border border-[var(--outline-variant)] bg-[var(--surface-container-low)] px-3 py-2 text-[12px] text-[var(--on-surface-variant)]">
          Changes apply to emails drafted from now on. A step that already has emails can&apos;t be
          removed.
        </p>
      ) : null}

      <ol className="space-y-4" aria-label="Sequence steps">
        {fields.map((field, index) => (
          <li key={field.id}>
            <StepCard
              index={index}
              total={fields.length}
              templates={templates}
              templatesLoading={templatesLoading}
              variables={variables}
              onMoveUp={() => move(index, index - 1)}
              onMoveDown={() => move(index, index + 1)}
              onRemove={() => remove(index)}
            />
          </li>
        ))}
      </ol>

      <FieldError message={typeof rootError === "string" ? rootError : undefined} />

      <Button
        type="button"
        variant="outline"
        onClick={() => append(newStep())}
        disabled={fields.length >= MAX_STEPS}
        className="w-full border-dashed sm:w-auto"
      >
        <Plus aria-hidden />
        Add follow-up step
      </Button>
      {fields.length >= MAX_STEPS ? (
        <FieldHint>A sequence can have up to {MAX_STEPS} steps.</FieldHint>
      ) : null}
    </div>
  );
}

type StepCardProps = {
  index: number;
  total: number;
  templates: EmailTemplate[];
  templatesLoading: boolean;
  variables: readonly string[];
  onMoveUp: () => void;
  onMoveDown: () => void;
  onRemove: () => void;
};

function StepCard({
  index,
  total,
  templates,
  templatesLoading,
  variables,
  onMoveUp,
  onMoveDown,
  onRemove,
}: StepCardProps) {
  const uid = useId();
  const number = index + 1;
  const name = `steps.${index}` as const;
  const {
    register,
    control,
    setValue,
    getValues,
    formState: { errors, isSubmitted },
  } = useFormContext<CampaignFormValues>();
  const step = useWatch({ control, name });
  const stepErrors = errors.steps?.[index];

  const subjectRef = useRef<HTMLInputElement | null>(null);
  const bodyRef = useRef<HTMLTextAreaElement | null>(null);
  const lastFocused = useRef<"subject" | "body">("body");

  const selectedTemplate = templates.find((template) => template.id === step?.template_id);
  const templateOptions = templates.filter(
    (template) => !template.is_archived || template.id === step?.template_id,
  );
  const isCustom = step?.source === "custom";
  const bodyHasLink = hasUnsubscribeLink(step?.body_template ?? "");

  const subjectField = register(`${name}.subject_template`);
  const bodyField = register(`${name}.body_template`);

  function chooseSource(source: "template" | "custom") {
    setValue(`${name}.source`, source, { shouldDirty: true, shouldValidate: isSubmitted });
    if (source === "custom") {
      // Start from the chosen template's text so the user edits rather than retypes.
      const current = getValues(name);
      const template = templates.find((item) => item.id === current.template_id);
      if (template && !current.subject_template.trim() && !current.body_template.trim()) {
        setValue(`${name}.subject_template`, template.subject, { shouldDirty: true });
        setValue(`${name}.body_template`, template.body, { shouldDirty: true });
      }
    }
  }

  function insertVariable(variable: string) {
    const token = `{{${variable}}}`;
    const target = lastFocused.current === "subject" ? subjectRef.current : bodyRef.current;
    const fieldName =
      lastFocused.current === "subject"
        ? (`${name}.subject_template` as const)
        : (`${name}.body_template` as const);
    const current = getValues(fieldName) ?? "";
    const start = target?.selectionStart ?? current.length;
    const end = target?.selectionEnd ?? current.length;
    const next = current.slice(0, start) + token + current.slice(end);
    setValue(fieldName, next, { shouldDirty: true, shouldValidate: isSubmitted });
    requestAnimationFrame(() => {
      if (!target) return;
      target.focus();
      const caret = start + token.length;
      target.setSelectionRange(caret, caret);
    });
  }

  const ids = {
    delay: `${uid}-delay`,
    template: `${uid}-template`,
    subject: `${uid}-subject`,
    body: `${uid}-body`,
    bodyError: `${uid}-body-error`,
    ai: `${uid}-ai`,
  };

  return (
    <article
      aria-label={`Step ${number}`}
      className="rounded-lg border border-[var(--outline-variant)] bg-white shadow-sm"
    >
      <header className="flex flex-wrap items-center gap-3 border-b border-[var(--outline-variant)] bg-[var(--surface-container-low)] px-4 py-3">
        <span
          className="flex size-7 shrink-0 items-center justify-center rounded-full bg-[var(--primary)] text-[13px] font-bold text-white"
          aria-hidden
        >
          {number}
        </span>
        <div className="min-w-0 flex-1">
          <h4 className="text-[14px] font-semibold text-[var(--on-surface)]">
            Step {number}
            {index === 0 ? " · First email" : " · Follow-up"}
          </h4>
          <p className="text-[12px] text-[var(--on-surface-variant)]">
            {index === 0
              ? "Sends as soon as it's approved, within the sending window"
              : `Sends ${step?.delay_days ?? 0} day${step?.delay_days === 1 ? "" : "s"} after step ${index}, once approved`}
          </p>
        </div>
        <div className="flex items-center gap-1">
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={onMoveUp}
            disabled={index === 0}
            aria-label={`Move step ${number} up`}
          >
            <ArrowUp aria-hidden />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={onMoveDown}
            disabled={index === total - 1}
            aria-label={`Move step ${number} down`}
          >
            <ArrowDown aria-hidden />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={onRemove}
            disabled={total <= 1}
            aria-label={`Remove step ${number}`}
            className="text-[var(--error)] hover:bg-[var(--error-container)] hover:text-[var(--on-error-container)]"
          >
            <Trash2 aria-hidden />
          </Button>
        </div>
      </header>

      <div className="space-y-5 px-4 py-4">
        {index > 0 ? (
          <div className="max-w-xs">
            <FieldLabel htmlFor={ids.delay}>Wait before sending</FieldLabel>
            <div className="flex items-center gap-2">
              <Input
                id={ids.delay}
                type="number"
                inputMode="numeric"
                min={0}
                max={365}
                className="h-9 w-24 bg-white text-[13px]"
                aria-invalid={Boolean(stepErrors?.delay_days)}
                {...register(`${name}.delay_days`, { valueAsNumber: true })}
              />
              <span className="text-[13px] text-[var(--on-surface-variant)]">
                days after the previous email
              </span>
            </div>
            <FieldError message={stepErrors?.delay_days?.message} />
          </div>
        ) : (
          <p className="flex items-center gap-2 text-[13px] text-[var(--on-surface-variant)]">
            <Clock className="size-4 text-[var(--primary)]" aria-hidden />
            Sends immediately once approved.
          </p>
        )}

        <fieldset>
          <legend className="mb-1.5 text-[13px] font-semibold text-[var(--on-surface)]">
            Email content
          </legend>
          <div
            role="radiogroup"
            aria-label={`Content source for step ${number}`}
            className="inline-flex w-full rounded-lg border border-[var(--outline-variant)] bg-[var(--surface-container-low)] p-1 sm:w-auto"
          >
            {(
              [
                { value: "template", label: "Saved template", icon: FileText },
                { value: "custom", label: "Custom", icon: PenLine },
              ] as const
            ).map((option) => {
              const selected = (step?.source ?? "template") === option.value;
              return (
                <button
                  key={option.value}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  onClick={() => chooseSource(option.value)}
                  className={cn(
                    "flex flex-1 items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-[13px] font-medium transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50 sm:flex-none",
                    selected
                      ? "bg-white text-[var(--primary)] shadow-sm"
                      : "text-[var(--on-surface-variant)] hover:text-[var(--on-surface)]",
                  )}
                >
                  <option.icon className="size-3.5" aria-hidden />
                  {option.label}
                </button>
              );
            })}
          </div>
        </fieldset>

        {!isCustom ? (
          <div className="space-y-3">
            <div className="max-w-md">
              <FieldLabel htmlFor={ids.template}>Template</FieldLabel>
              <NativeSelect
                id={ids.template}
                disabled={templatesLoading}
                aria-invalid={Boolean(stepErrors?.template_id)}
                {...register(`${name}.template_id`)}
              >
                <option value="">{templatesLoading ? "Loading templates…" : "Choose a template"}</option>
                {templateOptions.map((template) => (
                  <option key={template.id} value={template.id}>
                    {template.name}
                    {template.is_system ? " (built-in)" : ""}
                    {template.is_archived ? " (archived)" : ""}
                  </option>
                ))}
                {step?.template_id &&
                !templatesLoading &&
                !templates.some((template) => template.id === step.template_id) ? (
                  <option value={step.template_id}>Template {step.template_id}</option>
                ) : null}
              </NativeSelect>
              <FieldError message={stepErrors?.template_id?.message} />
            </div>
            {selectedTemplate ? (
              <div
                className="rounded-lg border border-[var(--outline-variant)] bg-[var(--surface-container-low)] p-3"
                aria-label={`Preview of ${selectedTemplate.name}`}
              >
                {selectedTemplate.description ? (
                  <p className="mb-2 text-[12px] text-[var(--on-surface-variant)]">
                    {selectedTemplate.description}
                  </p>
                ) : null}
                <p className="text-[12px] font-semibold uppercase tracking-wide text-[var(--on-surface-variant)]">
                  Subject
                </p>
                <p className="mb-2 text-[13px] font-medium text-[var(--on-surface)]">
                  <HighlightedTemplate text={selectedTemplate.subject} />
                </p>
                <p className="text-[12px] font-semibold uppercase tracking-wide text-[var(--on-surface-variant)]">
                  Body
                </p>
                <div
                  tabIndex={0}
                  className="max-h-56 overflow-y-auto whitespace-pre-wrap break-words text-[13px] leading-[20px] text-[var(--on-surface)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)]"
                >
                  <HighlightedTemplate text={selectedTemplate.body} />
                </div>
              </div>
            ) : null}
          </div>
        ) : (
          <div className="space-y-3">
            <div>
              <FieldLabel htmlFor={ids.subject}>Subject</FieldLabel>
              <Input
                id={ids.subject}
                placeholder="e.g. Quick question about {{company}}"
                className="h-9 bg-white text-[13px]"
                aria-invalid={Boolean(stepErrors?.subject_template)}
                {...subjectField}
                ref={(element) => {
                  subjectField.ref(element);
                  subjectRef.current = element;
                }}
                onFocus={() => {
                  lastFocused.current = "subject";
                }}
              />
              <FieldError message={stepErrors?.subject_template?.message} />
            </div>
            <div>
              <FieldLabel htmlFor={ids.body}>Body</FieldLabel>
              <Textarea
                id={ids.body}
                rows={9}
                placeholder={"Hi {{first_name}},\n\n…\n\nTo opt out, use this link: {{unsubscribe_link}}"}
                className="min-h-48 bg-white text-[13px] leading-[20px]"
                aria-invalid={Boolean(stepErrors?.body_template)}
                aria-describedby={stepErrors?.body_template ? ids.bodyError : undefined}
                {...bodyField}
                ref={(element) => {
                  bodyField.ref(element);
                  bodyRef.current = element;
                }}
                onFocus={() => {
                  lastFocused.current = "body";
                }}
              />
              <FieldError id={ids.bodyError} message={stepErrors?.body_template?.message} />
              <p
                className={cn(
                  "mt-1 flex items-center gap-1.5 text-[12px]",
                  bodyHasLink ? "text-[var(--secondary)]" : "text-[var(--on-surface-variant)]",
                )}
              >
                {bodyHasLink ? (
                  <CheckCircle2 className="size-3.5" aria-hidden />
                ) : (
                  <CircleAlert className="size-3.5" aria-hidden />
                )}
                {bodyHasLink
                  ? "Opt-out link included"
                  : "Every email needs {{unsubscribe_link}} so recipients can opt out"}
              </p>
            </div>
            <div>
              <p className="mb-1.5 text-[12px] font-medium text-[var(--on-surface-variant)]">
                Insert a variable at the cursor:
              </p>
              <div className="flex flex-wrap gap-1.5">
                {variables.map((variable) => (
                  <button
                    key={variable}
                    type="button"
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => insertVariable(variable)}
                    aria-label={`Insert ${variable}`}
                    className="rounded-full border border-[var(--outline-variant)] bg-white px-2.5 py-1 font-mono text-[12px] text-[var(--primary)] transition-colors outline-none hover:bg-[var(--primary-fixed)] focus-visible:ring-3 focus-visible:ring-ring/50"
                  >
                    {`{{${variable}}}`}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        <div className="space-y-3 rounded-lg border border-[var(--outline-variant)] p-3">
          <Switch
            label={
              <span className="inline-flex items-center gap-1.5">
                <Sparkles className="size-3.5 text-[var(--primary)]" aria-hidden />
                Write with AI
              </span>
            }
            description={
              step?.use_ai
                ? "Each email is personalised for the lead. If a draft fails our checks, the template above is used instead and the draft says why."
                : "Personalise each email for the lead. The template above stays as the fallback."
            }
            {...register(`${name}.use_ai`)}
          />
          {step?.use_ai ? (
            <div>
              <FieldLabel htmlFor={ids.ai} optional>
                Instructions for the AI draft
              </FieldLabel>
              <Textarea
                id={ids.ai}
                rows={3}
                placeholder="e.g. Mention their recent hiring for sales roles. Keep it under 120 words."
                className="bg-white text-[13px]"
                aria-invalid={Boolean(stepErrors?.ai_instructions)}
                {...register(`${name}.ai_instructions`)}
              />
              <FieldError message={stepErrors?.ai_instructions?.message} />
            </div>
          ) : null}
        </div>

        {index > 0 ? (
          <Switch
            label={
              <span className="inline-flex items-center gap-1.5">
                <CornerDownRight className="size-3.5 text-[var(--primary)]" aria-hidden />
                Send as a reply in the same thread
              </span>
            }
            description="The follow-up lands in the same conversation as the previous email."
            {...register(`${name}.thread_with_previous`)}
          />
        ) : null}
      </div>
    </article>
  );
}
