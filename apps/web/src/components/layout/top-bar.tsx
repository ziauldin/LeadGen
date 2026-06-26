"use client";

import { MobileNav } from "@/components/layout/mobile-nav";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";

export function TopBar() {
  const { user, logout } = useAuth();

  return (
    <header className="flex h-14 items-center justify-between border-b bg-card px-4 md:px-6">
      <MobileNav />
      <p className="text-sm font-medium md:hidden">LeadsGen</p>
      <div className="ml-auto flex items-center gap-3">
        {user ? (
          <>
            <span className="hidden text-sm text-muted-foreground sm:inline">{user.email}</span>
            <Button variant="outline" size="sm" onClick={logout}>
              Sign out
            </Button>
          </>
        ) : null}
      </div>
    </header>
  );
}
