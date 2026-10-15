"use client";

import { useEffect, useMemo, useState } from "react";
import { useForm, type UseFormRegister } from "react-hook-form";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Eye, EyeOff, LockKeyhole } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field } from "@/components/settings/settings-card";
import type {
  ProviderDefinition,
  ProviderField,
} from "@/components/settings/providers/provider-catalog";
import { providerSettingsApi } from "@/lib/api/endpoints";
import type { ProviderCredential, ProviderType } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type Values = Record<string, string | boolean>;

function SecretInput({
  id,
  placeholder,
  register,
  name,
  invalid,
  describedBy,
}: {
  id: string;
  placeholder?: string;
  register: UseFormRegister<Values>;
  name: string;
  invalid: boolean;
  describedBy?: string;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <Input
        id={id}
        type={visible ? "text" : "password"}
        autoComplete="new-password"
        spellCheck={false}
        placeholder={placeholder}
        className="h-9 bg-white pr-10 font-mono"
        aria-invalid={invalid}
        aria-describedby={describedBy}
        {...register(name)}
      />
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        className="absolute right-1 top-1/2 -translate-y-1/2"
        onClick={() => setVisible((value) => !value)}
        aria-label={visible ? "Hide value" : "Show value"}
        aria-pressed={visible}
      >
        {visible ? <EyeOff aria-hidden /> : <Eye aria-hidden />}
      </Button>
    </div>
  );
}

function defaultsFor(fields: ProviderField[], editing: boolean): Values {
  const values: Values = {};
  for (const field of fields) {
    if (field.kind === "checkbox") values[field.name] = field.defaultValue ?? false;
    // When editing we don't know the saved values (they're never sent back), so start empty.
    else values[field.name] = editing ? "" : ((field.defaultValue as string | undefined) ?? "");
  }
  return values;
}

/** Turns the form into the API's config: trimmed strings, numbers, booleans; blanks skipped. */
export function toConfig(fields: ProviderField[], values: Values) {
  const config: Record<string, string | number | boolean> = {};
  for (const field of fields) {
    const value = values[field.name];
    if (field.kind === "checkbox") {
      config[field.name] = Boolean(value);
      continue;
    }
    const text = typeof value === "string" ? value.trim() : "";
    if (!text) continue;
    config[field.name] = field.kind === "number" ? Number(text) : text;
  }
  return config;
}

function validate(fields: ProviderField[], values: Values, editing: boolean) {
  const errors: Record<string, string> = {};
  for (const field of fields) {
    const value = values[field.name];
    if (field.kind === "checkbox") continue;
    const text = typeof value === "string" ? value.trim() : "";
    if (!text) {
      if (field.required && !editing) errors[field.name] = `${field.label} is required`;
      continue;
    }
    if (field.kind === "email" && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(text)) {
      errors[field.name] = "Enter a valid email address";
    }
    if (field.kind === "number") {
      const number = Number(text);
      if (!Number.isInteger(number) || number < 1 || number > 65535) {
        errors[field.name] = "Enter a port between 1 and 65535";
      }
    }
    if (field.kind === "url" && !/^https?:\/\/\S+$/.test(text)) {
      errors[field.name] = "Enter a full URL starting with https://";
    }
  }
  return errors;
}

