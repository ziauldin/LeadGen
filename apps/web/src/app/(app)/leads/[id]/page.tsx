"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import {
  ArrowLeft,
  ExternalLink,
  Lock,
  Mail,
  MailPlus,
  Send,
  Trash2,
  UserRound,
} from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { ButtonLink } from "@/components/ui/button-link";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { ErrorState, LoadingState } from "@/components/shared/loading-error";
import { ScoreBadge } from "@/components/shared/score-badge";
import { StatusBadge } from "@/components/shared/status-badge";
import { OutreachChecklist } from "@/components/compliance/outreach-checklist";
import { AddToCampaignDialog } from "@/components/leads/add-to-campaign-dialog";
import { SelectField } from "@/components/leads/filter-controls";
import {
  SETTABLE_LEAD_STATUSES,
  formatDateTime,
  leadStatusLabel,
} from "@/components/leads/lead-status";
import { getErrorMessage } from "@/lib/api/client";
import { companiesApi, leadsApi, nichesApi } from "@/lib/api/endpoints";
import { VerificationBadge } from "@/components/leads/verification-badge";
import { LeadCrmPanel } from "@/components/crm/lead-crm-panel";
import type { Lead, LeadStatus, LeadUpdate } from "@/lib/api/types";

const schema = z.object({
  full_name: z.string().trim().min(1, "Name is required").max(255),
  job_title: z.string().max(255),
  linkedin_url: z
    .string()
    .trim()
    .refine((value) => !value || /^https?:\/\/\S+$/i.test(value), "Enter a full URL starting with https://"),
  company_id: z.string(),
  status: z.string(),
  qualification_notes: z.string().max(5000),
  compliance_source_note: z.string().max(2000),
  lawful_basis: z.enum(["legitimate_interest", "consent", "contract"]),
  lawful_basis_note: z.string().max(2000),
});
type FormValues = z.infer<typeof schema>;

const NO_COMPANY = "none";
const LAWFUL_BASIS_OPTIONS = [
  { value: "legitimate_interest", label: "Legitimate interest" },
  { value: "consent", label: "Consent" },
  { value: "contract", label: "Contract" },
];
const STATUS_OPTIONS = SETTABLE_LEAD_STATUSES.map((status) => ({
  value: status,
  label: leadStatusLabel(status),
}));

function toForm(lead: Lead): FormValues {
  return {
    full_name: lead.full_name,
    job_title: lead.job_title ?? "",
    linkedin_url: lead.linkedin_url ?? "",
    company_id: lead.company_id ? String(lead.company_id) : NO_COMPANY,
    status: lead.status,
    qualification_notes: lead.qualification_notes ?? "",
    compliance_source_note: lead.compliance_source_note ?? "",
    lawful_basis: (lead.lawful_basis ?? "legitimate_interest") as FormValues["lawful_basis"],
    lawful_basis_note: lead.lawful_basis_note ?? "",
  };
}

const blank = (value: string) => (value.trim() ? value.trim() : null);

function Field({
  id,
  label,
  error,
  hint,
  children,
}: {
  id: string;
  label: string;
  error?: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-[12px] font-medium text-[var(--on-surface-variant)]">
        {label}
      </label>
      {children}
      {error ? (
        <p id={`${id}-error`} className="text-[12px] text-destructive">
          {error}
        </p>
      ) : hint ? (
        <p className="text-[12px] text-[var(--on-surface-variant)]">{hint}</p>
      ) : null}
    </div>
  );
}

export default function LeadDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const valid = Number.isFinite(id) && id > 0;

  const lead = useQuery({
    queryKey: ["leads", "detail", id],
    queryFn: () => leadsApi.get(id),
    enabled: valid,
  });

  if (!valid) return <ErrorState message="This lead link isn't valid." />;
  if (lead.isLoading) return <LoadingState message="Loading lead…" />;
  if (lead.error || !lead.data) {
    return (
      <div className="space-y-4">
        <BackLink />
        <ErrorState error={lead.error} onRetry={() => lead.refetch()} />
      </div>
    );
  }
  return <LeadDetail lead={lead.data} />;
}

