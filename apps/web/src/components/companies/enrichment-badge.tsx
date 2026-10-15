import { CheckCircle2, CircleDashed, Loader2, XCircle } from "lucide-react";
import type { Company } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type EnrichmentStatus = Company["enrichment_status"];

const CONFIG: Record<
  EnrichmentStatus,
  { label: string; icon: typeof CheckCircle2; className: string; spin?: boolean }
> = {
  pending: {
    label: "Not enriched",
    icon: CircleDashed,
    className: "bg-[var(--surface-container-high)] text-[var(--on-surface-variant)]",
  },
  in_progress: {
    label: "Enriching",
    icon: Loader2,
    className: "bg-[var(--primary-container)] text-[var(--on-primary-container)]",
    spin: true,
  },
  completed: {
    label: "Enriched",
    icon: CheckCircle2,
    className: "bg-emerald-50 text-emerald-700",
  },
  failed: {
    label: "Failed",
    icon: XCircle,
    className: "bg-[var(--error-container)] text-[var(--on-error-container)]",
  },
};

export const ENRICHMENT_STATUS_OPTIONS = (Object.keys(CONFIG) as EnrichmentStatus[]).map(
  (status) => ({ value: status, label: CONFIG[status].label }),
);

export function EnrichmentBadge({
  status,
  message,
  className,
}: {
  status: EnrichmentStatus | string | null | undefined;
  message?: string | null;
  className?: string;
}) {
  const config = CONFIG[(status ?? "pending") as EnrichmentStatus] ?? CONFIG.pending;
  const Icon = config.icon;
  return (
    <span
      title={message ?? undefined}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[12px] font-semibold whitespace-nowrap",
        config.className,
        className,
      )}
    >
      <Icon className={cn("size-3", config.spin && "animate-spin")} aria-hidden />
      {config.label}
    </span>
  );
}
