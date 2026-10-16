import type { ReactNode } from "react";
import { CookieConsent } from "@/components/marketing/cookie-consent";
import { MarketingFooter, MarketingHeader } from "@/components/marketing/site-chrome";

export default function MarketingLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-[var(--background)] text-[var(--on-surface)]">
      <a
        href="#content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      <MarketingHeader />
      <main id="content" className="mx-auto max-w-6xl px-4 py-12 sm:py-16">
        {children}
      </main>
      <MarketingFooter />
      <CookieConsent />
    </div>
  );
}
