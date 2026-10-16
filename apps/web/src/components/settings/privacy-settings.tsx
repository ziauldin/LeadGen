"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Download, FileArchive, RotateCw, UserX } from "lucide-react";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { LoadingState } from "@/components/shared/loading-error";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { AdminOnlyNotice, SettingsCard, formatDate } from "@/components/settings/settings-card";
import { useWorkspace } from "@/hooks/use-workspace";
import { privacyApi } from "@/lib/api/endpoints";
import type { components } from "@/lib/api/schema";

type DataRequest = components["schemas"]["DataRequestRead"];
type Governance = components["schemas"]["GovernanceSettings"];

const RETENTION_OPTIONS: Record<string, string> = {
  off: "Keep until deleted",
  "180": "6 months",
  "365": "1 year",
  "730": "2 years",
  "1095": "3 years",
};

const KIND_LABELS: Record<string, string> = {
  export: "Export a person's data",
  erase: "Erase a person",
  workspace_export: "Workspace export",
};

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-[var(--surface-container)] text-[var(--on-surface-variant)]",
  running: "bg-[var(--secondary-fixed)] text-[var(--on-secondary-fixed)]",
  completed: "bg-[var(--primary-fixed)] text-[var(--on-primary-fixed)]",
  failed: "bg-[var(--error-container)] text-[var(--on-error-container)]",
};

