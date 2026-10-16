"use client";

import { useSearchParams } from "next/navigation";

/** Shown when a workspace sent the user here because it requires two-factor authentication. */
export function MfaRequiredNotice() {
  if (useSearchParams().get("required") !== "1") return null;
  return (
    <div role="alert" className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-[13px] text-amber-900">
      Your workspace requires two-factor authentication. Set it up below to continue.
    </div>
  );
}