export function ProviderConfigDialog({
  target,
  onOpenChange,
}: {
  target: {
    providerType: ProviderType;
    definition: ProviderDefinition;
    credential?: ProviderCredential;
  } | null;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  // Keep showing the last provider while the dialog animates closed.
  const [lastTarget, setLastTarget] = useState(target);
  if (target && target !== lastTarget) setLastTarget(target);
  const shown = target ?? lastTarget;
  const definition = shown?.definition;
  const fields = useMemo(() => definition?.fields ?? [], [definition]);
  const editing = Boolean(shown?.credential);
  const form = useForm<Values>({ defaultValues: defaultsFor(fields, editing) });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const { reset } = form;
  useEffect(() => {
    if (target) {
      reset(defaultsFor(fields, editing));
      setErrors({});
    }
  }, [target, fields, editing, reset]);

  const save = useMutation({
    mutationFn: (values: Values) =>
      providerSettingsApi.upsert({
        provider_type: target!.providerType,
        provider_name: target!.definition.name,
        config: toConfig(fields, values),
      }),
    onSuccess: (credential) => {
      void queryClient.invalidateQueries({ queryKey: ["provider-settings"] });
      void queryClient.invalidateQueries({ queryKey: ["onboarding"] });
      toast.success(
        credential.is_active
          ? `${credential.display_name} saved`
          : `${credential.display_name} saved. Test it, then activate it to start using it.`,
      );
      onOpenChange(false);
    },
  });

  function onSubmit(values: Values) {
    const found = validate(fields, values, editing);
    setErrors(found);
    if (Object.keys(found).length === 0) save.mutate(values);
  }

  const textFields = fields.filter((field) => field.kind !== "checkbox");
  const checkboxes = fields.filter((field) => field.kind === "checkbox");

  return (
    <Dialog open={target !== null} onOpenChange={(open) => !save.isPending && onOpenChange(open)}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-[560px]">
        <DialogHeader>
          <DialogTitle>
            {editing ? "Update" : "Set up"} {definition?.label}
          </DialogTitle>
          <DialogDescription className="flex items-start gap-1.5">
            <LockKeyhole className="mt-0.5 size-3.5 shrink-0" aria-hidden />
            <span>
              Keys and passwords are encrypted and never shown again.
              {editing ? " Leave a field empty to keep what's saved." : ""}
            </span>
          </DialogDescription>
        </DialogHeader>

        {fields.length === 0 ? (
          <p className="rounded-md bg-[var(--surface-container-low)] p-3 text-[13px] text-[var(--on-surface-variant)]">
            Nothing to fill in. Save to add it, then activate it when you want to use it.
          </p>
        ) : null}

        <form
          id="provider-config-form"
          onSubmit={form.handleSubmit(onSubmit)}
          className="grid gap-4 sm:grid-cols-2"
          noValidate
        >
          {textFields.map((field) => {
            const id = `provider-${field.name}`;
            const error = errors[field.name];
            const describedBy = error ? `${id}-error` : field.hint ? `${id}-hint` : undefined;
            const placeholder =
              field.kind === "secret" && editing ? "Saved — leave empty to keep" : field.placeholder;
            return (
              <Field
                key={field.name}
                label={field.label}
                htmlFor={id}
                hint={field.hint}
                error={error}
                required={field.required && !editing}
                className={cn(!field.half && "sm:col-span-2")}
              >
                {field.kind === "secret" ? (
                  <SecretInput
                    id={id}
                    name={field.name}
                    register={form.register}
                    placeholder={placeholder}
                    invalid={Boolean(error)}
                    describedBy={describedBy}
                  />
                ) : (
                  <Input
                    id={id}
                    type={field.kind === "number" ? "number" : field.kind === "email" ? "email" : "text"}
                    inputMode={field.kind === "number" ? "numeric" : undefined}
                    placeholder={placeholder}
                    className="h-9 bg-white"
                    aria-invalid={Boolean(error)}
                    aria-describedby={describedBy}
                    autoComplete="off"
                    {...form.register(field.name)}
                  />
                )}
              </Field>
            );
          })}
          {checkboxes.map((field) => (
            <label
              key={field.name}
              className="flex items-center gap-2 text-[13px] text-[var(--on-surface)] sm:col-span-2"
            >
              <input
                type="checkbox"
                className="size-4 accent-[var(--primary)]"
                {...form.register(field.name)}
              />
              {field.label}
            </label>
          ))}
        </form>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={save.isPending}>
            Cancel
          </Button>
          <Button type="submit" form="provider-config-form" disabled={save.isPending}>
            {save.isPending ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
