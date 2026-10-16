import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRight,
  BarChart3,
  Check,
  CheckCircle2,
  FileSearch,
  FlaskConical,
  Gauge,
  Inbox,
  KanbanSquare,
  Lock,
  MailCheck,
  Minus,
  PenLine,
  Plug,
  ShieldCheck,
  Sparkles,
  UserCheck,
  type LucideIcon,
} from "lucide-react";
import { COMMON_FAQ, Faq } from "@/components/marketing/faq";
import { HeroPreview } from "@/components/marketing/hero-preview";
import { RoiCalculator } from "@/components/marketing/roi-calculator";
import { Eyebrow, SectionHeading } from "@/components/marketing/site-chrome";
import { SITE } from "@/lib/marketing";

export const metadata: Metadata = {
  title: `${SITE.name}: ${SITE.tagline}`,
  description: SITE.description,
  alternates: { canonical: "/" },
};

const WORKS_WITH = ["Gmail", "Microsoft 365", "HubSpot", "Pipedrive", "ZeroBounce", "NeverBounce", "Resend", "SendGrid", "Mailgun", "Zapier"];

const PROOF: { value: string; label: string }[] = [
  { value: "100%", label: "of emails approved by a person before they send" },
  { value: "4-way", label: "A/B tests on any step, with a significance check" },
  { value: "1-click", label: "unsubscribe (RFC 8058) and suppression everywhere" },
  { value: "15 min", label: "deal status sync with HubSpot and Pipedrive" },
];

const STEPS: { icon: LucideIcon; title: string; text: string; points: string[] }[] = [
  {
    icon: FileSearch,
    title: "Build a list you can stand behind",
    text: "Search public listings for your niche, import a CSV or push leads by API. Every lead keeps its source and lawful basis, and addresses are verified before anything is sent.",
    points: ["Niche search and enrichment", "Email verification", "Lawful basis on every lead"],
  },
  {
    icon: PenLine,
    title: "Write emails that sound like you",
    text: "Start from proven templates or let AI draft from what you know about each lead, with guardrails against made-up facts. Test subject lines and openers with A/B versions.",
    points: ["AI drafts with guardrails", "Multi-step sequences", "A/B tests per step"],
  },
  {
    icon: MailCheck,
    title: "Send safely from your own mailboxes",
    text: "Connect Gmail or Microsoft 365 and rotate across mailboxes. Sending windows, warm-up and daily limits protect your domain, and a person approves every email.",
    points: ["Mailbox rotation", "Warm-up and limits", "Auto-pause on bounce spikes"],
  },
  {
    icon: Inbox,
    title: "Turn replies into revenue",
    text: "Every reply lands in one inbox, labelled and matched to its lead. Interested replies open a deal automatically, and won deals sync with your CRM.",
    points: ["Unified inbox", "Deals from replies", "HubSpot and Pipedrive sync"],
  },
];

const BENTO: { icon: LucideIcon; title: string; text: string; className: string; accent: string }[] = [
  {
    icon: Inbox,
    title: "One inbox for every mailbox",
    text: "Assign, snooze, label and answer from the original sender. Keyboard-first, with an optional AI-suggested reply you can edit before it sends.",
    className: "md:col-span-2",
    accent: "from-[#5b4bff]/30",
  },
  {
    icon: FlaskConical,
    title: "A/B tests that call a winner",
    text: "Up to four versions per step, split evenly, with a winner suggested only when the numbers are significant.",
    className: "",
    accent: "from-[#3ddcf5]/25",
  },
  {
    icon: Gauge,
    title: "Deliverability guardrails",
    text: "SPF, DKIM and DMARC checks, warm-up, per-domain limits and automatic pausing keep you out of spam.",
    className: "",
    accent: "from-[#4ade80]/20",
  },
  {
    icon: KanbanSquare,
    title: "A pipeline built from replies",
    text: "Interested replies open deals, tasks keep follow-ups on time and every lead has a full activity timeline.",
    className: "",
    accent: "from-[#f472b6]/25",
  },
  {
    icon: BarChart3,
    title: "Analytics you'll actually read",
    text: "Daily replies, positive rate and bounces by campaign, step, version, mailbox and template, plus a Monday summary in your inbox.",
    className: "md:col-span-2",
    accent: "from-[#8f7cff]/30",
  },
];

