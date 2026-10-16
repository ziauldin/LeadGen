import Link from "next/link";
import { Database } from "lucide-react";
import { FOOTER_LINKS, MARKETING_NAV, SITE } from "@/lib/marketing";

export function MarketingHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-[var(--outline-variant)] bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
        <Link href="/" className="flex items-center gap-2 text-[15px] font-bold text-[var(--primary)]">
          <span className="flex size-7 items-center justify-center rounded bg-[var(--primary)] text-white">
            <Database className="size-4" aria-hidden />
          </span>
          {SITE.name}
        </Link>
        <nav aria-label="Main" className="hidden md:block">
          <ul className="flex gap-6 text-[14px]">
            {MARKETING_NAV.map((item) => (
              <li key={item.href}>
                <Link href={item.href} className="text-[var(--on-surface-variant)] hover:text-[var(--on-surface)]">
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <div className="flex items-center gap-2 text-[14px]">
          <Link href="/login" className="px-3 py-1.5 font-medium text-[var(--on-surface)] hover:text-[var(--primary)]">
            Sign in
          </Link>
          <Link
            href="/register"
            className="rounded-lg bg-[var(--primary)] px-3 py-1.5 font-medium text-white hover:opacity-90"
          >
            Start free
          </Link>
        </div>
      </div>
      <nav aria-label="Main (mobile)" className="border-t border-[var(--outline-variant)] md:hidden">
        <ul className="mx-auto flex max-w-6xl justify-between gap-2 overflow-x-auto px-4 py-2 text-[13px]">
          {MARKETING_NAV.map((item) => (
            <li key={item.href}>
              <Link href={item.href} className="text-[var(--on-surface-variant)]">
                {item.label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </header>
  );
}

export function MarketingFooter() {
  return (
    <footer className="mt-20 border-t border-[var(--outline-variant)] bg-white">
      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-10 sm:grid-cols-2 md:grid-cols-4">
        <div>
          <p className="text-[15px] font-bold text-[var(--primary)]">{SITE.name}</p>
          <p className="mt-2 text-[13px] text-[var(--on-surface-variant)]">{SITE.tagline}</p>
          {SITE.statusUrl ? (
            <a href={SITE.statusUrl} className="mt-3 inline-block text-[13px] text-[var(--on-surface-variant)] underline">
              System status
            </a>
          ) : null}
        </div>
        {FOOTER_LINKS.map((group) => (
          <div key={group.heading}>
            <p className="text-[13px] font-semibold">{group.heading}</p>
            <ul className="mt-2 space-y-1.5 text-[13px]">
              {group.links.map((link) => (
                <li key={link.href}>
                  <Link href={link.href} className="text-[var(--on-surface-variant)] hover:text-[var(--on-surface)]">
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <p className="border-t border-[var(--outline-variant)] px-4 py-4 text-center text-[12px] text-[var(--on-surface-variant)]">
        © {new Date().getFullYear()} {SITE.legalEntity}. All rights reserved.
      </p>
    </footer>
  );
}

export function PageIntro({ eyebrow, title, children }: { eyebrow?: string; title: string; children?: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-3xl text-center">
      {eyebrow ? <p className="text-[13px] font-semibold uppercase tracking-wide text-[var(--primary)]">{eyebrow}</p> : null}
      <h1 className="mt-2 text-[32px] font-bold leading-tight tracking-tight sm:text-[40px]">{title}</h1>
      {children ? <div className="mt-4 text-[16px] leading-7 text-[var(--on-surface-variant)]">{children}</div> : null}
    </div>
  );
}
