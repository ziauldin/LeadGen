"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { BookOpen, HelpCircle, MessageSquarePlus, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Textarea } from "@/components/ui/textarea";
import { CHANGELOG } from "@/content/changelog";
import { track } from "@/lib/analytics";
import { apiFetch, getErrorMessage } from "@/lib/api/client";

const SEEN_KEY = "lg_changelog_seen";
const KINDS: [string, string][] = [
  ["idea", "Idea"],
  ["bug", "Something's broken"],
  ["question", "Question"],
  ["praise", "Something I like"],
];

function lastSeen(): string | null {
  try {
    return window.localStorage.getItem(SEEN_KEY);
  } catch {
    return null;
  }
}

/** How many changelog entries are newer than the last one this browser opened. */
export function unseenCount(seenId: string | null): number {
  if (!seenId) return Math.min(CHANGELOG.length, 3);
  const index = CHANGELOG.findIndex((entry) => entry.id === seenId);
  return index === -1 ? CHANGELOG.length : index;
}

function WhatsNewDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[80vh] overflow-y-auto sm:max-w-[560px]">
        <DialogHeader>
          <DialogTitle>What&apos;s new</DialogTitle>
          <DialogDescription>Recent improvements to LeadsGen.</DialogDescription>
        </DialogHeader>
        <ol className="space-y-5">
          {CHANGELOG.slice(0, 5).map((entry) => (
            <li key={entry.id}>
              <p className="text-[12px] text-[var(--on-surface-variant)]">
                {new Date(entry.date).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}
              </p>
              <p className="text-[14px] font-semibold">{entry.title}</p>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-[13px]">
                {entry.items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </li>
          ))}
        </ol>
        <DialogFooter>
          <Link href="/changelog" className="text-[13px] text-[var(--primary)] hover:underline">
            Full changelog
          </Link>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function FeedbackDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const pathname = usePathname();
  const [kind, setKind] = useState("idea");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSending(true);
    setError(null);
    try {
      await apiFetch("/feedback", { method: "POST", body: JSON.stringify({ kind, message: message.trim(), page: pathname }) });
      track("feedback_sent", { kind });
      toast.success("Thanks! Your feedback went straight to the team.");
      setMessage("");
      onOpenChange(false);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSending(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <form onSubmit={submit} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>Send feedback</DialogTitle>
            <DialogDescription>Tell us what&apos;s working, what isn&apos;t, or what you&apos;d like next.</DialogDescription>
          </DialogHeader>
          <fieldset className="flex flex-wrap gap-2">
            <legend className="sr-only">Type of feedback</legend>
            {KINDS.map(([value, label]) => (
              <label
                key={value}
                className={`cursor-pointer rounded-full border px-3 py-1 text-[13px] ${kind === value ? "border-[var(--primary)] bg-[var(--primary-fixed)] text-[var(--on-primary-fixed)]" : "border-[var(--outline-variant)]"}`}
              >
                <input type="radio" name="feedback-kind" value={value} checked={kind === value} onChange={() => setKind(value)} className="sr-only" />
                {label}
              </label>
            ))}
          </fieldset>
          <div className="grid gap-1.5">
            <label htmlFor="feedback-message" className="text-[13px] font-medium">
              Your feedback
            </label>
            <Textarea
              id="feedback-message"
              rows={5}
              required
              minLength={3}
              maxLength={5000}
              value={message}
              onChange={(event) => setMessage(event.target.value)}
            />
          </div>
          {error ? (
            <p role="alert" className="rounded-md bg-[var(--error-container)] px-3 py-2 text-[13px] text-[var(--on-error-container)]">
              {error}
            </p>
          ) : null}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={sending || message.trim().length < 3}>
              {sending ? "Sending…" : "Send"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function HelpMenu() {
  const [unseen, setUnseen] = useState(0);
  const [whatsNew, setWhatsNew] = useState(false);
  const [feedback, setFeedback] = useState(false);

  useEffect(() => setUnseen(unseenCount(lastSeen())), []);

  function openWhatsNew() {
    setWhatsNew(true);
    setUnseen(0);
    try {
      if (CHANGELOG[0]) window.localStorage.setItem(SEEN_KEY, CHANGELOG[0].id);
    } catch {
      // Storage unavailable: the badge just reappears next visit.
    }
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger
          className="relative flex size-9 items-center justify-center rounded-lg text-[var(--on-surface-variant)] hover:bg-[var(--surface-container-low)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)]"
          aria-label={unseen ? `Help and what's new (${unseen} new)` : "Help and what's new"}
        >
          <HelpCircle className="size-5" aria-hidden />
          {unseen ? (
            <span aria-hidden className="absolute right-1.5 top-1.5 size-2 rounded-full bg-[var(--error)]" />
          ) : null}
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuItem className="cursor-pointer gap-2 text-[13px]" onClick={openWhatsNew}>
            <Sparkles className="size-3.5" aria-hidden />
            What&apos;s new
            {unseen ? <span className="ml-auto rounded-full bg-[var(--error)] px-1.5 text-[11px] text-white">{unseen}</span> : null}
          </DropdownMenuItem>
          <DropdownMenuItem className="cursor-pointer gap-2 text-[13px]" render={<Link href="/help" target="_blank" />}>
            <BookOpen className="size-3.5" aria-hidden />
            Help center
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem className="cursor-pointer gap-2 text-[13px]" onClick={() => setFeedback(true)}>
            <MessageSquarePlus className="size-3.5" aria-hidden />
            Send feedback
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <WhatsNewDialog open={whatsNew} onOpenChange={setWhatsNew} />
      <FeedbackDialog open={feedback} onOpenChange={setFeedback} />
    </>
  );
}