const COMPARISON: { feature: string; us: boolean; diy: boolean | "partial" }[] = [
  { feature: "Human approval before every email", us: true, diy: false },
  { feature: "Mailbox rotation, warm-up and limits", us: true, diy: "partial" },
  { feature: "Verification before sending", us: true, diy: "partial" },
  { feature: "Suppression and one-click unsubscribe everywhere", us: true, diy: false },
  { feature: "Unified inbox with reply labelling", us: true, diy: false },
  { feature: "A/B tests with a significance check", us: true, diy: false },
  { feature: "Deals from replies and CRM sync", us: true, diy: "partial" },
  { feature: "GDPR exports, erasure and audit log", us: true, diy: false },
];

const TRUST: { icon: LucideIcon; text: string }[] = [
  { icon: ShieldCheck, text: "GDPR, PECR and CAN-SPAM rules built into every step" },
  { icon: UserCheck, text: "Export or erase a person's data in minutes" },
  { icon: Lock, text: "Two-factor sign-in, SSO and SAML on Enterprise" },
  { icon: CheckCircle2, text: "Row-level tenant isolation and a full audit log" },
];

function Section({ children, className = "", id }: { children: React.ReactNode; className?: string; id?: string }) {
  return (
    <section id={id} className={`relative mx-auto max-w-6xl px-4 py-20 sm:py-28 ${className}`}>
      {children}
    </section>
  );
}

