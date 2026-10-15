"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import {
  ArrowLeft,
  Building2,
  ExternalLink,
  Loader2,
  Mail,
  Sparkles,
  Users,
} from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { ButtonLink } from "@/components/ui/button-link";
import { Input } from "@/components/ui/input";
import { DataTable, type DataTableColumn } from "@/components/data-table/data-table";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState, LoadingState } from "@/components/shared/loading-error";
import { ScoreBadge } from "@/components/shared/score-badge";
import { StatusBadge } from "@/components/shared/status-badge";
import { EnrichmentBadge } from "@/components/companies/enrichment-badge";
import { enrichBlockedReason, useEnrichCompany } from "@/components/companies/use-enrich-company";
import { formatDateTime } from "@/components/leads/lead-status";
import { getErrorMessage } from "@/lib/api/client";
import { companiesApi, leadsApi } from "@/lib/api/endpoints";
import type { Company, CompanyUpdate, Lead } from "@/lib/api/types";

const schema = z.object({
  name: z.string().trim().min(1, "Name is required").max(255),
  website: z
    .string()
    .trim()
    .refine((v) => !v || /^https?:\/\/\S+\.\S+/i.test(v), "Enter a full URL starting with https://"),
  industry: z.string().max(255),
  country: z.string().max(100),
  size_estimate: z
    .string()
    .trim()
    .refine((v) => !v || (/^\d+$/.test(v) && Number(v) > 0), "Enter a whole number of people"),
});
type FormValues = z.infer<typeof schema>;

function toForm(company: Company): FormValues {
  return {
    name: company.name,
    website: company.website ?? "",
    industry: company.industry ?? "",
    country: company.country ?? "",
    size_estimate: company.size_estimate ? String(company.size_estimate) : "",
  };
}

const LEADS_PAGE_SIZE = 10;

export default function CompanyDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const valid = Number.isFinite(id) && id > 0;

  const company = useQuery({
    queryKey: ["companies", "detail", id],
    queryFn: () => companiesApi.get(id),
    enabled: valid,
    refetchInterval: (query) =>
      query.state.data?.enrichment_status === "in_progress" ? 5000 : false,
  });

  if (!valid) return <ErrorState message="This company link isn't valid." />;
  if (company.isLoading) return <LoadingState message="Loading company…" />;
  if (company.error || !company.data) {
    return (
      <div className="space-y-4">
        <BackLink />
        <ErrorState error={company.error} onRetry={() => company.refetch()} />
      </div>
    );
  }
  return <CompanyDetail company={company.data} />;
}

function BackLink() {
  return (
    <ButtonLink variant="ghost" size="sm" href="/companies">
      <ArrowLeft aria-hidden />
      All companies
    </ButtonLink>
  );
}