function RetentionSelect({
  id,
  label,
  value,
  disabled,
  onChange,
}: {
  id: string;
  label: string;
  value: number | null | undefined;
  disabled: boolean;
  onChange: (value: number | null) => void;
}) {
  return (
    <div className="grid gap-1.5">
      <label id={`${id}-label`} className="text-[13px] font-medium text-[var(--on-surface)]">
        {label}
      </label>
      <Select
        value={value ? String(value) : "off"}
        items={RETENTION_OPTIONS}
        disabled={disabled}
        onValueChange={(next) => onChange(!next || next === "off" ? null : Number(next))}
      >
        <SelectTrigger className="w-full bg-white sm:w-[220px]" aria-labelledby={`${id}-label`}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent alignItemWithTrigger={false}>
          {Object.entries(RETENTION_OPTIONS).map(([key, text]) => (
            <SelectItem key={key} value={key}>
              {text}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

function GovernanceCard({ canEdit }: { canEdit: boolean }) {
  const queryClient = useQueryClient();
  const settings = useQuery({ queryKey: ["privacy-settings"], queryFn: privacyApi.settings });
  const [draft, setDraft] = useState<Governance | null>(null);
  const value = draft ?? settings.data ?? null;

  const save = useMutation({
    mutationFn: (data: Governance) => privacyApi.updateSettings(data),
    onSuccess: (saved) => {
      queryClient.setQueryData(["privacy-settings"], saved);
      setDraft(null);
      toast.success("Data governance settings saved");
    },
  });

  return (
    <SettingsCard
      id="governance"
      title="Data governance"
      description="Rules for the personal data this workspace holds. Retention runs every night."
    >
      {settings.isLoading || !value ? (
        <LoadingState />
      ) : (
        <form
          className="grid gap-5"
          onSubmit={(event) => {
            event.preventDefault();
            if (draft) save.mutate(draft);
          }}
        >
          {!canEdit ? <AdminOnlyNotice what="change data governance settings" /> : null}
          <label className="flex items-start gap-3 text-[13px]">
            <input
              type="checkbox"
              className="mt-0.5 size-4 cursor-pointer accent-[var(--primary)]"
              checked={Boolean(value.require_lia_note)}
              disabled={!canEdit}
              onChange={(event) => setDraft({ ...value, require_lia_note: event.target.checked })}
            />
            <span>
              <span className="block font-medium text-[var(--on-surface)]">
                Require a legitimate-interest note before outreach
              </span>
              <span className="text-[var(--on-surface-variant)]">
                Leads contacted on the basis of legitimate interest need a short note explaining why the
                email is reasonable for them. Drafts can&apos;t be approved without it.
              </span>
            </span>
          </label>
          <div className="grid gap-4 sm:grid-cols-2">
            <RetentionSelect
              id="retention-leads"
              label="Delete leads never emailed after"
              value={value.retention_uncontacted_lead_days}
              disabled={!canEdit}
              onChange={(days) => setDraft({ ...value, retention_uncontacted_lead_days: days })}
            />
            <RetentionSelect
              id="retention-replies"
              label="Delete replies older than"
              value={value.retention_reply_days}
              disabled={!canEdit}
              onChange={(days) => setDraft({ ...value, retention_reply_days: days })}
            />
          </div>
          {canEdit ? (
            <div className="flex gap-2">
              <Button type="submit" disabled={!draft || save.isPending}>
                {save.isPending ? "Saving…" : "Save"}
              </Button>
              {draft ? (
                <Button type="button" variant="ghost" onClick={() => setDraft(null)}>
                  Cancel
                </Button>
              ) : null}
            </div>
          ) : null}
        </form>
      )}
    </SettingsCard>
  );
}

function RequestRow({ request }: { request: DataRequest }) {
  const queryClient = useQueryClient();
  const download = useMutation({
    mutationFn: () => privacyApi.downloadLink(request.id),
    onSuccess: (link) => window.location.assign(link.url),
  });
  const retry = useMutation({
    mutationFn: () => privacyApi.retry(request.id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["data-requests"] }),
  });
  const counts = request.summary
    ? Object.entries(request.summary)
        .filter(([, count]) => count > 0)
        .map(([name, count]) => `${count} ${name.replace(/_/g, " ")}`)
        .join(", ")
    : "";

  return (
    <li className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <p className="flex flex-wrap items-center gap-2 text-[14px] font-medium text-[var(--on-surface)]">
          {KIND_LABELS[request.kind] ?? request.kind}
          <span
            className={`rounded-full px-2 py-0.5 text-[11px] font-semibold capitalize ${STATUS_STYLES[request.status] ?? ""}`}
          >
            {request.status}
          </span>
        </p>
        <p className="text-[12px] text-[var(--on-surface-variant)]">
          {request.kind === "workspace_export"
            ? "All leads, companies, campaigns, emails, replies and suppressions"
            : (request.subject_email ?? "Erased person (kept only as a hash)")}
          {" · "}
          {formatDate(request.created_at)}
          {request.requested_by ? ` · ${request.requested_by}` : ""}
        </p>
        {counts ? <p className="text-[12px] text-[var(--on-surface-variant)]">{counts}</p> : null}
        {request.note ? <p className="text-[12px] text-[var(--on-surface-variant)]">Note: {request.note}</p> : null}
        {request.error ? <p className="text-[12px] text-[var(--error)]">{request.error}</p> : null}
      </div>
      <div className="flex shrink-0 gap-2">
        {request.downloadable ? (
          <Button size="sm" variant="outline" disabled={download.isPending} onClick={() => download.mutate()}>
            <Download aria-hidden /> Download
          </Button>
        ) : null}
        {request.status === "failed" ? (
          <Button size="sm" variant="outline" disabled={retry.isPending} onClick={() => retry.mutate()}>
            <RotateCw aria-hidden /> Retry
          </Button>
        ) : null}
      </div>
    </li>
  );
}

function DataRequestsCard({ canManage, canExport }: { canManage: boolean; canExport: boolean }) {
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [note, setNote] = useState("");
  const [confirmErase, setConfirmErase] = useState(false);

  const requests = useQuery({
    queryKey: ["data-requests"],
    queryFn: () => privacyApi.requests({ limit: 50 }),
    refetchInterval: (query) =>
      query.state.data?.items.some((r) => r.status === "pending" || r.status === "running") ? 3000 : false,
  });

  const create = useMutation({
    mutationFn: (kind: "export" | "erase" | "workspace_export") =>
      privacyApi.createRequest({
        kind,
        email: kind === "workspace_export" ? null : email.trim(),
        note: note.trim() || null,
      }),
    onSuccess: (request) => {
      void queryClient.invalidateQueries({ queryKey: ["data-requests"] });
      if (request.kind !== "workspace_export") {
        setEmail("");
        setNote("");
      }
      setConfirmErase(false);
      toast.success(
        request.kind === "erase"
          ? "Erasure started. Everything about this person is being deleted."
          : "Export started. It will be ready to download shortly.",
      );
    },
  });

  const validEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());

  return (
    <SettingsCard
      id="data-requests"
      title="Data requests"
      description="Answer access and erasure requests from the people you contact, or export everything in this workspace. Downloads stay available for 7 days."
      actions={
        canExport ? (
          <Button
            size="sm"
            variant="outline"
            disabled={create.isPending}
            onClick={() => create.mutate("workspace_export")}
          >
            <FileArchive aria-hidden /> Export workspace
          </Button>
        ) : null
      }
    >
      {canManage ? (
        <form
          className="mb-5 grid gap-3 rounded-md border border-[var(--outline-variant)] p-3 sm:p-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (validEmail) create.mutate("export");
          }}
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="grid gap-1.5">
              <label htmlFor="dsar-email" className="text-[13px] font-medium">
                Person&apos;s email address
              </label>
              <Input
                id="dsar-email"
                type="email"
                className="bg-white"
                value={email}
                placeholder="name@company.com"
                onChange={(event) => setEmail(event.target.value)}
              />
            </div>
            <div className="grid gap-1.5">
              <label htmlFor="dsar-note" className="text-[13px] font-medium">
                Note <span className="font-normal text-muted-foreground">(optional)</span>
              </label>
              <Input
                id="dsar-note"
                className="bg-white"
                maxLength={500}
                value={note}
                placeholder="e.g. Asked by email on 3 Oct"
                onChange={(event) => setNote(event.target.value)}
              />
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" size="sm" disabled={!validEmail || create.isPending}>
              <Download aria-hidden /> Export their data
            </Button>
            <Button
              type="button"
              size="sm"
              variant="destructive"
              disabled={!validEmail || create.isPending}
              onClick={() => setConfirmErase(true)}
            >
              <UserX aria-hidden /> Erase this person
            </Button>
          </div>
        </form>
      ) : (
        <AdminOnlyNotice what="export or erase a person's data" />
      )}

      {requests.isLoading ? (
        <LoadingState />
      ) : requests.data?.items.length ? (
        <ul aria-label="Data requests" className="divide-y divide-[var(--outline-variant)]">
          {requests.data.items.map((request) => (
            <RequestRow key={request.id} request={request} />
          ))}
        </ul>
      ) : (
        <p className="text-[13px] text-[var(--on-surface-variant)]">No data requests yet.</p>
      )}

      <ConfirmDialog
        open={confirmErase}
        onOpenChange={setConfirmErase}
        title={`Erase ${email.trim()}?`}
        description="This permanently deletes their leads, contact details, emails, replies and campaign history in this workspace. Only a one-way hash is kept, so they are never contacted again. This can't be undone."
        confirmLabel="Erase permanently"
        destructive
        loading={create.isPending}
        onConfirm={() => create.mutate("erase")}
      />
    </SettingsCard>
  );
}

export function PrivacySettings() {
  const { can, permissionsLoading } = useWorkspace();
  if (permissionsLoading) return <LoadingState />;
  return (
    <div className="space-y-6">
      <DataRequestsCard canManage={can("privacy.manage")} canExport={can("data.export")} />
      <GovernanceCard canEdit={can("privacy.manage")} />
      <p className="text-[12px] text-[var(--on-surface-variant)]">
        See the <a className="underline" href="/subprocessors">list of subprocessors</a> that may process
        this data on our behalf.
      </p>
    </div>
  );
}
