import { CheckCircle2, Circle, XCircle } from "lucide-react";
import type { ProviderCredential } from "@/lib/api/types";

export function ProviderStatusBadge({ credential }: { credential: ProviderCredential | undefined }) {
  let label = "Not set up";
  let className = "bg-[var(--surface-container)] text-[var(--on-surface-variant)]";
  let Icon = Circle;
  if (credential?.is_active) {
    label = "Active";
    className = "bg-[var(--secondary-fixed)] text-[var(--on-secondary-fixed)]";
    Icon = CheckCircle2;
  } else if (credential?.status === "error") {
    label = "Needs attention";
    className = "bg-[var(--error-container)] text-[var(--on-error-container)]";
    Icon = XCircle;
  } else if (credential?.status === "configured") {
    label = "Ready";
    className = "bg-[var(--primary-fixed)] text-[var(--on-primary-fixed)]";
    Icon = CheckCircle2;
  }
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-semibold ${className}`}
    >
      <Icon className="size-3" aria-hidden />
      {label}
    </span>
  );
}
