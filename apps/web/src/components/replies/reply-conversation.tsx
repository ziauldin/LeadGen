"use client";

import { useId, useState } from "react";
import { ChevronDown, ChevronUp, CornerDownRight, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { formatDateTime } from "@/components/replies/format";
import type { ReplyDetail } from "@/lib/api/types";

type SentMessage = ReplyDetail["thread"][number];

function SentEmail({ message, senderLabel }: { message: SentMessage; senderLabel: string }) {
  const [expanded, setExpanded] = useState(false);
  const bodyId = useId();
  const long = message.body.length > 600;
  return (
    <article
      className="rounded-lg border border-[var(--outline-variant)] bg-[var(--surface-container-low)] p-4"
      aria-label={`Sent email${message.step_number ? `, step ${message.step_number}` : ""}`}
    >
      <header className="mb-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] text-[var(--on-surface-variant)]">
        <Send className="size-3.5 text-[var(--primary)]" aria-hidden />
        <span className="font-semibold text-[var(--on-surface)]">{senderLabel}</span>
        {message.step_number ? (
          <span className="rounded bg-white px-1.5 py-0.5 text-[11px] font-medium ring-1 ring-[var(--outline-variant)]">
            Step {message.step_number}
          </span>
        ) : null}
        <span className="sm:ml-auto">
          {message.sent_at ? `Sent ${formatDateTime(message.sent_at)}` : "Not sent"}
        </span>
      </header>
      <h3 className="mb-2 text-[14px] font-semibold text-[var(--on-surface)]">{message.subject}</h3>
      <div
        id={bodyId}
        className={
          long && !expanded
            ? "relative max-h-40 overflow-hidden whitespace-pre-wrap break-words text-[13px] leading-[20px] text-[var(--on-surface-variant)]"
            : "whitespace-pre-wrap break-words text-[13px] leading-[20px] text-[var(--on-surface-variant)]"
        }
      >
        {message.body}
        {long && !expanded ? (
          <div className="pointer-events-none absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-[var(--surface-container-low)]" />
        ) : null}
      </div>
      {long ? (
        <Button
          variant="link"
          size="sm"
          className="mt-1 h-auto px-0"
          aria-expanded={expanded}
          aria-controls={bodyId}
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? "Show less" : "Show full email"}
        </Button>
      ) : null}
    </article>
  );
}

export function ReplyConversation({ reply }: { reply: ReplyDetail }) {
  const [showRaw, setShowRaw] = useState(false);
  const rawId = useId();
  const hasRaw = Boolean(reply.raw_body && reply.raw_body.trim() !== reply.body.trim());

  return (
    <section aria-labelledby="conversation-heading" className="space-y-3">
      <h2 id="conversation-heading" className="text-[15px] font-semibold text-[var(--on-surface)]">
        Conversation
      </h2>

      {reply.thread.length > 0 ? (
        <ol className="space-y-3">
          {reply.thread.map((message) => (
            <li key={message.id}>
              <SentEmail message={message} senderLabel="You" />
            </li>
          ))}
        </ol>
      ) : (
        <p className="rounded-lg border border-dashed border-[var(--outline-variant)] p-4 text-[13px] text-[var(--on-surface-variant)]">
          {reply.email_message_id
            ? "The sent email for this reply isn't available."
            : "This reply isn't linked to one of your sent emails yet, so there's no conversation to show."}
        </p>
      )}

      <article
        className="rounded-lg border-2 border-[var(--primary)]/30 bg-white p-4 shadow-sm"
        aria-label={`Reply from ${reply.from_email}`}
      >
        <header className="mb-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] text-[var(--on-surface-variant)]">
          <CornerDownRight className="size-3.5 text-[var(--secondary)]" aria-hidden />
          <span className="font-semibold text-[var(--on-surface)]">
            {reply.lead_name ? `${reply.lead_name} <${reply.from_email}>` : reply.from_email}
          </span>
          {reply.is_auto_reply ? (
            <span className="rounded bg-[var(--surface-container)] px-1.5 py-0.5 text-[11px] font-medium">
              Automatic reply
            </span>
          ) : null}
          <span className="sm:ml-auto">Received {formatDateTime(reply.received_at)}</span>
        </header>
        <h3 className="mb-2 text-[14px] font-semibold text-[var(--on-surface)]">
          {reply.subject || "(no subject)"}
        </h3>
        <div className="whitespace-pre-wrap break-words text-[14px] leading-[22px] text-[var(--on-surface)]">
          {reply.body.trim() || (
            <span className="italic text-[var(--on-surface-variant)]">
              No new text. The sender may have only quoted the earlier email.
            </span>
          )}
        </div>

        {hasRaw ? (
          <div className="mt-4 border-t border-[var(--outline-variant)] pt-3">
            <Button
              variant="ghost"
              size="sm"
              aria-expanded={showRaw}
              aria-controls={rawId}
              onClick={() => setShowRaw((value) => !value)}
            >
              {showRaw ? <ChevronUp aria-hidden /> : <ChevronDown aria-hidden />}
              {showRaw ? "Hide full original" : "Show full original"}
            </Button>
            {showRaw ? (
              <pre
                id={rawId}
                className="mt-2 max-h-[420px] overflow-auto whitespace-pre-wrap break-words rounded-md bg-[var(--surface-container-low)] p-3 font-mono text-[12px] leading-[18px] text-[var(--on-surface-variant)]"
              >
                {reply.raw_body}
              </pre>
            ) : null}
          </div>
        ) : null}
      </article>
    </section>
  );
}
