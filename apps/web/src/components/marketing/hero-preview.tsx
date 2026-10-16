import { BarChart3, CheckCircle2, FlaskConical, Inbox, KanbanSquare, Megaphone, Sparkles, Users } from "lucide-react";

const CONVERSATIONS = [
  { name: "Maya Chen", company: "Northwind Foods", snippet: "Yes, Tuesday works. Send an invite?", label: "Interested", tone: "green", unread: true },
  { name: "Owen Hart", company: "Brightline Labs", snippet: "Can you share pricing for 20 seats?", label: "Interested", tone: "green", unread: true },
  { name: "Priya Nair", company: "Cobalt Logistics", snippet: "Back next week. Let's talk then.", label: "Not now", tone: "amber", unread: false },
  { name: "Leo Brandt", company: "Atlas Tooling", snippet: "Thanks, booked a slot for Friday.", label: "Meeting", tone: "violet", unread: false },
] as const;

const TONES = {
  green: "bg-emerald-400/15 text-emerald-300 ring-emerald-400/30",
  amber: "bg-amber-400/15 text-amber-200 ring-amber-400/30",
  violet: "bg-violet-400/15 text-violet-200 ring-violet-400/30",
} as const;

const NAV = [Inbox, Megaphone, Users, KanbanSquare, BarChart3];
const BARS = [38, 52, 46, 64, 58, 82, 74];

/**
 * A product illustration built in HTML so it stays crisp and light. Sample data only.
 * Decorative for assistive tech; the wrapper carries a short description.
 */
