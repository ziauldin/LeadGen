"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Archive, ArchiveRestore, Copy, Eye, FilePlus2, Lock, Pencil } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/loading-error";
import { EmailBody } from "@/components/emails/email-parts";
import { EMPTY_TEMPLATE, TemplateForm } from "@/components/templates/template-form";
import { templatesQueryKey } from "@/components/templates/template-select";
import {
  DEFAULT_REQUIRED,
  DEFAULT_VARIABLES,
  type TemplateFormValues,
} from "@/components/templates/template-validation";
import { getErrorMessage } from "@/lib/api/client";
import { templatesApi } from "@/lib/api/endpoints";
import type { EmailTemplate } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type Editor =
  | { kind: "create"; values: TemplateFormValues; title: string }
  | { kind: "edit"; template: EmailTemplate; values: TemplateFormValues };

function toValues(template: EmailTemplate): TemplateFormValues {
  return {
    name: template.name,
    description: template.description ?? "",
    subject: template.subject,
    body: template.body,
  };
}

function TemplateCard({
  template,
  onView,
  onEdit,
  onDuplicate,
  onArchive,
  onRestore,
}: {
  template: EmailTemplate;
  onView: () => void;
  onEdit: () => void;
  onDuplicate: () => void;
  onArchive: () => void;
  onRestore: () => void;
}) {
  return (
    <li
      className={cn(
        "flex flex-col gap-3 rounded-lg border border-[var(--outline-variant)] bg-white p-4 shadow-sm",
        template.is_archived && "bg-[var(--surface-container-low)]/50",
      )}
    >
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="truncate text-[14px] font-semibold text-[var(--on-surface)]">
            {template.name}
          </h3>
          {template.is_system ? (
            <span className="inline-flex items-center gap-1 rounded-full border border-[var(--primary)]/20 bg-[var(--primary-fixed)] px-2 py-0.5 text-[11px] font-semibold text-[var(--on-primary-fixed)]">
              <Lock className="size-3" aria-hidden />
              System
            </span>
          ) : null}
          {template.is_archived ? (
            <span className="rounded-full border border-[var(--outline-variant)] bg-[var(--surface-container-high)] px-2 py-0.5 text-[11px] font-semibold text-[var(--on-surface-variant)]">
              Archived
            </span>
          ) : null}
        </div>
        {template.description ? (
          <p className="mt-1 line-clamp-2 text-[13px] text-[var(--on-surface-variant)]">
            {template.description}
          </p>
        ) : null}
        <p className="mt-2 truncate rounded bg-[var(--surface-container-low)] px-2 py-1 font-mono text-xs text-[var(--on-surface)]">
          <span className="text-[var(--on-surface-variant)]">Subject: </span>
          {template.subject}
        </p>
      </div>
      <div className="mt-auto flex flex-wrap gap-1.5">
        {template.is_system ? (
          <Button size="sm" variant="outline" onClick={onView}>
            <Eye aria-hidden />
            View
          </Button>
        ) : template.is_archived ? null : (
          <Button size="sm" variant="outline" onClick={onEdit}>
            <Pencil aria-hidden />
            Edit
          </Button>
        )}
        <Button size="sm" variant="outline" onClick={onDuplicate}>
          <Copy aria-hidden />
          Duplicate
        </Button>
        {!template.is_system && !template.is_archived ? (
          <Button
            size="sm"
            variant="ghost"
            className="text-[var(--on-surface-variant)]"
            onClick={onArchive}
          >
            <Archive aria-hidden />
            Archive
          </Button>
        ) : null}
        {template.is_archived ? (
          <Button size="sm" variant="ghost" onClick={onRestore}>
            <ArchiveRestore aria-hidden />
            Restore
          </Button>
        ) : null}
      </div>
    </li>
  );
}

