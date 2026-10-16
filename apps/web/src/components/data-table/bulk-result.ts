import { toast } from "sonner";
import type { BulkResult } from "@/lib/api/types";

/** One toast summarising a bulk action, including why items failed. */
export function toastBulkResult(result: BulkResult, verb: string) {
  const parts = [`${result.succeeded} ${verb}`];
  if (result.skipped) parts.push(`${result.skipped} skipped`);
  if (result.failed) parts.push(`${result.failed} failed`);
  const reasons = [
    ...new Set(
      result.results
        .filter((item) => item.status !== "ok" && item.detail)
        .map((item) => item.detail as string),
    ),
  ].slice(0, 3);
  const description = reasons.length ? reasons.join(" · ") : undefined;
  if (result.failed && !result.succeeded) toast.error(parts.join(", "), { description });
  else if (result.failed || result.skipped) toast.warning(parts.join(", "), { description });
  else toast.success(parts.join(", "));
}
