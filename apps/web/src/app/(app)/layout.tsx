import { AppSidebar } from "@/components/layout/app-sidebar";
import { TopBar } from "@/components/layout/top-bar";
import { BillingBanner } from "@/components/layout/billing-banner";
import { ImpersonationBanner } from "@/components/layout/impersonation-banner";
import { VerifyEmailBanner } from "@/components/layout/verify-email-banner";
import { AuthGuard } from "@/components/auth/auth-guard";
import { CookieConsent } from "@/components/marketing/cookie-consent";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <AppSidebar />
      <TopBar />
      <main className="min-h-screen bg-[var(--background)] pt-16 lg:ml-[260px]">
        <div className="mx-auto max-w-[1440px] p-4 sm:p-6 lg:p-8">
          <ImpersonationBanner />
          <BillingBanner />
          <VerifyEmailBanner />
          {children}
        </div>
      </main>
      <CookieConsent />
    </AuthGuard>
  );
}