export function HeroPreview() {
  return (
    <div role="img" aria-label="Illustration of the LeadsGen inbox with sample replies, an A/B test result and weekly replies" className="relative mx-auto w-full max-w-5xl text-left">
      <div aria-hidden className="absolute -inset-x-10 -bottom-10 top-10 rounded-[40px] bg-[radial-gradient(60%_60%_at_50%_40%,rgba(91,75,255,0.45),transparent_70%)] blur-2xl" />
      <div aria-hidden className="mk-glow-frame relative overflow-hidden rounded-2xl border border-white/10 bg-[#0b0d26]/90 shadow-[0_40px_120px_-30px_rgba(0,0,0,0.8)] backdrop-blur">
        {/* window bar */}
        <div className="flex items-center gap-2 border-b border-white/10 px-4 py-3">
          <span className="size-3 rounded-full bg-[#ff5f57]" />
          <span className="size-3 rounded-full bg-[#febc2e]" />
          <span className="size-3 rounded-full bg-[#28c840]" />
          <span className="ml-3 rounded-md bg-white/5 px-3 py-1 text-[11px] text-white/50">app.leadsgen.io/inbox</span>
        </div>
        <div className="grid grid-cols-[52px_minmax(0,1fr)] md:grid-cols-[52px_minmax(0,1fr)_minmax(0,1.1fr)]">
          {/* sidebar */}
          <div className="flex flex-col items-center gap-4 border-r border-white/10 py-4">
            {NAV.map((Icon, index) => (
              <span key={index} className={`flex size-8 items-center justify-center rounded-lg ${index === 0 ? "bg-[#5b4bff] text-white" : "text-white/40"}`}>
                <Icon className="size-4" />
              </span>
            ))}
          </div>
          {/* conversation list */}
          <div className="border-r border-white/10 p-3">
            <div className="mb-3 flex items-center justify-between px-1">
              <span className="text-[13px] font-semibold text-white">Inbox</span>
              <span className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] text-white/70">2 new</span>
            </div>
            <ul className="space-y-1.5">
              {CONVERSATIONS.map((item, index) => (
                <li key={item.name} className={`rounded-xl p-2.5 ${index === 0 ? "bg-white/[0.07] ring-1 ring-white/10" : ""}`}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="flex min-w-0 items-center gap-2 truncate text-[12px] font-semibold text-white">
                      {item.unread ? <span className="size-1.5 rounded-full bg-[#8f7cff]" /> : <span className="size-1.5" />}
                      {item.name}
                    </span>
                    <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ring-1 ${TONES[item.tone]}`}>{item.label}</span>
                  </div>
                  <p className="mt-1 truncate pl-3.5 text-[11px] text-white/50">
                    {item.company} · {item.snippet}
                  </p>
                </li>
              ))}
            </ul>
          </div>
          {/* thread */}
          <div className="hidden p-4 md:block">
            <p className="text-[13px] font-semibold text-white">Maya Chen · Northwind Foods</p>
            <p className="text-[11px] text-white/45">Step 1 · Version B · sent from sam@acme.co</p>
            <div className="mt-4 space-y-3">
              <div className="max-w-[85%] rounded-2xl rounded-tl-sm bg-white/[0.06] p-3 text-[12px] leading-5 text-white/75">
                Hi Maya, noticed Northwind is hiring QA leads. Teams like yours cut audit prep by a third with…
              </div>
              <div className="ml-auto max-w-[85%] rounded-2xl rounded-tr-sm bg-[#5b4bff]/25 p-3 text-[12px] leading-5 text-white ring-1 ring-[#8f7cff]/30">
                Yes, Tuesday works. Send an invite?
              </div>
            </div>
            <div className="mt-4 rounded-xl border border-white/10 bg-white/[0.03] p-3">
              <p className="flex items-center gap-1.5 text-[11px] font-medium text-[#cfc7ff]">
                <Sparkles className="size-3.5" /> Suggested reply
              </p>
              <p className="mt-1 text-[12px] leading-5 text-white/70">Great, sending an invite for Tuesday 10:00. Looking forward to it!</p>
              <div className="mt-2 flex gap-2">
                <span className="rounded-md bg-[#5b4bff] px-2.5 py-1 text-[11px] font-semibold text-white">Send</span>
                <span className="rounded-md bg-white/10 px-2.5 py-1 text-[11px] text-white/70">Edit</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* floating cards */}
      <div aria-hidden className="mk-float absolute -left-28 top-32 hidden w-56 rounded-2xl border border-white/10 bg-[#11143a]/90 p-4 shadow-2xl backdrop-blur xl:block">
        <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-[#a9e9ff]">
          <FlaskConical className="size-3.5" /> A/B test
        </p>
        <div className="mt-3 space-y-2 text-[12px]">
          <div className="flex items-center justify-between text-white/60">
            <span>Version A</span>
            <span>4.1% replies</span>
          </div>
          <div className="h-1.5 rounded-full bg-white/10">
            <div className="h-1.5 w-[42%] rounded-full bg-white/40" />
          </div>
          <div className="flex items-center justify-between font-semibold text-white">
            <span>Version B</span>
            <span>7.9% replies</span>
          </div>
          <div className="h-1.5 rounded-full bg-white/10">
            <div className="h-1.5 w-[79%] rounded-full bg-gradient-to-r from-[#5b4bff] to-[#3ddcf5]" />
          </div>
        </div>
        <p className="mt-3 flex items-center gap-1.5 text-[11px] text-emerald-300">
          <CheckCircle2 className="size-3.5" /> Clear winner
        </p>
      </div>

      <div aria-hidden className="mk-float-slow absolute -right-28 bottom-16 hidden w-60 rounded-2xl border border-white/10 bg-[#11143a]/90 p-4 shadow-2xl backdrop-blur xl:block">
        <div className="flex items-center justify-between">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-[#ffc2e3]">Replies this week</p>
          <span className="mk-live-dot size-2 rounded-full bg-emerald-400" />
        </div>
        <div className="mt-3 flex h-16 items-end gap-1.5">
          {BARS.map((height, index) => (
            <span
              key={index}
              className="w-full rounded-t bg-gradient-to-t from-[#5b4bff] to-[#f472b6]"
              style={{ height: `${Math.round(height * 0.64)}px` }}
            />
          ))}
        </div>
        <p className="mt-2 text-[11px] text-white/55">New deal opened from an interested reply</p>
      </div>
    </div>
  );
}
