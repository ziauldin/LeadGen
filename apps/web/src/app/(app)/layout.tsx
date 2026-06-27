import { AppSidebar } from "@/components/layout/app-sidebar";
import { TopBar } from "@/components/layout/top-bar";
import { AuthGuard } from "@/components/auth/auth-guard";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      {/* Fixed sidebar */}
      <AppSidebar />
      {/* Fixed topbar (offset by sidebar width) */}
      <TopBar />
      {/* Main content: offset from fixed sidebar + topbar */}
      <main
        className="ml-[260px] pt-16 min-h-screen"
        style={{ background: "var(--background)" }}
      >
        <div className="p-8 max-w-[1440px] mx-auto">
          {children}
        </div>
      </main>
    </AuthGuard>
  );
}
