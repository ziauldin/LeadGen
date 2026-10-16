import type { Metadata } from "next";
import type { ReactNode } from "react";
import { AdminShell } from "@/components/admin/admin-shell";
import { AuthGuard } from "@/components/auth/auth-guard";

export const metadata: Metadata = { title: "Admin · LeadsGen", robots: { index: false } };

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGuard>
      <AdminShell>{children}</AdminShell>
    </AuthGuard>
  );
}
