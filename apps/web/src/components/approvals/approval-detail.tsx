"use client";

import { useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Building2,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  FileText,
  Globe,
  Pencil,
  RefreshCw,
  Sparkles,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ScoreBadge } from "@/components/shared/score-badge";
import {
  EmailBody,
  GenerationBadge,
  GenerationNote,
  ProblemList,
} from "@/components/emails/email-parts";
import type { ApprovalItem, GenerationMode } from "@/lib/api/types";

function formatDate(value: string | null | undefined) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

export type ApprovalDetailProps = {
  item: ApprovalItem;
  index: number;
  count: number;
  onPrevious: () => void;
  onNext: () => void;
  onBack: () => void;
  isVerified: boolean;
  onApprove: () => void;
  approving: boolean;
  onReject: () => void;
  editing: boolean;
  onEditStart: () => void;
  onEditCancel: () => void;
  onEditSave: (changes: { subject?: string; body?: string }) => void;
  saving: boolean;
  saveError: string | null;
  onRegenerate: (mode: GenerationMode) => void;
  busy: boolean;
};

export function ApprovalDetail(props: ApprovalDetailProps) {
  const { item, isVerified, editing } = props;
  const lead = item.lead;
  const blockedReason = !isVerified
    ? "Confirm your email address to approve drafts. Check your inbox for the verification link."
    : !item.can_approve
      ? "Fix the problems above before this draft can be approved."
      : null;
  const scheduled = formatDate(item.scheduled_for);

  return (
    <article aria-labelledby="approval-detail-subject" className="flex flex-col">
      {/* Top bar: back (mobile), position, previous/next */}
      <div className="flex items-center gap-2 border-b border-[var(--outline-variant)] px-4 py-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={props.onBack}
          className="-ml-2 lg:hidden"
        >
          <ArrowLeft aria-hidden />
          All drafts
        </Button>
        <span className="text-xs text-[var(--on-surface-variant)]">
          Draft {props.index + 1} of {props.count}
        </span>
        <div className="ml-auto flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="Previous draft"
            onClick={props.onPrevious}
            disabled={props.index <= 0}
          >
            <ChevronLeft aria-hidden />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="Next draft"
            onClick={props.onNext}
            disabled={props.index >= props.count - 1}
          >
            <ChevronRight aria-hidden />
          </Button>
        </div>
      </div>

      <div className="grid gap-4 p-4 sm:p-5">
        {/* Lead card */}
        {lead ? (
          <section
            aria-label="Lead"
            className="flex items-start gap-3 rounded-lg bg-[var(--surface-container-low)] p-3"
          >
            <div
              aria-hidden
              className="flex size-10 shrink-0 items-center justify-center rounded-full bg-[var(--primary)] text-[12px] font-bold text-white"
            >
              {initials(lead.full_name)}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <Link
                  href={`/leads/${lead.id}`}
                  className="truncate text-[14px] font-semibold text-[var(--on-surface)] hover:text-[var(--primary)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)]"
                >
                  {lead.full_name}
                </Link>
                <ScoreBadge score={Math.round(lead.score)} />
              </div>
              {lead.job_title ? (
                <p className="truncate text-[13px] text-[var(--on-surface-variant)]">
                  {lead.job_title}
                </p>
              ) : null}
              <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[var(--on-surface-variant)]">
                {lead.company_name ? (
                  <span className="inline-flex items-center gap-1">
                    <Building2 className="size-3.5" aria-hidden />
                    {lead.company_name}
                  </span>
                ) : null}
                {lead.company_domain ? (
                  <a
                    href={`https://${lead.company_domain}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 hover:text-[var(--primary)] hover:underline"
                  >
                    <Globe className="size-3.5" aria-hidden />
                    {lead.company_domain}
                    <ExternalLink className="size-3" aria-hidden />
                    <span className="sr-only">(opens in a new tab)</span>
                  </a>
                ) : null}
              </p>
            </div>
          </section>
        ) : null}

        {/* Envelope */}
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[13px]">
          <dt className="text-[var(--on-surface-variant)]">To</dt>
          <dd className="min-w-0 truncate font-medium text-[var(--on-surface)]">
            {item.recipient_email}
          </dd>
          <dt className="text-[var(--on-surface-variant)]">Campaign</dt>
          <dd className="min-w-0 text-[var(--on-surface)]">
            {item.campaign_id && item.campaign_name ? (
              <Link
                href={`/campaigns/${item.campaign_id}`}
                className="hover:text-[var(--primary)] hover:underline"
              >
                {item.campaign_name}
              </Link>
            ) : (
              "One-off email"
            )}
            {item.step_number ? (
              <span className="text-[var(--on-surface-variant)]"> · Step {item.step_number}</span>
            ) : null}
          </dd>
          {scheduled ? (
            <>
              <dt className="text-[var(--on-surface-variant)]">Sends</dt>
              <dd className="text-[var(--on-surface)]">After approval, from {scheduled}</dd>
            </>
          ) : null}
          <dt className="text-[var(--on-surface-variant)]">Written</dt>
          <dd className="flex flex-wrap items-center gap-2">
            <GenerationBadge mode={item.generation_mode} />
            {item.edited_at ? (
              <span className="text-xs text-[var(--on-surface-variant)]">
                Edited {formatDate(item.edited_at)}
              </span>
            ) : null}
          </dd>
        </dl>

        <ProblemList problems={item.problems} />
        <GenerationNote mode={item.generation_mode} note={item.generation_note} />

        {/* Message */}
        {editing ? (
          <EditForm
            key={item.id}
            item={item}
            onCancel={props.onEditCancel}
            onSave={props.onEditSave}
            saving={props.saving}
            error={props.saveError}
          />
        ) : (
          <section
            aria-label="Email"
            className="rounded-lg border border-[var(--outline-variant)] bg-white"
          >
            <h3
              id="approval-detail-subject"
              className="border-b border-[var(--outline-variant)] px-4 py-3 text-[15px] font-semibold text-[var(--on-surface)]"
            >
              {item.subject}
            </h3>
            <EmailBody body={item.body} className="px-4 py-4" />
          </section>
        )}

        {/* Actions */}
        {!editing ? (
          <div className="grid gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <Button
                size="lg"
                onClick={props.onApprove}
                disabled={Boolean(blockedReason) || props.busy}
                aria-describedby={blockedReason ? "approve-blocked-reason" : undefined}
                className="px-4"
              >
                <Check aria-hidden />
                {props.approving ? "Approving…" : "Approve & next"}
              </Button>
              <Button
                size="lg"
                variant="outline"
                onClick={props.onReject}
                disabled={props.busy}
              >
                <X aria-hidden />
                Reject
              </Button>
              <Button
                size="lg"
                variant="outline"
                onClick={props.onEditStart}
                disabled={props.busy}
              >
                <Pencil aria-hidden />
                Edit
              </Button>
              <DropdownMenu>
                <DropdownMenuTrigger
                  render={<Button size="lg" variant="outline" disabled={props.busy} />}
                >
                  <RefreshCw aria-hidden />
                  Regenerate
                  <ChevronDown aria-hidden />
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56">
                  <DropdownMenuItem onClick={() => props.onRegenerate("template")}>
                    <FileText aria-hidden />
                    Rewrite from template
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => props.onRegenerate("ai")}>
                    <Sparkles aria-hidden />
                    Write with AI
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
            {blockedReason ? (
              <p id="approve-blocked-reason" className="text-xs text-[var(--on-surface-variant)]">
                {blockedReason}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>
    </article>
  );
}

function EditForm({
  item,
  onCancel,
  onSave,
  saving,
  error,
}: {
  item: ApprovalItem;
  onCancel: () => void;
  onSave: (changes: { subject?: string; body?: string }) => void;
  saving: boolean;
  error: string | null;
}) {
  const [subject, setSubject] = useState(item.subject);
  const [body, setBody] = useState(item.body);
  const subjectError = !subject.trim() ? "Add a subject line." : null;
  const bodyError = !body.trim() ? "The email can't be empty." : null;
  const unchanged = subject === item.subject && body === item.body;

  function submit() {
    if (subjectError || bodyError || saving) return;
    if (unchanged) {
      onCancel();
      return;
    }
    onSave({
      subject: subject !== item.subject ? subject : undefined,
      body: body !== item.body ? body : undefined,
    });
  }

  return (
    <form
      aria-label="Edit draft"
      className="grid gap-3 rounded-lg border border-[var(--primary)]/40 bg-white p-4"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
      onKeyDown={(event) => {
        if (event.key === "Escape" && !saving) {
          event.preventDefault();
          onCancel();
        }
        if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
          event.preventDefault();
          submit();
        }
      }}
    >
      <div className="grid gap-1.5">
        <label htmlFor="edit-subject" className="text-[13px] font-medium">
          Subject
        </label>
        <Input
          id="edit-subject"
          value={subject}
          maxLength={500}
          autoFocus
          aria-invalid={Boolean(subjectError)}
          onChange={(event) => setSubject(event.target.value)}
        />
        {subjectError ? <p className="text-xs text-[var(--error)]">{subjectError}</p> : null}
      </div>
      <div className="grid gap-1.5">
        <label htmlFor="edit-body" className="text-[13px] font-medium">
          Body
        </label>
        <Textarea
          id="edit-body"
          value={body}
          rows={14}
          maxLength={20000}
          aria-invalid={Boolean(bodyError)}
          aria-describedby="edit-body-hint"
          className="min-h-64 font-sans leading-[22px]"
          onChange={(event) => setBody(event.target.value)}
        />
        <p id="edit-body-hint" className="text-xs text-[var(--on-surface-variant)]">
          Plain text. Keep the opt-out line so the recipient can say no to further emails.
        </p>
        {bodyError ? <p className="text-xs text-[var(--error)]">{bodyError}</p> : null}
      </div>
      {error ? (
        <p
          role="alert"
          className="rounded-md border border-[var(--error)]/30 bg-[var(--error-container)]/60 px-3 py-2 text-[13px] text-[var(--on-error-container)]"
        >
          {error}
        </p>
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" disabled={saving || Boolean(subjectError || bodyError)}>
          {saving ? "Saving…" : "Save changes"}
        </Button>
        <Button type="button" variant="outline" onClick={onCancel} disabled={saving}>
          Cancel
        </Button>
        <span className="ml-auto hidden text-xs text-[var(--on-surface-variant)] sm:inline">
          Ctrl+Enter to save · Esc to cancel
        </span>
      </div>
    </form>
  );
}
