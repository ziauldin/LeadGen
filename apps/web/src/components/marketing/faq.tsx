import { ChevronDown } from "lucide-react";

export type FaqItem = { question: string; answer: string };

/** Accessible accordion built on <details>, so it works without JavaScript. */
export function Faq({ items }: { items: FaqItem[] }) {
  return (
    <div className="mx-auto max-w-3xl divide-y divide-[var(--mk-line)] rounded-2xl border border-[var(--mk-line)] bg-white/[0.02]">
      {items.map((item) => (
        <details key={item.question} className="group px-5 py-1 sm:px-6">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-4 text-[16px] font-semibold text-white [&::-webkit-details-marker]:hidden">
            {item.question}
            <ChevronDown className="size-5 shrink-0 text-[var(--mk-muted)] transition-transform group-open:rotate-180" aria-hidden />
          </summary>
          <p className="pb-5 text-[15px] leading-7 text-[var(--mk-muted)]">{item.answer}</p>
        </details>
      ))}
    </div>
  );
}

export const COMMON_FAQ: FaqItem[] = [
  {
    question: "Can I use my own API keys?",
    answer:
      "Yes. Connect your own mailboxes or sending service, AI model, verification and email-finding keys. Usage on your own keys is paid to those providers directly and never counts against your plan. If you'd rather not manage keys, use ours: each plan includes credits, and you can top up any time.",
  },
  {
    question: "So what am I paying LeadsGen for?",
    answer:
      "The system that turns those services into booked meetings: sequences with human approval, sending windows, warm-up and mailbox rotation, bounce and reply handling, a shared inbox, deals, A/B tests, analytics, CRM sync and the compliance guardrails that keep your domain and your company out of trouble.",
  },
  {
    question: "What are credits?",
    answer:
      "Credits cover services we provide when you don't bring a key: one email verification or one email lookup is one credit, and 1,000 AI tokens is one credit. Every plan includes a monthly allowance; extra credit packs never expire.",
  },
  {
    question: "Is cold email legal?",
    answer:
      "B2B outreach is allowed in most places when you contact relevant people, say who you are, and let them opt out. LeadsGen records a lawful basis for every lead, adds one-click unsubscribe and your address to every email, and suppresses anyone who opts out, everywhere.",
  },
  {
    question: "Will it hurt my domain's reputation?",
    answer:
      "It's built not to. Sending windows, daily and per-domain limits, warm-up, verification before sending and automatic pausing when bounces or complaints rise all protect your sender reputation.",
  },
  {
    question: "Can I cancel any time?",
    answer: "Yes. Plans are monthly or yearly, you can change or cancel from the billing portal, and you can export all of your data whenever you like.",
  },
];