function CompanyDetail({ company }: { company: Company }) {
  const queryClient = useQueryClient();
  const { enrich, isPending } = useEnrichCompany();
  const [saveError, setSaveError] = useState<string | null>(null);
  const [leadsPage, setLeadsPage] = useState(0);
  const busy = isPending(company.id);
  const blocked = enrichBlockedReason(company);

  const form = useForm<FormValues>({ resolver: zodResolver(schema), values: toForm(company) });
  const { errors, isDirty, dirtyFields } = form.formState;

  const save = useMutation({
    mutationFn: (payload: CompanyUpdate) => companiesApi.update(company.id, payload),
    onError: (error) => setSaveError(getErrorMessage(error)),
    onSuccess: (updated) => {
      setSaveError(null);
      queryClient.setQueryData(["companies", "detail", company.id], updated);
      queryClient.invalidateQueries({ queryKey: ["companies"] });
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      toast.success("Company saved");
    },
  });

  function onSubmit(values: FormValues) {
    const blank = (v: string) => (v.trim() ? v.trim() : null);
    const payload: CompanyUpdate = {};
    if (dirtyFields.name) payload.name = values.name.trim();
    if (dirtyFields.website) payload.website = blank(values.website);
    if (dirtyFields.industry) payload.industry = blank(values.industry);
    if (dirtyFields.country) payload.country = blank(values.country);
    if (dirtyFields.size_estimate)
      payload.size_estimate = values.size_estimate ? Number(values.size_estimate) : null;
    save.mutate(payload);
  }

  const leads = useQuery({
    queryKey: ["leads", "list", { company_id: company.id, skip: leadsPage * LEADS_PAGE_SIZE }],
    queryFn: () =>
      leadsApi.list({
        company_id: company.id,
        skip: leadsPage * LEADS_PAGE_SIZE,
        limit: LEADS_PAGE_SIZE,
        sort: "full_name",
      }),
    placeholderData: keepPreviousData,
  });

  const leadColumns = useMemo<DataTableColumn<Lead>[]>(
    () => [
      {
        id: "name",
        header: "Name",
        cell: ({ row }) => (
          <div>
            <Link
              href={`/leads/${row.original.id}`}
              className="font-semibold text-[var(--on-surface)] hover:text-[var(--primary)] hover:underline"
            >
              {row.original.full_name}
            </Link>
            <p className="text-[12px] text-[var(--on-surface-variant)]">
              {row.original.job_title || "No job title"}
            </p>
          </div>
        ),
      },
      {
        id: "email",
        header: "Email",
        cell: ({ row }) =>
          row.original.primary_email ?? (
            <span className="text-[12px] text-[var(--on-surface-variant)] italic">No email</span>
          ),
      },
      {
        id: "status",
        header: "Status",
        cell: ({ row }) => <StatusBadge status={row.original.status} />,
      },
      {
        id: "score",
        header: "Score",
        cell: ({ row }) => <ScoreBadge score={Math.round(row.original.score)} />,
      },
    ],
    [],
  );

  const field = (name: keyof FormValues, label: string, props: React.ComponentProps<"input"> = {}) => (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={`company-${name}`} className="text-[12px] font-medium text-[var(--on-surface-variant)]">
        {label}
      </label>
      <Input
        id={`company-${name}`}
        aria-invalid={Boolean(errors[name])}
        aria-describedby={errors[name] ? `company-${name}-error` : undefined}
        className="h-9 text-[13px]"
        {...props}
        {...form.register(name)}
      />
      {errors[name] ? (
        <p id={`company-${name}-error`} className="text-[12px] text-destructive">
          {errors[name]?.message}
        </p>
      ) : null}
    </div>
  );

  return (
    <div>
      <div className="mb-2">
        <BackLink />
      </div>
      <PageHeader
        title={company.name}
        description={[company.industry, company.country].filter(Boolean).join(" · ") || "No industry or country recorded"}
        actions={
          <>
            {company.website ? (
              <ButtonLink variant="outline" external href={company.website}>
                <ExternalLink aria-hidden />
                Visit website
                <span className="sr-only">(opens in a new tab)</span>
              </ButtonLink>
            ) : null}
            <Button
              onClick={() => enrich(company.id)}
              disabled={busy || Boolean(blocked)}
              title={blocked ?? undefined}
            >
              {busy || company.enrichment_status === "in_progress" ? (
                <Loader2 className="animate-spin" aria-hidden />
              ) : (
                <Sparkles aria-hidden />
              )}
              {company.enrichment_status === "in_progress"
                ? "Enriching…"
                : company.enrichment_status === "completed"
                  ? "Enrich again"
                  : "Enrich"}
            </Button>
          </>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex min-w-0 flex-col gap-6">
          <form
            onSubmit={form.handleSubmit(onSubmit)}
            noValidate
            aria-labelledby="company-details-title"
            className="rounded-lg border border-[var(--outline-variant)] bg-white p-5 shadow-sm"
          >
            <h3
              id="company-details-title"
              className="mb-4 flex items-center gap-2 text-[15px] font-semibold text-[var(--on-surface)]"
            >
              <Building2 className="size-4 text-[var(--primary)]" aria-hidden />
              Company details
            </h3>
            <div className="grid gap-4 sm:grid-cols-2">
              {field("name", "Name")}
              {field("website", "Website", {
                type: "url",
                inputMode: "url",
                placeholder: "https://example.com",
              })}
              {field("industry", "Industry")}
              {field("country", "Country")}
              {field("size_estimate", "Company size (people)", { inputMode: "numeric" })}
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
                  form.reset(toForm(company));
                  setSaveError(null);
                }}
              >
                Discard
              </Button>
            </div>
          </form>

          <section
            aria-labelledby="company-leads-title"
            className="rounded-lg border border-[var(--outline-variant)] bg-white p-5 shadow-sm"
          >
            <h3
              id="company-leads-title"
              className="mb-4 flex items-center gap-2 text-[15px] font-semibold text-[var(--on-surface)]"
            >
              <Users className="size-4 text-[var(--primary)]" aria-hidden />
              Leads at this company
            </h3>
            <DataTable<Lead>
              caption={`Leads at ${company.name}`}
              columns={leadColumns}
              data={leads.data?.items}
              total={leads.data?.total ?? 0}
              page={leadsPage}
              pageSize={LEADS_PAGE_SIZE}
              onPageChange={setLeadsPage}
              isLoading={leads.isLoading || leads.isPlaceholderData}
              error={leads.error}
              onRetry={() => leads.refetch()}
              emptyState={
                <EmptyState
                  title="No leads linked yet"
                  description="Link a lead to this company from the lead's page, or import leads with this company name."
                />
              }
            />
          </section>
        </div>

        <aside className="flex min-w-0 flex-col gap-6">
          <section
            aria-labelledby="company-enrichment-title"
            className="rounded-lg border border-[var(--outline-variant)] bg-white p-5 text-[13px] shadow-sm"
          >
            <h3
              id="company-enrichment-title"
              className="mb-3 flex items-center gap-2 text-[15px] font-semibold text-[var(--on-surface)]"
            >
              <Sparkles className="size-4 text-[var(--primary)]" aria-hidden />
              Enrichment
            </h3>
            <div aria-live="polite">
              <EnrichmentBadge status={company.enrichment_status} />
              <p className="mt-2 text-[var(--on-surface-variant)]">
                {company.enrichment_message ??
                  (company.website
                    ? "Not enriched yet. Enrichment reads the public website (respecting robots.txt) for contact addresses."
                    : "Add a website above so this company can be enriched.")}
              </p>
            </div>
            <dl className="mt-4 space-y-2 border-t border-[var(--outline-variant)] pt-3">
              {[
                { label: "Contact page", url: company.contact_page_url },
                { label: "About page", url: company.about_page_url },
              ].map((item) => (
                <div key={item.label} className="flex items-center justify-between gap-3">
                  <dt className="text-[var(--on-surface-variant)]">{item.label}</dt>
                  <dd className="min-w-0 truncate">
                    {item.url ? (
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[var(--primary)] hover:underline"
                      >
                        Open
                        <span className="sr-only"> {item.label.toLowerCase()} (opens in a new tab)</span>
                      </a>
                    ) : (
                      "—"
                    )}
                  </dd>
                </div>
              ))}
              <div className="flex items-center justify-between gap-3">
                <dt className="text-[var(--on-surface-variant)]">robots.txt checked</dt>
                <dd>{company.robots_checked ? "Yes" : "No"}</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="text-[var(--on-surface-variant)]">Last updated</dt>
                <dd>{formatDateTime(company.updated_at)}</dd>
              </div>
            </dl>
          </section>

          <section
            aria-labelledby="company-emails-title"
            className="rounded-lg border border-[var(--outline-variant)] bg-white p-5 text-[13px] shadow-sm"
          >
            <h3
              id="company-emails-title"
              className="mb-3 flex items-center gap-2 text-[15px] font-semibold text-[var(--on-surface)]"
            >
              <Mail className="size-4 text-[var(--primary)]" aria-hidden />
              Discovered emails
              <span className="ml-auto text-[12px] font-normal text-[var(--on-surface-variant)]">
                {company.email_contacts.length}
              </span>
            </h3>
            {company.email_contacts.length > 0 ? (
              <ul className="space-y-2">
                {company.email_contacts.map((contact) => (
                  <li
                    key={contact.id}
                    className="flex items-start justify-between gap-2 rounded-md border border-[var(--outline-variant)] p-2.5"
                  >
                    <div className="min-w-0">
                      <p
                        className={`truncate font-medium ${contact.opted_out ? "text-[var(--on-surface-variant)] line-through" : "text-[var(--on-surface)]"}`}
                      >
                        {contact.email}
                      </p>
                      <p className="text-[12px] text-[var(--on-surface-variant)]">
                        {contact.source_provider ? `Found via ${contact.source_provider}` : "Source unknown"}
                      </p>
                    </div>
                    {contact.opted_out ? (
                      <span className="shrink-0 rounded-full bg-[var(--error-container)] px-2 py-0.5 text-[11px] font-semibold text-[var(--on-error-container)]">
                        Opted out
                      </span>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-[var(--on-surface-variant)]">
                No emails found yet. Run enrichment to look for public contact addresses.
              </p>
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}
