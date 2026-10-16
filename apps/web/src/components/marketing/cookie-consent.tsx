"use client";

import Link from "next/link";
import { setConsent, useConsent } from "@/lib/consent";

/** A slim bar at the bottom of the public site until the visitor chooses. */
export function CookieConsent() {
  const consent = useConsent();
  if (consent !== null) return null;
  return (
    <section
      aria-label="Cookie preferences"
      className="fixed inset-x-3 bottom-3 z-40 mx-auto flex max-w-3xl flex-col gap-3 rounded-2xl border border-white/15 bg-[#0d0f28]/95 px-4 py-3 text-[13px] text-[var(--mk-text,#eef0ff)] shadow-2xl backdrop-blur-xl sm:flex-row sm:items-center sm:justify-between"
    >
      <p className="leading-5 text-[#c9cdea]">
        We use essential cookies to run the site, and analytics cookies only if you allow them.{" "}
        <Link href="/legal/cookies" className="font-medium text-white underline underline-offset-2">
          Cookie policy
        </Link>
      </p>
      <div className="flex shrink-0 gap-2">
        <button
          type="button"
          onClick={() => setConsent("essential")}
          className="rounded-lg border border-white/20 px-3 py-1.5 font-semibold text-white hover:bg-white/10"
        >
          Essential only
        </button>
        <button type="button" onClick={() => setConsent("all")} className="mk-cta rounded-lg px-3 py-1.5 font-semibold">
          Accept all
        </button>
      </div>
    </section>
  );
}
