"use client";

import { useState } from "react";
import { Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Brand, NewCampaignButton } from "@/components/layout/app-sidebar";
import { NavLinks } from "@/components/layout/nav-links";

/** Below the lg breakpoint the sidebar becomes this slide-out sheet. */
export function MobileNav() {
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger
        render={<Button variant="outline" size="icon-sm" className="lg:hidden" />}
        aria-label="Open navigation"
      >
        <Menu className="size-4" aria-hidden />
      </SheetTrigger>
      <SheetContent side="left" className="flex w-72 flex-col gap-0 p-0">
        <SheetHeader className="px-6 pb-4 pt-6">
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          <Brand />
        </SheetHeader>
        <div className="mb-4 px-4">
          <NewCampaignButton onNavigate={close} />
        </div>
        <NavLinks onNavigate={close} />
      </SheetContent>
    </Sheet>
  );
}
