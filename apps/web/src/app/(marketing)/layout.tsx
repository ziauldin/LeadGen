import type { ReactNode } from "react";
import { CookieConsent } from "@/components/marketing/cookie-consent";
import { MarketingFooter, MarketingHeader } from "@/components/marketing/site-chrome";

export default function MarketingLayout({ children }: { children: ReactNode }) {
  return (
    <div className="mk relative min-h-screen overflow-x-clip">
      <a
        href="#content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2 focus:text-black"
      >
        Skip to content
      </a>
      <MarketingHeader />
      {/* Pages lay out their own sections; most wrap content in <Container>. */}
      <main id="content">{children}</main>
      <MarketingFooter />
      <CookieConsent />
    </div>
  );
}
