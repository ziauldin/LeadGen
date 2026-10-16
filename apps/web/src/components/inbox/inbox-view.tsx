"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlarmClock, CheckCheck, Inbox as InboxIcon, RotateCcw, Search, Send, Sparkles, Tag, UserCheck } from "lucide-react";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState, LoadingState } from "@/components/shared/loading-error";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/hooks/use-auth";
import { useWorkspace } from "@/hooks/use-workspace";
import { inboxApi } from "@/lib/api/endpoints";
import type { components } from "@/lib/api/schema";
import { cn } from "@/lib/utils";

type Row = components["schemas"]["ConversationRow"];
type Detail = components["schemas"]["ConversationDetail"];

const VIEWS = [
  { key: "open", label: "Open", params: { status: "open" } },
  { key: "mine", label: "Mine", params: { status: "open", assigned: "me" } },
  { key: "unassigned", label: "Unassigned", params: { status: "open", assigned: "unassigned" } },
  { key: "snoozed", label: "Snoozed", params: { status: "snoozed" } },
  { key: "done", label: "Done", params: { status: "done" } },
] as const;

const CLASSIFICATION_STYLES: Record<string, string> = {
  positive: "bg-[var(--primary-fixed)] text-[var(--on-primary-fixed)]",
  objection: "bg-[var(--tertiary-fixed,#ffe8c2)] text-[var(--on-surface)]",
  unsubscribe: "bg-[var(--error-container)] text-[var(--on-error-container)]",
};

function when(value?: string | null) {
  if (!value) return "";
  const date = new Date(value);
  const today = new Date();
  return date.toDateString() === today.toDateString()
    ? date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : date.toLocaleDateString([], { day: "numeric", month: "short" });
}

function tomorrowMorning() {
  const date = new Date();
  date.setDate(date.getDate() + 1);
  date.setHours(9, 0, 0, 0);
  return date.toISOString();
}

function nextWeek() {
  const date = new Date();
  date.setDate(date.getDate() + 7);
  date.setHours(9, 0, 0, 0);
  return date.toISOString();
}

function isTyping(target: EventTarget | null) {
  const el = target as HTMLElement | null;
  return Boolean(el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable));
}

