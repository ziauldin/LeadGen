"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { Menu, X } from "lucide-react";
import { MARKETING_NAV } from "@/lib/marketing";

/** Small-screen navigation: a menu button that opens a full-width panel. */
export function MobileMenu() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const panelId = useId();
  const buttonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => setOpen(false), [pathname]);
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        buttonRef.current?.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <div className="md:hidden">
      <button
        ref={buttonRef}
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
        className="mk-ghost flex size-10 items-center justify-center rounded-lg"
      >
        {open ? <X className="size-5" aria-hidden /> : <Menu className="size-5" aria-hidden />}
        <span className="sr-only">{open ? "Close menu" : "Open menu"}</span>
      </button>
      {open ? (
        <nav
          id={panelId}
          aria-label="Main (mobile)"
          className="absolute inset-x-0 top-full border-b border-[var(--mk-line)] bg-[#080a20]/95 px-4 pb-6 pt-2 backdrop-blur-xl"
        >
          <ul className="space-y-1">
            {MARKETING_NAV.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className="block rounded-lg px-3 py-3 text-[16px] font-medium text-[var(--mk-text)] hover:bg-white/5"
                >
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <Link href="/login" className="mk-ghost rounded-xl px-4 py-3 text-center text-[15px] font-semibold">
              Sign in
            </Link>
            <Link href="/register" className="mk-cta rounded-xl px-4 py-3 text-center text-[15px] font-semibold">
              Start free
            </Link>
          </div>
        </nav>
      ) : null}
    </div>
  );
}
