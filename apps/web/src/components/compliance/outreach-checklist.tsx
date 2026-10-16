import { AlertTriangle, CheckCircle2, ShieldCheck, XCircle } from "lucide-react";
import type { Lead } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type CheckItem = {
  label: string;
  hint: string;
  passed: boolean;
};

type Readiness = { ready: boolean; issues: string[] };

function buildChecks(lead: Lead, issues: string[]): CheckItem[] {
  const lower = issues.map((issue) => issue.toLowerCase());
  const suppressed = lower.some((issue) => issue.includes("suppress"));
  return [
    {
      label: "Email address on file",
      hint: "Enrich the company or add an email via CSV import.",
      passed: Boolean(lead.primary_email),
    },
    {
      label: "Hasn't opted out",
      hint: "This person unsubscribed and can't be contacted again.",
      passed: lead.status !== "opted_out",
    },
    {
      label: "Source URL recorded",
      hint: "Where this lead's details were found.",
      passed: Boolean(lead.source_url),
    },
    {
      label: "Source note recorded",
      hint: "A short note on how and why this person was found.",
      passed: Boolean(lead.compliance_source_note?.trim()),
    },
    {
      label: "Not on a suppression list",
      hint: "The email or its domain is suppressed in Settings.",
      passed: !suppressed,
    },
  ];
}

/**
 * Compliance checks before a lead can be emailed. Pass the API's `outreach-readiness`
 * result as `readiness` (preferred) or just its `issues`.
 */
export function OutreachChecklist({
  lead,
  issues,
  readiness,
  loading = false,
  className,
}: {
  lead: Lead;
  issues?: string[];
  readiness?: Readiness;
  loading?: boolean;
  className?: string;
}) {
  const problems = readiness?.issues ?? issues ?? [];
  const checks = buildChecks(lead, problems);
  const ready = readiness ? readiness.ready : checks.every((c) => c.passed) && !problems.length;

  return (
    <section
      aria-labelledby="outreach-readiness-title"
      className={cn(
        "rounded-lg border border-[var(--outline-variant)] bg-white p-5 shadow-sm",
        className,
      )}
    >
      <div className="mb-4 flex items-center justify-between gap-2">
        <h3
          id="outreach-readiness-title"
          className="flex items-center gap-2 text-[15px] font-semibold text-[var(--on-surface)]"
        >
          <ShieldCheck className="size-4 text-[var(--primary)]" aria-hidden />
          Outreach readiness
        </h3>
        {loading ? (
          <span className="text-[12px] text-[var(--on-surface-variant)]">Checking…</span>
        ) : (
          <span
            className={cn(
              "rounded-full px-2 py-0.5 text-[11px] font-semibold",
              ready ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-800",
            )}
          >
            {ready ? "Ready" : "Not ready"}
          </span>
        )}
      </div>

      <ul className="space-y-2.5 text-[13px]">
        {checks.map((check) => (
          <li key={check.label} className="flex items-start gap-2.5">
            {check.passed ? (
              <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-600" aria-hidden />
            ) : (
              <XCircle className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden />
            )}
            <span>
              <span className="text-[var(--on-surface)]">{check.label}</span>
              <span className="sr-only">{check.passed ? " (passed)" : " (missing)"}</span>
              {!check.passed ? (
                <span className="block text-[12px] text-[var(--on-surface-variant)]">
                  {check.hint}
                </span>
              ) : null}
            </span>
          </li>
        ))}
      </ul>

      {problems.length > 0 ? (
        <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-[12px] text-amber-900">
          <p className="mb-1 flex items-center gap-1.5 font-semibold">
            <AlertTriangle className="size-3.5" aria-hidden />
            Why outreach is blocked
          </p>
          <ul className="list-disc space-y-0.5 pl-5">
            {problems.map((issue) => (
              <li key={issue}>{issue}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <p className="mt-4 text-[12px] leading-[18px] text-[var(--on-surface-variant)]">
        {ready
          ? "Ready for outreach. Every email is still a draft until someone approves it."
          : "Fix the items above before writing or approving emails to this lead."}
      </p>
    </section>
  );
}