function ConversationPane({ id, onChanged }: { id: number; onChanged: () => void }) {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const { can } = useWorkspace();
  const canManage = can("replies.manage");
  const composer = useRef<HTMLTextAreaElement>(null);
  const [draft, setDraft] = useState("");
  const [labelText, setLabelText] = useState("");
  const detail = useQuery({ queryKey: ["conversation", id], queryFn: () => inboxApi.get(id) });

  const refresh = (data?: Detail) => {
    if (data) queryClient.setQueryData(["conversation", id], data);
    onChanged();
  };
  const update = useMutation({
    mutationFn: (data: components["schemas"]["ConversationUpdate"]) => inboxApi.update(id, data),
    onSuccess: refresh,
  });
  const send = useMutation({
    mutationFn: () => inboxApi.reply(id, draft),
    onSuccess: () => {
      setDraft("");
      toast.success("Reply sent");
      void queryClient.invalidateQueries({ queryKey: ["conversation", id] });
      onChanged();
    },
  });
  const suggest = useMutation({
    mutationFn: () => inboxApi.suggest(id),
    onSuccess: (result) => {
      setDraft(result.body);
      composer.current?.focus();
    },
  });

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (isTyping(event.target) || event.metaKey || event.ctrlKey || event.altKey || !canManage) return;
      if (event.key === "e") update.mutate({ status: detail.data?.status === "done" ? "open" : "done" });
      else if (event.key === "s") update.mutate({ snoozed_until: tomorrowMorning() });
      else if (event.key === "a" && user) update.mutate({ assignee_id: user.id });
      else if (event.key === "u") update.mutate({ unread: true });
      else if (event.key === "r") {
        event.preventDefault();
        composer.current?.focus();
      } else return;
      event.preventDefault();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [canManage, detail.data?.status, update, user]);

  if (detail.isLoading) return <LoadingState />;
  if (detail.error) return <ErrorState error={detail.error} onRetry={() => void detail.refetch()} />;
  const c = detail.data!;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="border-b border-[var(--outline-variant)] p-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <h2 className="truncate text-[16px] font-semibold">
              {c.lead_id ? (
                <Link href={`/leads/${c.lead_id}`} className="hover:underline">
                  {c.lead_name ?? c.contact_email}
                </Link>
              ) : (
                c.contact_email
              )}
            </h2>
            <p className="truncate text-[12px] text-[var(--on-surface-variant)]">
              {[c.contact_email, c.company_name].filter(Boolean).join(" · ")}
            </p>
          </div>
          {canManage ? (
            <div className="flex flex-wrap gap-1">
              {user && c.assignee_id !== user.id ? (
                <Button size="sm" variant="outline" onClick={() => update.mutate({ assignee_id: user.id })} title="Assign to me (a)">
                  <UserCheck aria-hidden /> Assign to me
                </Button>
              ) : null}
              <Button size="sm" variant="outline" onClick={() => update.mutate({ snoozed_until: tomorrowMorning() })} title="Snooze until tomorrow (s)">
                <AlarmClock aria-hidden /> Tomorrow
              </Button>
              <Button size="sm" variant="ghost" onClick={() => update.mutate({ snoozed_until: nextWeek() })}>
                Next week
              </Button>
              {c.status === "done" ? (
                <Button size="sm" variant="outline" onClick={() => update.mutate({ status: "open" })} title="Reopen (e)">
                  <RotateCcw aria-hidden /> Reopen
                </Button>
              ) : (
                <Button size="sm" onClick={() => update.mutate({ status: "done" })} title="Mark done (e)">
                  <CheckCheck aria-hidden /> Done
                </Button>
              )}
            </div>
          ) : null}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[12px]">
          {c.assignee_name ? <span className="text-[var(--on-surface-variant)]">Assigned to {c.assignee_name}</span> : null}
          {c.snoozed_until && c.status === "snoozed" ? (
            <span className="text-[var(--on-surface-variant)]">· Snoozed until {new Date(c.snoozed_until).toLocaleString()}</span>
          ) : null}
          {c.labels.map((label) => (
            <button
              key={label}
              type="button"
              disabled={!canManage}
              onClick={() => update.mutate({ labels: c.labels.filter((l) => l !== label) })}
              className="rounded-full bg-[var(--surface-container)] px-2 py-0.5 hover:line-through"
              aria-label={`Remove label ${label}`}
            >
              {label}
            </button>
          ))}
          {canManage ? (
            <form
              className="flex items-center gap-1"
              onSubmit={(event) => {
                event.preventDefault();
                if (labelText.trim()) {
                  update.mutate({ labels: [...c.labels, labelText.trim()] });
                  setLabelText("");
                }
              }}
            >
              <Tag className="size-3.5 text-[var(--on-surface-variant)]" aria-hidden />
              <label htmlFor="add-label" className="sr-only">
                Add label
              </label>
              <Input
                id="add-label"
                value={labelText}
                maxLength={30}
                onChange={(event) => setLabelText(event.target.value)}
                placeholder="Add label"
                className="h-7 w-28 bg-white text-[12px]"
              />
            </form>
          ) : null}
        </div>
      </div>

      <ol aria-label="Messages" className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4" tabIndex={0}>
        {c.messages.map((message) => (
          <li
            key={`${message.kind}-${message.id}`}
            className={cn(
              "max-w-[90%] rounded-lg border p-3 text-[13px]",
              message.kind === "sent"
                ? "ml-auto border-[var(--primary-fixed)] bg-[var(--primary-fixed)]/40"
                : "border-[var(--outline-variant)] bg-white",
            )}
          >
            <p className="mb-1 flex flex-wrap items-center gap-2 text-[11px] text-[var(--on-surface-variant)]">
              <span className="font-semibold text-[var(--on-surface)]">{message.kind === "sent" ? "You" : (message.from_email ?? "Them")}</span>
              <span>{new Date(message.at).toLocaleString()}</span>
              {message.classification ? (
                <span className={cn("rounded-full px-1.5 capitalize", CLASSIFICATION_STYLES[message.classification] ?? "bg-[var(--surface-container)]")}>
                  {message.classification.replace(/_/g, " ")}
                </span>
              ) : null}
            </p>
            {message.subject ? <p className="mb-1 font-medium">{message.subject}</p> : null}
            <p className="whitespace-pre-wrap break-words">{message.body}</p>
          </li>
        ))}
      </ol>

      {canManage ? (
        <form
          className="border-t border-[var(--outline-variant)] p-3"
          onSubmit={(event) => {
            event.preventDefault();
            if (draft.trim() && c.can_reply) send.mutate();
          }}
        >
          <label htmlFor="inbox-reply" className="sr-only">
            Reply
          </label>
          <Textarea
            id="inbox-reply"
            ref={composer}
            rows={4}
            value={draft}
            disabled={!c.can_reply}
            placeholder={c.can_reply ? "Write a reply… (Ctrl+Enter to send)" : "Link this reply to a lead on the Replies page to answer it here."}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && (event.ctrlKey || event.metaKey) && draft.trim()) send.mutate();
              if (event.key === "Escape") (event.target as HTMLTextAreaElement).blur();
            }}
            className="bg-white text-[13px]"
          />
          <div className="mt-2 flex justify-between gap-2">
            <Button type="button" size="sm" variant="ghost" disabled={!c.can_reply || suggest.isPending} onClick={() => suggest.mutate()}>
              <Sparkles aria-hidden /> {suggest.isPending ? "Thinking…" : "Suggest a reply"}
            </Button>
            <Button type="submit" size="sm" disabled={!c.can_reply || !draft.trim() || send.isPending}>
              <Send aria-hidden /> {send.isPending ? "Sending…" : "Send"}
            </Button>
          </div>
        </form>
      ) : null}
    </div>
  );
}

