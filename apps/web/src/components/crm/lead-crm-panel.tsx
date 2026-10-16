"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { KanbanSquare } from "lucide-react";
import { TasksList } from "@/components/crm/tasks-list";
import { LoadingState } from "@/components/shared/loading-error";
import { Button } from "@/components/ui/button";
import { ButtonLink } from "@/components/ui/button-link";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/hooks/use-auth";
import { useFlags } from "@/hooks/use-flags";
import { useWorkspace } from "@/hooks/use-workspace";
import { crmApi } from "@/lib/api/endpoints";

const KIND_LABELS: Record<string, string> = {
  email: "Email",
  reply: "Reply",
  note: "Note",
  task: "Task",
  task_done: "Task",
  activity: "Update",
};

function Timeline({ leadId }: { leadId: number }) {
  const timeline = useQuery({ queryKey: ["timeline", leadId], queryFn: () => crmApi.timeline(leadId) });
  if (timeline.isLoading) return <LoadingState />;
  if (!timeline.data?.length) return <p className="text-[13px] text-[var(--on-surface-variant)]">Nothing has happened yet.</p>;
  return (
    <ol aria-label="Activity" className="relative space-y-3 border-l border-[var(--outline-variant)] pl-4">
      {timeline.data.map((event, index) => (
        <li key={`${event.kind}-${event.ref_id}-${index}`} className="text-[13px]">
          <span aria-hidden className="absolute -left-[5px] mt-1.5 size-2.5 rounded-full bg-[var(--primary)]" />
          <p className="flex flex-wrap items-baseline gap-2">
            <span className="rounded bg-[var(--surface-container)] px-1.5 text-[11px]">{KIND_LABELS[event.kind] ?? event.kind}</span>
            <span className="font-medium">{event.title}</span>
            <span className="text-[11px] text-[var(--on-surface-variant)]">
              {new Date(event.at).toLocaleString()}
              {event.actor ? ` · ${event.actor}` : ""}
            </span>
          </p>
          {event.detail ? <p className="mt-0.5 line-clamp-3 whitespace-pre-wrap text-[12px] text-[var(--on-surface-variant)]">{event.detail}</p> : null}
        </li>
      ))}
    </ol>
  );
}

function Notes({ leadId }: { leadId: number }) {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const { can } = useWorkspace();
  const [body, setBody] = useState("");
  const notes = useQuery({ queryKey: ["notes", leadId], queryFn: () => crmApi.notes(leadId) });
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["notes", leadId] });
    void queryClient.invalidateQueries({ queryKey: ["timeline", leadId] });
  };
  const add = useMutation({ mutationFn: () => crmApi.addNote(leadId, body), onSuccess: () => { setBody(""); refresh(); } });
  const remove = useMutation({ mutationFn: (id: number) => crmApi.deleteNote(id), onSuccess: refresh });
  return (
    <div className="space-y-3">
      {can("leads.write") ? (
        <form className="grid gap-2" onSubmit={(event) => { event.preventDefault(); if (body.trim()) add.mutate(); }}>
          <label htmlFor="new-note" className="text-[12px] font-medium">Add a note</label>
          <Textarea id="new-note" rows={3} value={body} maxLength={10_000} onChange={(e) => setBody(e.target.value)} className="bg-white text-[13px]" />
          <div><Button type="submit" size="sm" disabled={!body.trim() || add.isPending}>Save note</Button></div>
        </form>
      ) : null}
      <ul className="space-y-2">
        {notes.data?.map((note) => (
          <li key={note.id} className="rounded-lg border border-[var(--outline-variant)] bg-white p-3 text-[13px]">
            <p className="whitespace-pre-wrap">{note.body}</p>
            <p className="mt-1 flex items-center justify-between text-[11px] text-[var(--on-surface-variant)]">
              <span>{note.author_name ?? "Someone"} · {new Date(note.created_at).toLocaleString()}</span>
              {note.author_id === user?.id ? (
                <button type="button" className="underline" onClick={() => remove.mutate(note.id)}>Delete</button>
              ) : null}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Timeline, notes, tasks and deal creation for one lead (CRM must be on). */
export function LeadCrmPanel({ leadId, leadName }: { leadId: number; leadName: string }) {
  const flags = useFlags();
  const { can } = useWorkspace();
  const queryClient = useQueryClient();
  const createDeal = useMutation({
    mutationFn: () => crmApi.createDeal({ lead_id: leadId, title: leadName }),
    onSuccess: () => {
      toast.success("Deal created");
      void queryClient.invalidateQueries({ queryKey: ["timeline", leadId] });
      void queryClient.invalidateQueries({ queryKey: ["deals-board"] });
    },
  });
  if (!flags.crm) return null;
  return (
    <section aria-labelledby="crm-heading" className="mt-6 rounded-lg border border-[var(--outline-variant)] bg-white p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 id="crm-heading" className="text-[15px] font-semibold">Activity</h2>
        <div className="flex gap-2">
          {can("leads.write") ? (
            <Button size="sm" variant="outline" disabled={createDeal.isPending} onClick={() => createDeal.mutate()}>
              <KanbanSquare aria-hidden /> Create deal
            </Button>
          ) : null}
          <ButtonLink href="/deals" size="sm" variant="ghost">Deals board</ButtonLink>
        </div>
      </div>
      <Tabs defaultValue="timeline">
        <TabsList variant="line" className="border-b border-[var(--outline-variant)] pb-1">
          <TabsTrigger value="timeline" className="px-3 text-[13px]">Timeline</TabsTrigger>
          <TabsTrigger value="notes" className="px-3 text-[13px]">Notes</TabsTrigger>
          <TabsTrigger value="tasks" className="px-3 text-[13px]">Tasks</TabsTrigger>
        </TabsList>
        <TabsContent value="timeline" className="pt-4"><Timeline leadId={leadId} /></TabsContent>
        <TabsContent value="notes" className="pt-4"><Notes leadId={leadId} /></TabsContent>
        <TabsContent value="tasks" className="pt-4"><TasksList leadId={leadId} /></TabsContent>
      </Tabs>
    </section>
  );
}
