import { AppSidebar } from "@/components/layout/app-sidebar";
import { TopBar } from "@/components/layout/top-bar";
import { VerifyEmailBanner } from "@/components/layout/verify-email-banner";
import { AuthGuard } from "@/components/auth/auth-guard";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <AppSidebar />
      <TopBar />
      <main className="min-h-screen bg-[var(--background)] pt-16 lg:ml-[260px]">
        <div className="mx-auto max-w-[1440px] p-4 sm:p-6 lg:p-8">
          <VerifyEmailBanner />
          {children}
        </div>
      </main>
    </AuthGuard>
  );
}