export function TemplateLibrary() {
  const queryClient = useQueryClient();
  const [showArchived, setShowArchived] = useState(false);
  const [editor, setEditor] = useState<Editor | null>(null);
  const [viewing, setViewing] = useState<EmailTemplate | null>(null);
  const [archiving, setArchiving] = useState<EmailTemplate | null>(null);

  const templates = useQuery({
    queryKey: templatesQueryKey(showArchived),
    queryFn: () => templatesApi.list(showArchived),
  });
  const variables = useQuery({
    queryKey: ["templates", "variables"],
    queryFn: templatesApi.variables,
    staleTime: Infinity,
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["templates"] });

  const save = useMutation({
    mutationFn: ({ editor: target, values }: { editor: Editor; values: TemplateFormValues }) => {
      const payload = {
        name: values.name.trim(),
        description: values.description.trim() || null,
        subject: values.subject,
        body: values.body,
      };
      return target.kind === "edit"
        ? templatesApi.update(target.template.id, payload)
        : templatesApi.create(payload);
    },
    meta: { silent: true },
    onSuccess: (template, { editor: target }) => {
      toast.success(target.kind === "edit" ? "Template saved" : `“${template.name}” created`);
      setEditor(null);
      void invalidate();
    },
  });

  const archive = useMutation({
    mutationFn: (template: EmailTemplate) => templatesApi.archive(template.id),
    onSuccess: (_data, template) => {
      toast.success(`“${template.name}” archived`, {
        description: "Existing drafts keep their text. It won't be offered for new emails.",
      });
      setArchiving(null);
      void invalidate();
    },
  });

  const restore = useMutation({
    mutationFn: (template: EmailTemplate) =>
      templatesApi.update(template.id, { is_archived: false }),
    onSuccess: (template) => {
      toast.success(`“${template.name}” restored`);
      void invalidate();
    },
  });

  const openCreate = () => {
    save.reset();
    setEditor({ kind: "create", values: EMPTY_TEMPLATE, title: "New template" });
  };
  const openDuplicate = (template: EmailTemplate) => {
    save.reset();
    setViewing(null);
    setEditor({
      kind: "create",
      title: "Duplicate template",
      values: { ...toValues(template), name: `Copy of ${template.name}`.slice(0, 255) },
    });
  };
  const openEdit = (template: EmailTemplate) => {
    save.reset();
    setEditor({ kind: "edit", template, values: toValues(template) });
  };

  const list = templates.data ?? [];
  const system = list.filter((template) => template.is_system);
  const own = list.filter((template) => !template.is_system);

  const cardProps = (template: EmailTemplate) => ({
    template,
    onView: () => setViewing(template),
    onEdit: () => openEdit(template),
    onDuplicate: () => openDuplicate(template),
    onArchive: () => setArchiving(template),
    onRestore: () => restore.mutate(template),
  });

  return (
    <div className="grid gap-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <label className="inline-flex cursor-pointer items-center gap-2 text-[13px] text-[var(--on-surface)]">
          <input
            type="checkbox"
            className="size-4 cursor-pointer accent-[var(--primary)]"
            checked={showArchived}
            onChange={(event) => setShowArchived(event.target.checked)}
          />
          Show archived templates
        </label>
        <Button onClick={openCreate} className="self-start sm:self-auto">
          <FilePlus2 aria-hidden />
          New template
        </Button>
      </div>

      {templates.isError ? (
        <ErrorState error={templates.error} onRetry={() => templates.refetch()} />
      ) : templates.isPending ? (
        <div role="status" aria-label="Loading templates" className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 4 }, (_, i) => (
            <div key={i} className="h-36 animate-pulse rounded-lg border border-[var(--outline-variant)] bg-white" />
          ))}
        </div>
      ) : (
        <>
          <section aria-labelledby="own-templates" className="grid gap-3">
            <div>
              <h3 id="own-templates" className="text-[15px] font-semibold text-[var(--on-surface)]">
                Your templates
              </h3>
              <p className="text-[13px] text-[var(--on-surface-variant)]">
                Shared with everyone in this workspace.
              </p>
            </div>
            {own.length ? (
              <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {own.map((template) => (
                  <TemplateCard key={template.id} {...cardProps(template)} />
                ))}
              </ul>
            ) : (
              <EmptyState
                title="No templates of your own yet"
                description="Start from scratch, or duplicate a system template below and adjust it to your voice."
                action={
                  <Button onClick={openCreate}>
                    <FilePlus2 aria-hidden />
                    New template
                  </Button>
                }
              />
            )}
          </section>

          <section aria-labelledby="system-templates" className="grid gap-3">
            <div>
              <h3 id="system-templates" className="text-[15px] font-semibold text-[var(--on-surface)]">
                System templates
              </h3>
              <p className="text-[13px] text-[var(--on-surface-variant)]">
                Ready to use and read-only. Duplicate one to make your own version.
              </p>
            </div>
            <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {system.map((template) => (
                <TemplateCard key={template.id} {...cardProps(template)} />
              ))}
            </ul>
          </section>
        </>
      )}

      {/* Create / edit */}
      <Dialog open={editor !== null} onOpenChange={(open) => !open && !save.isPending && setEditor(null)}>
        <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto sm:max-w-4xl">
          {editor ? (
            <>
              <DialogHeader>
                <DialogTitle>{editor.kind === "edit" ? "Edit template" : editor.title}</DialogTitle>
                <DialogDescription>
                  Use variables like {"{{first_name}}"} to personalise each email. Every email needs
                  an opt-out link.
                </DialogDescription>
              </DialogHeader>
              <TemplateForm
                key={editor.kind === "edit" ? editor.template.id : editor.values.name}
                defaultValues={editor.values}
                variables={variables.data?.variables ?? DEFAULT_VARIABLES}
                required={variables.data?.required ?? DEFAULT_REQUIRED}
                submitting={save.isPending}
                serverError={save.error ? getErrorMessage(save.error) : null}
                submitLabel={editor.kind === "edit" ? "Save changes" : "Create template"}
                onCancel={() => setEditor(null)}
                onSubmit={(values) => save.mutate({ editor, values })}
              />
            </>
          ) : null}
        </DialogContent>
      </Dialog>

      {/* Read-only view of a system template */}
      <Dialog open={viewing !== null} onOpenChange={(open) => !open && setViewing(null)}>
        <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto sm:max-w-2xl">
          {viewing ? (
            <>
              <DialogHeader>
                <DialogTitle>{viewing.name}</DialogTitle>
                <DialogDescription>
                  {viewing.description || "A built-in template."} System templates can&apos;t be
                  changed; duplicate it to make your own version.
                </DialogDescription>
              </DialogHeader>
              <div className="rounded-lg border border-[var(--outline-variant)] bg-white">
                <p className="border-b border-[var(--outline-variant)] px-4 py-3 font-mono text-[13px] font-semibold">
                  {viewing.subject}
                </p>
                <EmailBody body={viewing.body} className="px-4 py-3 font-mono text-[13px] leading-[20px]" />
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setViewing(null)}>
                  Close
                </Button>
                <Button onClick={() => openDuplicate(viewing)}>
                  <Copy aria-hidden />
                  Duplicate
                </Button>
              </DialogFooter>
            </>
          ) : null}
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={archiving !== null}
        onOpenChange={(open) => !open && setArchiving(null)}
        title={`Archive “${archiving?.name ?? ""}”?`}
        description="It won't be offered for new emails or campaign steps. Drafts already written from it keep their text. You can restore it later from archived templates."
        confirmLabel="Archive template"
        destructive
        loading={archive.isPending}
        onConfirm={() => archiving && archive.mutate(archiving)}
      />
    </div>
  );
}
