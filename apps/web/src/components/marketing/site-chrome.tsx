import Link from "next/link";
import type { ReactNode } from "react";
import { Sparkles } from "lucide-react";
import { MobileMenu } from "@/components/marketing/mobile-menu";
import { FOOTER_LINKS, MARKETING_NAV, SITE } from "@/lib/marketing";

export function Logo() {
  return (
    <Link href="/" className="flex items-center gap-2.5 text-[16px] font-bold tracking-tight text-white">
      <span className="mk-cta flex size-8 items-center justify-center rounded-lg" aria-hidden>
        <Sparkles className="size-4" />
      </span>
      {SITE.name}
    </Link>
  );
}

export function MarketingHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-[var(--mk-line)] bg-[#06071a]/70 backdrop-blur-xl">
      <div className="relative mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
        <Logo />
        <nav aria-label="Main" className="hidden md:block">
          <ul className="flex gap-1 text-[14px]">
            {MARKETING_NAV.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className="rounded-lg px-3 py-2 text-[var(--mk-muted)] transition-colors hover:bg-white/5 hover:text-white"
                >
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <div className="flex items-center gap-2 text-[14px]">
          <Link href="/login" className="hidden rounded-lg px-3 py-2 font-medium text-[var(--mk-muted)] hover:text-white sm:block">
            Sign in
          </Link>
          <Link href="/register" className="mk-cta hidden rounded-lg px-4 py-2 font-semibold sm:block">
            Start free
          </Link>
          <MobileMenu />
        </div>
      </div>
    </header>
  );
}

export function MarketingFooter() {
  return (
    <footer className="relative border-t border-[var(--mk-line)] bg-[#05061450]">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-14 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-[1.4fr_repeat(4,1fr)]">
        <div>
          <Logo />
          <p className="mt-3 max-w-xs text-[14px] leading-6 text-[var(--mk-muted)]">{SITE.tagline}</p>
          {SITE.statusUrl ? (
            <a href={SITE.statusUrl} className="mt-4 inline-flex items-center gap-2 text-[13px] text-[var(--mk-muted)] hover:text-white">
              <span className="mk-live-dot size-2 rounded-full bg-[var(--mk-green)]" aria-hidden />
              System status
            </a>
          ) : null}
        </div>
        {FOOTER_LINKS.map((group) => (
          <div key={group.heading}>
            <p className="text-[13px] font-semibold text-white">{group.heading}</p>
            <ul className="mt-3 space-y-2 text-[14px]">
              {group.links.map((link) => (
                <li key={link.href}>
                  <Link href={link.href} className="text-[var(--mk-muted)] transition-colors hover:text-white">
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <p className="border-t border-[var(--mk-line)] px-4 py-5 text-center text-[13px] text-[var(--mk-muted)]">
        © {new Date().getFullYear()} {SITE.legalEntity}. All rights reserved.
      </p>
    </footer>
  );
}

/** Heading block used at the top of inner marketing pages. */
export function PageIntro({ eyebrow, title, children }: { eyebrow?: string; title: string; children?: ReactNode }) {
  return (
    <div className="relative mx-auto max-w-3xl text-center">
      {eyebrow ? <Eyebrow>{eyebrow}</Eyebrow> : null}
      <h1 className="mk-gradient-text mt-4 text-[36px] font-bold leading-[1.1] tracking-tight sm:text-[52px]">{title}</h1>
      {children ? <div className="mt-5 text-[17px] leading-8 text-[var(--mk-muted)]">{children}</div> : null}
    </div>
  );
}

export function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <p className="inline-flex items-center gap-2 rounded-full border border-[var(--mk-line)] bg-white/5 px-3 py-1 text-[12px] font-semibold uppercase tracking-[0.12em] text-[#cfc7ff]">
      {children}
    </p>
  );
}

/** Section heading used on the landing page and inner pages. */
export function SectionHeading({
  eyebrow,
  title,
  children,
  align = "center",
}: {
  eyebrow?: string;
  title: string;
  children?: ReactNode;
  align?: "center" | "left";
}) {
  return (
    <div className={align === "center" ? "mx-auto max-w-2xl text-center" : "max-w-2xl"}>
      {eyebrow ? <Eyebrow>{eyebrow}</Eyebrow> : null}
      <h2 className="mt-4 text-[30px] font-bold leading-tight tracking-tight text-white sm:text-[40px]">{title}</h2>
      {children ? <p className="mt-4 text-[16px] leading-7 text-[var(--mk-muted)]">{children}</p> : null}
    </div>
  );
}
