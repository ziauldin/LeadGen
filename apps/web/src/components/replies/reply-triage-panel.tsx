"use client";

import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { CalendarCheck, Link2, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import {
  AiLabelMarker,
  CLASSIFICATION_ORDER,
  CLASSIFICATION_STYLES,
} from "@/components/replies/reply-classification-badge";
import { MATCH_METHODS } from "@/components/replies/format";
import { repliesApi } from "@/lib/api/endpoints";
import type { ReplyClassification, ReplyDetail } from "@/lib/api/types";

const CLASSIFICATION_ITEMS = Object.fromEntries(
  CLASSIFICATION_ORDER.map((value) => [value, CLASSIFICATION_STYLES[value].label]),
);

function PanelCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-[var(--outline-variant)] bg-white p-4">
      <h2 className="mb-3 text-[13px] font-semibold uppercase tracking-wide text-[var(--on-surface-variant)]">
        {title}
      </h2>
      {children}
    </section>
  );
}

export function useInvalidateReply(id: number) {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({ queryKey: ["reply", id] });
    void queryClient.invalidateQueries({ queryKey: ["replies"] });
    void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  };
}

export function ReplyTriagePanel({ reply }: { reply: ReplyDetail }) {
  const queryClient = useQueryClient();
  const invalidate = useInvalidateReply(reply.id);
  const [notes, setNotes] = useState(reply.notes ?? "");
  const [confirmMeeting, setConfirmMeeting] = useState(false);

  useEffect(() => setNotes(reply.notes ?? ""), [reply.notes]);

  const classify = useMutation({
    mutationFn: (classification: ReplyClassification) =>
      repliesApi.update(reply.id, { classification }),
    onSuccess: (updated) => {
      invalidate();
      if (updated.lead_id) void queryClient.invalidateQueries({ queryKey: ["leads"] });
      toast.success(`Labelled as ${CLASSIFICATION_STYLES[updated.classification].label}`);
    },
  });

  const saveNotes = useMutation({
    mutationFn: () => repliesApi.update(reply.id, { notes }),
    onSuccess: () => {
      invalidate();
      toast.success("Notes saved");
    },
  });

  const meeting = useMutation({
    mutationFn: () => repliesApi.update(reply.id, { mark_meeting_booked: true }),
    onSuccess: () => {
      invalidate();
      void queryClient.invalidateQueries({ queryKey: ["leads"] });
      if (reply.lead_id) void queryClient.invalidateQueries({ queryKey: ["lead", reply.lead_id] });
      setConfirmMeeting(false);
      toast.success("Meeting booked. The lead's status has been updated.");
    },
  });

  const match = reply.email_message_id
    ? (MATCH_METHODS[reply.match_method ?? ""] ?? {
        label: reply.match_method ?? "Unknown",
        detail: "",
      })
    : MATCH_METHODS.unmatched;
  const notesChanged = notes !== (reply.notes ?? "");

  return (
    <div className="space-y-4">
      <PanelCard title="Label">
        <label htmlFor="reply-classification" className="sr-only">
          Reply label
        </label>
        <Select
          value={reply.classification}
          items={CLASSIFICATION_ITEMS}
          onValueChange={(value) => {
            if (value && value !== reply.classification) {
              classify.mutate(value as ReplyClassification);
            }
          }}
          disabled={classify.isPending}
        >
          <SelectTrigger id="reply-classification" className="h-9 w-full bg-white">
            <SelectValue />
          </SelectTrigger>
          <SelectContent alignItemWithTrigger={false}>
            {CLASSIFICATION_ORDER.map((value) => (
              <SelectItem key={value} value={value}>
                {CLASSIFICATION_STYLES[value].label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="mt-2 text-[12px] text-[var(--on-surface-variant)]">
          {CLASSIFICATION_STYLES[reply.classification].description}
        </p>
        {reply.classified_by === "llm" ? (
          <p className="mt-2 flex items-center gap-1.5 text-[12px] text-[var(--on-surface-variant)]">
            <AiLabelMarker
              classifiedBy={reply.classified_by}
              confidence={reply.classification_confidence}
            />
            Suggested by AI. Change it if it&apos;s wrong.
          </p>
        ) : reply.classified_by ? (
          <p className="mt-2 text-[12px] text-[var(--on-surface-variant)]">
            Labelled by {reply.classified_by === "user" ? "your team" : "automatic rules"}.
          </p>
        ) : null}
        {reply.classification === "unsubscribe" ? (
          <p className="mt-2 flex items-start gap-1.5 text-[12px] text-[var(--on-surface-variant)]">
            <ShieldAlert className="mt-0.5 size-3.5 shrink-0 text-[var(--error)]" aria-hidden />
            This person won&apos;t be emailed again.
          </p>
        ) : null}
      </PanelCard>

      <PanelCard title="Next step">
        <Button
          className="w-full"
          variant="secondary"
          onClick={() => setConfirmMeeting(true)}
          disabled={!reply.lead_id || meeting.isPending}
        >
          <CalendarCheck aria-hidden />
          Mark meeting booked
        </Button>
        <p className="mt-2 text-[12px] text-[var(--on-surface-variant)]">
          {reply.lead_id
            ? "Moves the lead to \"Meeting booked\" so your pipeline stays accurate."
            : "Link this reply to a sent email first, so we know which lead it belongs to."}
        </p>
      </PanelCard>

      <PanelCard title="Notes">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            saveNotes.mutate();
          }}
          className="space-y-2"
        >
          <label htmlFor="reply-notes" className="sr-only">
            Notes about this reply
          </label>
          <Textarea
            id="reply-notes"
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            maxLength={5000}
            rows={4}
            placeholder="Anything your team should know, e.g. 'Call back in Q3'."
            className="bg-white text-[13px]"
          />
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11px] text-[var(--on-surface-variant)]">{notes.length}/5000</span>
            <Button type="submit" size="sm" disabled={!notesChanged || saveNotes.isPending}>
              {saveNotes.isPending ? "Saving…" : "Save notes"}
            </Button>
          </div>
        </form>
      </PanelCard>

      <PanelCard title="How it was matched">
        <div className="flex items-start gap-2">
          <Link2
            className={`mt-0.5 size-4 shrink-0 ${match.low ? "text-[var(--tertiary)]" : "text-[var(--secondary)]"}`}
            aria-hidden
          />
          <div>
            <p className="text-[13px] font-medium text-[var(--on-surface)]">{match.label}</p>
            {match.detail ? (
              <p className="text-[12px] text-[var(--on-surface-variant)]">{match.detail}</p>
            ) : null}
          </div>
        </div>
      </PanelCard>

      <ConfirmDialog
        open={confirmMeeting}
        onOpenChange={setConfirmMeeting}
        title="Mark a meeting as booked?"
        description={`${reply.lead_name ?? "This lead"} will move to "Meeting booked".`}
        confirmLabel="Mark meeting booked"
        loading={meeting.isPending}
        onConfirm={() => meeting.mutate()}
      />
    </div>
  );
}
