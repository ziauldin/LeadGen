"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { setConsent, useConsent } from "@/lib/consent";

export function CookieConsent() {
  const consent = useConsent();
  if (consent !== null) return null;
  return (
    <section
      aria-label="Cookie preferences"
      className="fixed inset-x-0 bottom-0 z-40 border-t border-[var(--outline-variant)] bg-white p-4 shadow-lg sm:inset-x-auto sm:bottom-4 sm:right-4 sm:max-w-md sm:rounded-lg sm:border"
    >
      <p className="text-[13px] leading-5 text-[var(--on-surface)]">
        We use essential cookies to run the site. With your permission we&apos;d also use analytics
        cookies to understand which pages help people. See our{" "}
        <Link href="/legal/cookies" className="underline">
          cookie policy
        </Link>
        .
      </p>
      <div className="mt-3 flex gap-2">
        <Button size="sm" onClick={() => setConsent("all")}>
          Accept all
        </Button>
        <Button size="sm" variant="outline" onClick={() => setConsent("essential")}>
          Essential only
        </Button>
      </div>
    </section>
  );
}
