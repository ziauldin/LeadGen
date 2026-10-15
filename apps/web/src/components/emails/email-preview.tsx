import type { ReactNode } from "react";
import { CheckCircle2, Mail } from "lucide-react";
import { ErrorState } from "@/components/shared/loading-error";
import {
  EmailBody,
  GenerationBadge,
  GenerationNote,
  ProblemList,
} from "@/components/emails/email-parts";
import type { EmailPreview as EmailPreviewData } from "@/lib/api/types";

/** A rendered email for one lead, with the compliance result and how it was written. */
export function EmailPreview({
  preview,
  loading,
  error,
  onRetry,
  placeholder,
}: {
  preview?: EmailPreviewData | null;
  loading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  placeholder?: ReactNode;
}) {
  if (error) {
    return (
      <div className="p-5">
        <ErrorState error={error} onRetry={onRetry} />
      </div>
    );
  }

  if (!preview) {
    if (loading) {
      return (
        <div role="status" aria-label="Loading preview" className="space-y-3 p-5">
          <div className="h-4 w-1/3 animate-pulse rounded bg-[var(--surface-container-high)]" />
          <div className="h-5 w-2/3 animate-pulse rounded bg-[var(--surface-container-high)]" />
          <div className="h-40 animate-pulse rounded bg-[var(--surface-container-high)]/60" />
        </div>
      );
    }
    return (
      <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
        <Mail className="mb-3 size-10 text-[var(--outline)]" aria-hidden />
        <div className="max-w-sm text-[13px] text-[var(--on-surface-variant)]">
          {placeholder ?? "Choose a lead to see the email they would receive."}
        </div>
      </div>
    );
  }

  const blocked = preview.compliance_errors.length > 0 || !preview.can_send;
  const problems = preview.compliance_errors.length
    ? preview.compliance_errors
    : !preview.has_opt_out_line
      ? ["The email is missing the opt-out line"]
      : [];

  return (
    <div className="grid gap-4 p-4 sm:p-5" aria-busy={loading || undefined}>
      <dl className="grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-1.5 text-[13px]">
        <dt className="text-[var(--on-surface-variant)]">To</dt>
        <dd className="min-w-0 truncate font-medium text-[var(--on-surface)]">
          {preview.recipient_email || "No email address"}
        </dd>
        <dt className="text-[var(--on-surface-variant)]">Written</dt>
        <dd>
          <GenerationBadge mode={preview.generation_mode} />
        </dd>
      </dl>

      {blocked ? (
        <ProblemList problems={problems} title="This email can't be sent yet" />
      ) : (
        <p className="flex items-center gap-2 rounded-lg border border-[var(--secondary)]/25 bg-[var(--secondary-container)]/25 px-3 py-2 text-[13px] text-[var(--on-secondary-fixed-variant)]">
          <CheckCircle2 className="size-4 shrink-0" aria-hidden />
          Compliance checks passed. Opt-out line present.
        </p>
      )}
      <GenerationNote mode={preview.generation_mode} note={preview.generation_note} />

      <section
        aria-label="Email preview"
        className={
          loading
            ? "rounded-lg border border-[var(--outline-variant)] bg-white opacity-60 transition-opacity"
            : "rounded-lg border border-[var(--outline-variant)] bg-white transition-opacity"
        }
      >
        <h3 className="border-b border-[var(--outline-variant)] px-4 py-3 text-[15px] font-semibold text-[var(--on-surface)]">
          {preview.subject}
        </h3>
        <EmailBody body={preview.body} className="px-4 py-4" />
      </section>
    </div>
  );
}