export default function HomePage() {
  return (
    <>
      {/* ── Hero ───────────────────────────────────────────────── */}
      <div className="relative overflow-hidden">
        <div className="mk-grid-bg" aria-hidden />
        <div className="mk-aurora" aria-hidden />
        <div className="relative mx-auto max-w-6xl px-4 pb-10 pt-16 text-center sm:pt-24">
          <Link
            href="/changelog"
            className="mk-fade-up inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 py-1 pl-1 pr-3 text-[13px] text-[var(--mk-muted)] hover:border-white/30 hover:text-white"
          >
            <span className="mk-cta rounded-full px-2 py-0.5 text-[11px] font-semibold">New</span>
            A/B tests, analytics and HubSpot sync
            <ArrowRight className="size-3.5" aria-hidden />
          </Link>
          <h1 className="mk-fade-up mk-delay-1 mx-auto mt-6 max-w-4xl text-[42px] font-bold leading-[1.05] tracking-tight text-white sm:text-[64px] lg:text-[76px]">
            Book more meetings.{" "}
            <span className="mk-gradient-text">Keep your domain clean.</span>
          </h1>
          <p className="mk-fade-up mk-delay-2 mx-auto mt-6 max-w-2xl text-[17px] leading-8 text-[var(--mk-muted)] sm:text-[19px]">
            {SITE.name} finds the right businesses, writes personal emails with AI and a human in the loop, sends from your own
            mailboxes and turns every reply into pipeline. Compliance built in, not bolted on.
          </p>
          <div className="mk-fade-up mk-delay-3 mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link href="/register" className="mk-cta inline-flex w-full items-center justify-center gap-2 rounded-xl px-7 py-3.5 text-[16px] font-semibold sm:w-auto">
              Start free, no card needed
              <ArrowRight className="size-4" aria-hidden />
            </Link>
            <Link href="#how-it-works" className="mk-ghost inline-flex w-full items-center justify-center rounded-xl px-7 py-3.5 text-[16px] font-semibold sm:w-auto">
              See how it works
            </Link>
          </div>
          <ul className="mt-6 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-[13px] text-[var(--mk-muted)]">
            {["Free plan forever", "Bring your own keys", "Cancel any time"].map((item) => (
              <li key={item} className="flex items-center gap-1.5">
                <Check className="size-4 text-[var(--mk-green)]" aria-hidden />
                {item}
              </li>
            ))}
          </ul>
          <div className="mk-fade-up mk-delay-3 mt-16 sm:mt-20">
            <HeroPreview />
          </div>
        </div>
      </div>

      {/* ── Works with ─────────────────────────────────────────── */}
      <div className="border-y border-[var(--mk-line)] bg-white/[0.015]">
        <div className="mx-auto max-w-6xl px-4 py-8">
          <p className="text-center text-[12px] font-semibold uppercase tracking-[0.18em] text-[var(--mk-muted)]">
            Works with the tools you already use
          </p>
          <ul className="mt-5 flex flex-wrap items-center justify-center gap-x-8 gap-y-3">
            {WORKS_WITH.map((name) => (
              <li key={name} className="text-[16px] font-semibold tracking-tight text-white/70">
                {name}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* ── Proof points ───────────────────────────────────────── */}
      <Section className="!py-16">
        <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {PROOF.map((item) => (
            <div key={item.label} className="mk-card p-6">
              <dt className="sr-only">{item.label}</dt>
              <dd>
                <span className="mk-gradient-text block text-[38px] font-bold leading-none">{item.value}</span>
                <span className="mt-3 block text-[14px] leading-6 text-[var(--mk-muted)]">{item.label}</span>
              </dd>
            </div>
          ))}
        </dl>
      </Section>

      {/* ── How it works ───────────────────────────────────────── */}
      <Section id="how-it-works" className="scroll-mt-20">
        <SectionHeading eyebrow="How it works" title="From cold list to booked meeting in four steps">
          Everything a sales team needs between “who should we email?” and “see you on Tuesday”.
        </SectionHeading>
        <ol className="mt-16 grid gap-6 md:grid-cols-2">
          {STEPS.map((step, index) => (
            <li key={step.title} className="mk-card mk-card-hover relative overflow-hidden p-7">
              <span aria-hidden className="absolute -right-4 -top-6 text-[120px] font-black leading-none text-white/[0.04]">
                {index + 1}
              </span>
              <span className="mk-cta flex size-11 items-center justify-center rounded-xl" aria-hidden>
                <step.icon className="size-5" />
              </span>
              <h3 className="mt-5 text-[20px] font-semibold text-white">
                <span className="sr-only">Step {index + 1}: </span>
                {step.title}
              </h3>
              <p className="mt-3 text-[15px] leading-7 text-[var(--mk-muted)]">{step.text}</p>
              <ul className="mt-5 flex flex-wrap gap-2">
                {step.points.map((point) => (
                  <li key={point} className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[12px] text-[#d9d4ff]">
                    {point}
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ol>
      </Section>

      {/* ── Feature bento ─────────────────────────────────────── */}
      <Section>
        <SectionHeading eyebrow="Product" title="Everything after “send”, handled">
          The inbox, pipeline and analytics live next to your campaigns, so nothing falls between tools.
        </SectionHeading>
        <div className="mt-16 grid gap-5 md:grid-cols-3">
          {BENTO.map((tile) => (
            <article key={tile.title} className={`mk-card mk-card-hover relative overflow-hidden p-7 ${tile.className}`}>
              <div aria-hidden className={`absolute inset-x-0 top-0 h-32 bg-gradient-to-b ${tile.accent} to-transparent`} />
              <tile.icon className="relative size-7 text-white" aria-hidden />
              <h3 className="relative mt-5 text-[19px] font-semibold text-white">{tile.title}</h3>
              <p className="relative mt-2 text-[15px] leading-7 text-[var(--mk-muted)]">{tile.text}</p>
            </article>
          ))}
        </div>
        <p className="mt-8 text-center">
          <Link href="/features" className="inline-flex items-center gap-1.5 text-[15px] font-semibold text-[#cfc7ff] hover:text-white">
            Explore every feature <ArrowRight className="size-4" aria-hidden />
          </Link>
        </p>
      </Section>

      {/* ── ROI calculator ────────────────────────────────────── */}
      <Section>
        <SectionHeading eyebrow="Estimate" title="What could outbound be worth to you?">
          Move the sliders to match your market. The maths is simple, and doing it consistently is what LeadsGen is for.
        </SectionHeading>
        <div className="mt-14">
          <RoiCalculator />
        </div>
      </Section>

      {/* ── Comparison ────────────────────────────────────────── */}
      <Section>
        <SectionHeading eyebrow="Why LeadsGen" title="One system instead of five tabs">
          Compared with stitching together a spreadsheet, a bulk sender, a verifier and a CRM.
        </SectionHeading>
        <div className="mk-card mt-14 overflow-x-auto" tabIndex={0} role="region" aria-label="Comparison table">
          <table className="w-full min-w-[560px] text-left text-[15px]">
            <caption className="sr-only">LeadsGen compared with a do-it-yourself tool stack</caption>
            <thead>
              <tr className="border-b border-[var(--mk-line)] text-[13px] uppercase tracking-wider text-[var(--mk-muted)]">
                <th scope="col" className="px-6 py-4 font-semibold">Capability</th>
                <th scope="col" className="px-6 py-4 text-center font-semibold text-white">{SITE.name}</th>
                <th scope="col" className="px-6 py-4 text-center font-semibold">DIY stack</th>
              </tr>
            </thead>
            <tbody>
              {COMPARISON.map((row) => (
                <tr key={row.feature} className="border-b border-[var(--mk-line)] last:border-0">
                  <th scope="row" className="px-6 py-4 font-medium text-white">{row.feature}</th>
                  <td className="px-6 py-4 text-center">
                    <CheckCircle2 className="mx-auto size-5 text-[var(--mk-green)]" aria-label="Included" />
                  </td>
                  <td className="px-6 py-4 text-center text-[var(--mk-muted)]">
                    {row.diy === "partial" ? (
                      <span className="text-[13px]">With extra tools</span>
                    ) : (
                      <Minus className="mx-auto size-5" aria-label="Not included" />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {/* ── Trust ─────────────────────────────────────────────── */}
      <Section>
        <div className="mk-card relative grid gap-10 overflow-hidden p-8 sm:p-12 lg:grid-cols-2">
          <div aria-hidden className="absolute -left-20 -top-20 size-72 rounded-full bg-[#4ade80]/10 blur-3xl" />
          <div className="relative">
            <Eyebrow>Trust</Eyebrow>
            <h2 className="mt-4 text-[30px] font-bold leading-tight tracking-tight text-white sm:text-[38px]">
              Compliance is the default, not an add-on
            </h2>
            <p className="mt-4 text-[16px] leading-7 text-[var(--mk-muted)]">
              Outreach only works long term when recipients are treated fairly. LeadsGen makes the right thing the easy thing, and
              gives your security team the controls they ask for.
            </p>
            <Link href="/subprocessors" className="mt-6 inline-flex items-center gap-1.5 text-[15px] font-semibold text-[#cfc7ff] hover:text-white">
              Security and subprocessors <ArrowRight className="size-4" aria-hidden />
            </Link>
          </div>
          <ul className="relative grid gap-4 sm:grid-cols-2">
            {TRUST.map((item) => (
              <li key={item.text} className="rounded-xl border border-white/10 bg-white/[0.03] p-5">
                <item.icon className="size-6 text-[var(--mk-green)]" aria-hidden />
                <p className="mt-3 text-[15px] leading-6 text-white">{item.text}</p>
              </li>
            ))}
          </ul>
        </div>
      </Section>

      {/* ── Integrations teaser ───────────────────────────────── */}
      <Section className="!pt-0">
        <div className="grid items-center gap-8 md:grid-cols-[auto_1fr_auto]">
          <span className="mk-cta flex size-14 items-center justify-center rounded-2xl" aria-hidden>
            <Plug className="size-6" />
          </span>
          <div>
            <h2 className="text-[22px] font-semibold text-white">Bring your own keys, or use ours</h2>
            <p className="mt-1 text-[15px] leading-7 text-[var(--mk-muted)]">
              Connect your mailboxes, AI model and data providers and pay them directly, or use LeadsGen credits and skip the setup.
            </p>
          </div>
          <Link href="/pricing" className="mk-ghost rounded-xl px-5 py-3 text-center text-[15px] font-semibold">
            How pricing works
          </Link>
        </div>
      </Section>

      {/* ── FAQ ───────────────────────────────────────────────── */}
      <Section>
        <SectionHeading eyebrow="FAQ" title="Questions, answered" />
        <div className="mt-12">
          <Faq items={COMMON_FAQ} />
        </div>
      </Section>

      {/* ── Final CTA ─────────────────────────────────────────── */}
      <Section className="!pt-0">
        <div className="relative overflow-hidden rounded-3xl p-10 text-center sm:p-16">
          <div aria-hidden className="absolute inset-0 bg-gradient-to-br from-[#3b2bd6] via-[#6b2fd0] to-[#b2369f]" />
          <div aria-hidden className="mk-grid-bg opacity-40" />
          <div className="relative">
            <Sparkles className="mx-auto size-8 text-white" aria-hidden />
            <h2 className="mx-auto mt-4 max-w-2xl text-[32px] font-bold leading-tight tracking-tight text-white sm:text-[46px]">
              Your next customers are a few good emails away.
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-[17px] leading-8 text-white/85">
              Start on the free plan in two minutes. Upgrade when it&apos;s working for you.
            </p>
            <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <Link href="/register" className="inline-flex items-center gap-2 rounded-xl bg-white px-7 py-3.5 text-[16px] font-semibold text-[#2a1d8f] shadow-lg transition hover:bg-white/90">
                Create your workspace <ArrowRight className="size-4" aria-hidden />
              </Link>
              <Link href="/contact" className="rounded-xl border border-white/40 px-7 py-3.5 text-[16px] font-semibold text-white hover:bg-white/10">
                Talk to us
              </Link>
            </div>
          </div>
        </div>
      </Section>
    </>
  );
}