export function InboxView() {
  const router = useRouter();
  const params = useSearchParams();
  const queryClient = useQueryClient();
  const view = VIEWS.find((v) => v.key === params.get("view")) ?? VIEWS[0];
  const selected = Number(params.get("c")) || null;
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(search.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  const listParams = useMemo(() => ({ ...view.params, search: query || undefined, limit: 100 }), [view, query]);
  const list = useQuery({
    queryKey: ["inbox", listParams],
    queryFn: () => inboxApi.list(listParams),
    refetchInterval: 30_000,
    placeholderData: (previous) => previous,
  });
  const rows = useMemo(() => list.data?.items ?? [], [list.data]);

  const select = useCallback(
    (id: number | null, nextView?: string) => {
      const next = new URLSearchParams(params.toString());
      if (id) next.set("c", String(id));
      else next.delete("c");
      if (nextView) next.set("view", nextView);
      router.replace(`/inbox?${next.toString()}`, { scroll: false });
    },
    [params, router],
  );

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (isTyping(event.target) || event.metaKey || event.ctrlKey || event.altKey) return;
      if (event.key !== "j" && event.key !== "k") return;
      event.preventDefault();
      const index = rows.findIndex((row) => row.id === selected);
      const next = event.key === "j" ? Math.min(rows.length - 1, index + 1) : Math.max(0, index - 1);
      if (rows[next]) select(rows[next].id);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [rows, select, selected]);

  const onChanged = () => void queryClient.invalidateQueries({ queryKey: ["inbox"] });

  return (
    <div className="flex h-[calc(100vh-8rem)] min-h-[520px] overflow-hidden rounded-lg border border-[var(--outline-variant)] bg-[var(--surface-container-lowest)]">
      <div className={cn("flex w-full flex-col border-r border-[var(--outline-variant)] md:w-[360px] md:shrink-0", selected && "hidden md:flex")}>
        <nav aria-label="Inbox views" className="flex gap-1 overflow-x-auto border-b border-[var(--outline-variant)] px-2 pt-2">
          {VIEWS.map((v) => (
            <button
              key={v.key}
              type="button"
              onClick={() => select(null, v.key)}
              aria-current={v.key === view.key ? "page" : undefined}
              className={cn(
                "whitespace-nowrap border-b-2 px-2.5 py-1.5 text-[13px] font-medium",
                v.key === view.key ? "border-[var(--primary)] text-[var(--primary)]" : "border-transparent text-[var(--on-surface-variant)]",
              )}
            >
              {v.label}
              {v.key === "open" && list.data?.counts.unread ? (
                <span className="ml-1 rounded-full bg-[var(--primary)] px-1.5 text-[11px] text-white">{list.data.counts.unread}</span>
              ) : null}
            </button>
          ))}
        </nav>
        <div className="relative p-2">
          <Search className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-[var(--on-surface-variant)]" aria-hidden />
          <label htmlFor="inbox-search" className="sr-only">
            Search conversations
          </label>
          <Input
            id="inbox-search"
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search name, email or subject"
            className="h-9 bg-white pl-8"
          />
        </div>
        {list.isLoading ? (
          <LoadingState />
        ) : list.error ? (
          <ErrorState error={list.error} onRetry={() => void list.refetch()} />
        ) : rows.length ? (
          <ul aria-label="Conversations" className="min-h-0 flex-1 divide-y divide-[var(--outline-variant)] overflow-y-auto">
            {rows.map((row: Row) => (
              <li key={row.id}>
                <button
                  type="button"
                  onClick={() => select(row.id)}
                  aria-current={row.id === selected ? "true" : undefined}
                  className={cn(
                    "block w-full px-3 py-2.5 text-left hover:bg-[var(--surface-container-low)]",
                    row.id === selected && "bg-[var(--surface-container-high)]",
                  )}
                >
                  <span className="flex items-center justify-between gap-2">
                    <span className={cn("truncate text-[13px]", row.unread ? "font-bold" : "font-medium")}>
                      {row.unread ? <span className="sr-only">Unread: </span> : null}
                      {row.lead_name ?? row.contact_email}
                    </span>
                    <span className="shrink-0 text-[11px] text-[var(--on-surface-variant)]">{when(row.last_message_at)}</span>
                  </span>
                  <span className="mt-0.5 block truncate text-[12px] text-[var(--on-surface-variant)]">{row.subject ?? "(no subject)"}</span>
                  <span className="mt-1 flex flex-wrap gap-1">
                    {row.last_classification ? (
                      <span className={cn("rounded-full px-1.5 text-[11px] capitalize", CLASSIFICATION_STYLES[row.last_classification] ?? "bg-[var(--surface-container)]")}>
                        {row.last_classification.replace(/_/g, " ")}
                      </span>
                    ) : null}
                    {row.labels.map((label) => (
                      <span key={label} className="rounded-full bg-[var(--surface-container)] px-1.5 text-[11px]">
                        {label}
                      </span>
                    ))}
                    {row.assignee_name ? <span className="text-[11px] text-[var(--on-surface-variant)]">→ {row.assignee_name}</span> : null}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <div className="p-4">
            <EmptyState
              title={view.key === "open" ? "Inbox zero" : "Nothing here"}
              description={view.key === "open" ? "New replies to your campaigns show up here." : "No conversations in this view."}
            />
          </div>
        )}
        <p className="border-t border-[var(--outline-variant)] px-3 py-2 text-[11px] text-[var(--on-surface-variant)]">
          Shortcuts: <kbd>j</kbd>/<kbd>k</kbd> move · <kbd>r</kbd> reply · <kbd>e</kbd> done · <kbd>s</kbd> snooze · <kbd>a</kbd> assign to me
        </p>
      </div>
      <section aria-label="Conversation" className={cn("min-w-0 flex-1", !selected && "hidden md:block")}>
        {selected ? (
          <>
            <button type="button" className="p-3 text-[13px] text-[var(--primary)] md:hidden" onClick={() => select(null)}>
              ← All conversations
            </button>
            <ConversationPane key={selected} id={selected} onChanged={onChanged} />
          </>
        ) : (
          <div className="flex h-full items-center justify-center p-6 text-center text-[13px] text-[var(--on-surface-variant)]">
            <span>
              <InboxIcon className="mx-auto mb-2 size-8" aria-hidden />
              Choose a conversation, or press <kbd>j</kbd> to start.
            </span>
          </div>
        )}
      </section>
    </div>
  );
}
