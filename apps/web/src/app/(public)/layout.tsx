import Link from "next/link";
import type { ReactNode } from "react";

export default function PublicLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-[var(--background)] text-[var(--on-surface)]">
      <header className="border-b border-[var(--outline-variant)] bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <Link href="/" className="text-[15px] font-semibold">
            LeadsGen
          </Link>
          <Link href="/login" className="text-[13px] font-medium text-[var(--primary)]">
            Sign in
          </Link>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-10">{children}</main>
    </div>
  );
}
