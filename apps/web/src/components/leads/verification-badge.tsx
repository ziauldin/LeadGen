const STYLES: Record<string, { label: string; className: string }> = {
  valid: { label: "Verified", className: "bg-[var(--primary-fixed)] text-[var(--on-primary-fixed)]" },
  risky: { label: "Risky", className: "bg-[var(--tertiary-fixed,#ffe8c2)] text-[var(--on-surface)]" },
  invalid: { label: "Invalid", className: "bg-[var(--error-container)] text-[var(--on-error-container)]" },
  unknown: { label: "Unverified", className: "bg-[var(--surface-container)] text-[var(--on-surface-variant)]" },
};

/** The result of the last email check, with the provider's detail on hover. */
export function VerificationBadge({ status, detail }: { status?: string | null; detail?: string | null }) {
  if (!status) return null;
  const style = STYLES[status] ?? STYLES.unknown;
  return (
    <span
      title={detail ?? undefined}
      className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold ${style.className}`}
    >
      {style.label}
      {detail ? <span className="sr-only">: {detail}</span> : null}
    </span>
  );
}