function BackLink() {
  return (
    <ButtonLink variant="ghost" size="sm" href="/leads">
      <ArrowLeft aria-hidden />
      All leads
    </ButtonLink>
  );
}

function LeadDetail({ lead }: { lead: Lead }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [campaignOpen, setCampaignOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const optedOut = lead.status === "opted_out";

  const readiness = useQuery({
    queryKey: ["leads", "detail", lead.id, "readiness"],
    queryFn: () => leadsApi.outreachReadiness(lead.id),
  });
  const companies = useQuery({
    queryKey: ["companies", "options"],
    queryFn: () => companiesApi.list({ limit: 200, sort: "name" }),
  });
  const niche = useQuery({
    queryKey: ["niches", "detail", lead.niche_id],
    queryFn: () => nichesApi.get(lead.niche_id),
  });

  const companyOptions = useMemo(() => {
    const items = (companies.data?.items ?? []).map((c) => ({ value: String(c.id), label: c.name }));
    if (lead.company && !items.some((item) => item.value === String(lead.company!.id))) {
      items.unshift({ value: String(lead.company.id), label: lead.company.name });
    }
    return [{ value: NO_COMPANY, label: "No company" }, ...items];
  }, [companies.data, lead.company]);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    values: toForm(lead),
  });
  const { errors, isDirty, dirtyFields } = form.formState;

  const save = useMutation({
    mutationFn: (payload: LeadUpdate) => leadsApi.update(lead.id, payload),
    // Validation problems from the API are shown next to the form, not just in a toast.
    onError: (error) => setSaveError(getErrorMessage(error)),
    onSuccess: (updated) => {
      setSaveError(null);
      queryClient.setQueryData(["leads", "detail", lead.id], updated);
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success("Lead saved");
    },
  });

  const remove = useMutation({
    mutationFn: () => leadsApi.delete(lead.id),
    onError: (error) => setDeleteError(getErrorMessage(error)),
    onSuccess: () => {
      toast.success(`Deleted ${lead.full_name}`);
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      router.push("/leads");
    },
  });

  function onSubmit(values: FormValues) {
    const payload: LeadUpdate = {};
    if (dirtyFields.full_name) payload.full_name = values.full_name.trim();
    if (dirtyFields.job_title) payload.job_title = blank(values.job_title);
    if (dirtyFields.linkedin_url) payload.linkedin_url = blank(values.linkedin_url);
    if (dirtyFields.qualification_notes)
      payload.qualification_notes = blank(values.qualification_notes);
    if (dirtyFields.compliance_source_note)
      payload.compliance_source_note = blank(values.compliance_source_note);
    if (dirtyFields.lawful_basis) payload.lawful_basis = values.lawful_basis;
    if (dirtyFields.lawful_basis_note) payload.lawful_basis_note = blank(values.lawful_basis_note);
    if (dirtyFields.company_id)
      payload.company_id = values.company_id === NO_COMPANY ? null : Number(values.company_id);
    if (dirtyFields.status && !optedOut) payload.status = values.status as LeadStatus;
    setSaveError(null);
    save.mutate(payload);
  }

  const subtitle = [lead.job_title, lead.company?.name].filter(Boolean).join(" at ");

  return (
    <div>
      <div className="mb-2">
        <BackLink />
      </div>
      <PageHeader
        title={lead.full_name}
        description={subtitle || "No job title or company recorded"}
        actions={
          <>
            <ButtonLink href={`/email-studio?lead_id=${lead.id}`}>
              <MailPlus aria-hidden />
              Write email
            </ButtonLink>
            <Button variant="outline" onClick={() => setCampaignOpen(true)} disabled={optedOut}>
              <Send aria-hidden />
              Add to campaign
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                setDeleteError(null);
                setDeleteOpen(true);
              }}
            >
              <Trash2 aria-hidden />
              Delete
            </Button>
          </>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex min-w-0 flex-col gap-6">
          <form
            onSubmit={form.handleSubmit(onSubmit)}
            noValidate
            className="rounded-lg border border-[var(--outline-variant)] bg-white p-5 shadow-sm"
            aria-labelledby="lead-details-title"
          >
            <h3
              id="lead-details-title"
              className="mb-4 flex items-center gap-2 text-[15px] font-semibold text-[var(--on-surface)]"
            >
              <UserRound className="size-4 text-[var(--primary)]" aria-hidden />
              Details
            </h3>

            <div className="grid gap-4 sm:grid-cols-2">
              <Field id="full_name" label="Full name" error={errors.full_name?.message}>
                <Input
                  id="full_name"
                  aria-invalid={Boolean(errors.full_name)}
                  aria-describedby={errors.full_name ? "full_name-error" : undefined}
                  className="h-9 text-[13px]"
                  {...form.register("full_name")}
                />
              </Field>
              <Field id="job_title" label="Job title" error={errors.job_title?.message}>
                <Input id="job_title" className="h-9 text-[13px]" {...form.register("job_title")} />
              </Field>
              <Field id="linkedin_url" label="LinkedIn URL" error={errors.linkedin_url?.message}>
                <Input
                  id="linkedin_url"
                  type="url"
                  inputMode="url"
                  placeholder="https://www.linkedin.com/in/…"
                  aria-invalid={Boolean(errors.linkedin_url)}
                  aria-describedby={errors.linkedin_url ? "linkedin_url-error" : undefined}
                  className="h-9 text-[13px]"
                  {...form.register("linkedin_url")}
                />
              </Field>
              <Controller
                control={form.control}
                name="company_id"
                render={({ field }) => (
                  <SelectField
                    id="company_id"
                    label="Company"
                    value={field.value}
                    onChange={field.onChange}
                    options={companyOptions}
                    placeholder={companies.isLoading ? "Loading companies…" : "Choose a company"}
                  />
                )}
              />
              <div className="sm:col-span-2">
                {optedOut ? (
                  <div
                    role="note"
                    className="flex items-start gap-2.5 rounded-lg border border-[var(--outline-variant)] bg-[var(--surface-container-low)] p-3 text-[13px]"
                  >
                    <Lock className="mt-0.5 size-4 shrink-0 text-[var(--on-surface-variant)]" aria-hidden />
                    <div>
                      <p className="font-medium text-[var(--on-surface)]">
                        Status locked: this person opted out
                      </p>
                      <p className="text-[var(--on-surface-variant)]">
                        They unsubscribed, so the status can&apos;t be changed and they won&apos;t be
                        emailed again.
                      </p>
                    </div>
                  </div>
                ) : (
                  <Controller
                    control={form.control}
                    name="status"
                    render={({ field }) => (
                      <SelectField
                        id="status"
                        label="Status"
                        value={field.value}
                        onChange={field.onChange}
                        options={STATUS_OPTIONS}
                        className="sm:max-w-xs"
                      />
                    )}
                  />
                )}
              </div>
              <div className="sm:col-span-2">
                <Field
                  id="qualification_notes"
                  label="Notes"
                  hint="Why this lead fits, what you know about them, anything to mention."
                  error={errors.qualification_notes?.message}
                >
                  <Textarea
                    id="qualification_notes"
                    rows={4}
                    className="text-[13px]"
                    {...form.register("qualification_notes")}
                  />
                </Field>
              </div>
              <div className="sm:col-span-2">
                <Field
                  id="compliance_source_note"
                  label="Source note"
                  hint="Where you found this person and the basis for contacting them. Required before outreach."
                  error={errors.compliance_source_note?.message}
                >
                  <Textarea
                    id="compliance_source_note"
                    rows={3}
                    className="text-[13px]"
                    {...form.register("compliance_source_note")}
                  />
                </Field>
              </div>
              <Controller
                control={form.control}
                name="lawful_basis"
                render={({ field }) => (
                  <SelectField
                    id="lawful_basis"
                    label="Lawful basis"
                    value={field.value}
                    onChange={field.onChange}
                    options={LAWFUL_BASIS_OPTIONS}
                  />
                )}
              />
              <div className="sm:col-span-2">
                <Field
                  id="lawful_basis_note"
                  label="Legitimate-interest note"
                  hint="Why contacting this person is reasonable and expected. Your workspace may require it before outreach."
                  error={errors.lawful_basis_note?.message}
                >
                  <Textarea
                    id="lawful_basis_note"
                    rows={2}
                    className="text-[13px]"
                    {...form.register("lawful_basis_note")}
                  />
                </Field>
              </div>
            </div>

            {saveError ? (
              <p
                role="alert"
                className="mt-4 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-[13px] text-destructive"
              >
                {saveError}
              </p>
            ) : null}

            <div className="mt-5 flex flex-wrap items-center gap-2">
              <Button type="submit" disabled={!isDirty || save.isPending}>
                {save.isPending ? "Saving…" : "Save changes"}
              </Button>
              <Button
                type="button"
                variant="ghost"
                disabled={!isDirty || save.isPending}
                onClick={() => {
                  form.reset(toForm(lead));
                  setSaveError(null);
                }}
              >
                Discard
              </Button>
              {isDirty ? (
                <span className="text-[12px] text-[var(--on-surface-variant)]">Unsaved changes</span>
              ) : null}
            </div>
          </form>

          <section
            aria-labelledby="lead-emails-title"
            className="rounded-lg border border-[var(--outline-variant)] bg-white p-5 shadow-sm"
          >
            <h3
              id="lead-emails-title"
              className="mb-4 flex items-center gap-2 text-[15px] font-semibold text-[var(--on-surface)]"
            >
              <Mail className="size-4 text-[var(--primary)]" aria-hidden />
              Email addresses
            </h3>
            {lead.email_contacts.length > 0 ? (
              <ul className="divide-y divide-[var(--outline-variant)] rounded-lg border border-[var(--outline-variant)]">
                {lead.email_contacts.map((contact) => (
                  <li
                    key={contact.id}
                    className="flex flex-col gap-2 p-3 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div className="min-w-0">
                      <p
                        className={`truncate text-[13px] font-medium ${contact.opted_out ? "text-[var(--on-surface-variant)] line-through" : "text-[var(--on-surface)]"}`}
                      >
                        {contact.email}
                        {contact.email === lead.primary_email ? (
                          <span className="ml-2 text-[11px] font-normal text-[var(--on-surface-variant)] no-underline">
                            (primary)
                          </span>
                        ) : null}
                      </p>
                      <p className="text-[12px] text-[var(--on-surface-variant)]">
                        {[
                          contact.source_provider ? `Found via ${contact.source_provider}` : null,
                          contact.confidence ? `${Math.round(contact.confidence * 100)}% confidence` : null,
                          contact.is_role_based ? "Role-based address" : null,
                        ]
                          .filter(Boolean)
                          .join(" · ") || "Source unknown"}
                      </p>
                    </div>
                    {contact.opted_out ? (
                      <span className="self-start rounded-full bg-[var(--error-container)] px-2 py-0.5 text-[11px] font-semibold text-[var(--on-error-container)] sm:self-auto">
                        Opted out
                      </span>
                    ) : (
                      <VerificationBadge status={contact.verification_status} detail={contact.verification_detail} />
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-[13px] text-[var(--on-surface-variant)]">
                No email address yet.{" "}
                {lead.company ? (
                  <>
                    Enrich{" "}
                    <Link
                      href={`/companies/${lead.company.id}`}
                      className="font-medium text-[var(--primary)] underline"
                    >
                      {lead.company.name}
                    </Link>{" "}
                    to look for public contact addresses.
                  </>
                ) : (
                  "Link this lead to a company with a website, then enrich it."
                )}
              </p>
            )}
          </section>
        </div>

        <aside className="flex min-w-0 flex-col gap-6">
          <section
            aria-label="Score and status"
            className="rounded-lg border border-[var(--outline-variant)] bg-white p-5 shadow-sm"
          >
            <dl className="grid grid-cols-2 gap-4 text-[13px]">
              <div>
                <dt className="mb-1 text-[12px] text-[var(--on-surface-variant)]">Score</dt>
                <dd>
                  <ScoreBadge score={Math.round(lead.score)} />
                </dd>
              </div>
              <div>
                <dt className="mb-1 text-[12px] text-[var(--on-surface-variant)]">Status</dt>
                <dd>
                  <StatusBadge status={lead.status} />
                </dd>
              </div>
              <div className="col-span-2">
                <dt className="mb-1 text-[12px] text-[var(--on-surface-variant)]">Niche</dt>
                <dd>
                  <Link
                    href={`/niches/${lead.niche_id}`}
                    className="font-medium text-[var(--primary)] hover:underline"
                  >
                    {niche.data?.name ?? `Niche #${lead.niche_id}`}
                  </Link>
                </dd>
              </div>
            </dl>
          </section>

          <OutreachChecklist
            lead={lead}
            readiness={readiness.data}
            loading={readiness.isLoading}
          />
          {readiness.isError ? (
            <ErrorState error={readiness.error} onRetry={() => readiness.refetch()} />
          ) : null}

          <section
            aria-labelledby="lead-source-title"
            className="rounded-lg border border-[var(--outline-variant)] bg-white p-5 text-[13px] shadow-sm"
          >
            <h3
              id="lead-source-title"
              className="mb-3 text-[15px] font-semibold text-[var(--on-surface)]"
            >
              Source
            </h3>
            <dl className="space-y-3">
              <div>
                <dt className="text-[12px] text-[var(--on-surface-variant)]">Source URL</dt>
                <dd className="min-w-0">
                  {lead.source_url ? (
                    <a
                      href={lead.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex max-w-full items-center gap-1 break-all text-[var(--primary)] hover:underline"
                    >
                      <span className="truncate">{lead.source_url}</span>
                      <ExternalLink className="size-3 shrink-0" aria-hidden />
                      <span className="sr-only">(opens in a new tab)</span>
                    </a>
                  ) : (
                    "Not recorded"
                  )}
                </dd>
              </div>
              <div>
                <dt className="text-[12px] text-[var(--on-surface-variant)]">Found via</dt>
                <dd>{lead.source_provider ?? "Unknown"}</dd>
              </div>
              {lead.linkedin_url ? (
                <div>
                  <dt className="text-[12px] text-[var(--on-surface-variant)]">LinkedIn</dt>
                  <dd>
                    <a
                      href={lead.linkedin_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-[var(--primary)] hover:underline"
                    >
                      View profile
                      <ExternalLink className="size-3" aria-hidden />
                      <span className="sr-only">(opens in a new tab)</span>
                    </a>
                  </dd>
                </div>
              ) : null}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <dt className="text-[12px] text-[var(--on-surface-variant)]">Added</dt>
                  <dd>{formatDateTime(lead.created_at)}</dd>
                </div>
                <div>
                  <dt className="text-[12px] text-[var(--on-surface-variant)]">Updated</dt>
                  <dd>{formatDateTime(lead.updated_at)}</dd>
                </div>
              </div>
            </dl>
          </section>
        </aside>
      </div>

      <LeadCrmPanel leadId={lead.id} leadName={lead.full_name} />

      <AddToCampaignDialog
        open={campaignOpen}
        onOpenChange={setCampaignOpen}
        leadIds={[lead.id]}
        nicheId={lead.niche_id}
      />

      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title={`Delete ${lead.full_name}?`}
        description="This removes the lead, its contacts and any unsent drafts. Leads that have already been emailed are kept for the record; disqualify them instead."
        confirmLabel="Delete lead"
        destructive
        loading={remove.isPending}
        onConfirm={() => remove.mutate()}
      >
        {deleteError ? (
          <p role="alert" className="rounded-lg bg-destructive/5 p-3 text-[13px] text-destructive">
            {deleteError}
          </p>
        ) : null}
      </ConfirmDialog>
    </div>
  );
}
