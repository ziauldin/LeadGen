import type { ReactNode } from "react";

/** Inner marketing pages (features, help, blog, legal…): a centred column under a soft glow. */
export default function ContentLayout({ children }: { children: ReactNode }) {
  return (
    <div className="relative">
      <div className="mk-grid-bg h-[520px]" aria-hidden />
      <div className="mk-aurora opacity-60" aria-hidden />
      <div className="relative mx-auto max-w-6xl px-4 py-14 sm:py-20">{children}</div>
    </div>
  );
}
