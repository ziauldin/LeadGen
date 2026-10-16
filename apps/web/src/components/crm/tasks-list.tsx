"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { EmptyState } from "@/components/shared/empty-state";
import { LoadingState } from "@/components/shared/loading-error";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useWorkspace } from "@/hooks/use-workspace";
import { crmApi } from "@/lib/api/endpoints";
import { cn } from "@/lib/utils";

const FILTERS = [
  { key: "mine", label: "My tasks", params: { scope: "mine", state: "open" } },
  { key: "overdue", label: "Overdue", params: { scope: "mine", state: "open", due: "overdue" } },
  { key: "all", label: "Everyone's", params: { scope: "all", state: "open" } },
  { key: "done", label: "Done", params: { scope: "all", state: "done" } },
] as const;

/** Task list with quick add. Pass ``leadId`` to show and add tasks for one lead. */
export function TasksList({ leadId }: { leadId?: number }) {
  const queryClient = useQueryClient();
  const { can } = useWorkspace();
  const canEdit = can("leads.write");
  const [filter, setFilter] = useState<(typeof FILTERS)[number]["key"]>("mine");
  const [title, setTitle] = useState("");
  const [due, setDue] = useState("");
  const params = leadId ? { lead_id: leadId, state: "all" } : FILTERS.find((f) => f.key === filter)!.params;
  const tasks = useQuery({ queryKey: ["tasks", params], queryFn: () => crmApi.tasks(params) });
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["tasks"] });
    void queryClient.invalidateQueries({ queryKey: ["timeline"] });
  };
  const add = useMutation({
    mutationFn: () =>
      crmApi.createTask({ title: title.trim(), due_at: due ? new Date(`${due}T09:00`).toISOString() : null, lead_id: leadId ?? null }),
    onSuccess: () => {
      setTitle("");
      setDue("");
      refresh();
    },
  });
  const toggle = useMutation({ mutationFn: ({ id, done }: { id: number; done: boolean }) => crmApi.updateTask(id, { done }), onSuccess: refresh });
  const remove = useMutation({ mutationFn: (id: number) => crmApi.deleteTask(id), onSuccess: refresh });
  const now = Date.now();

  return (
    <div className="space-y-3">
      {!leadId ? (
        <nav aria-label="Task filters" className="flex flex-wrap gap-1">
          {FILTERS.map((f) => (
            <Button key={f.key} size="sm" variant={f.key === filter ? "default" : "outline"} aria-pressed={f.key === filter} onClick={() => setFilter(f.key)}>
              {f.label}
            </Button>
          ))}
        </nav>
      ) : null}
      {canEdit ? (
        <form
          className="flex flex-col gap-2 sm:flex-row sm:items-end"
          onSubmit={(event) => {
            event.preventDefault();
            if (title.trim()) add.mutate();
          }}
        >
          <div className="grid flex-1 gap-1">
            <label htmlFor={`task-title-${leadId ?? "all"}`} className="text-[12px] font-medium">New task</label>
            <Input id={`task-title-${leadId ?? "all"}`} value={title} maxLength={255} placeholder="e.g. Call to confirm the demo" onChange={(e) => setTitle(e.target.value)} className="bg-white" />
          </div>
          <div className="grid gap-1">
            <label htmlFor={`task-due-${leadId ?? "all"}`} className="text-[12px] font-medium">Due</label>
            <Input id={`task-due-${leadId ?? "all"}`} type="date" value={due} onChange={(e) => setDue(e.target.value)} className="bg-white" />
          </div>
          <Button type="submit" size="sm" disabled={!title.trim() || add.isPending}>Add task</Button>
        </form>
      ) : null}
      {tasks.isLoading ? (
        <LoadingState />
      ) : tasks.data?.length ? (
        <ul aria-label="Tasks" className="divide-y divide-[var(--outline-variant)] rounded-lg border border-[var(--outline-variant)] bg-white">
          {tasks.data.map((task) => {
            const overdue = !task.done_at && task.due_at && new Date(task.due_at).getTime() < now;
            return (
              <li key={task.id} className="flex items-start gap-3 px-3 py-2.5">
                <input
                  type="checkbox"
                  className="mt-0.5 size-4 accent-[var(--primary)]"
                  checked={Boolean(task.done_at)}
                  disabled={!canEdit}
                  aria-label={`Mark "${task.title}" ${task.done_at ? "not done" : "done"}`}
                  onChange={(event) => toggle.mutate({ id: task.id, done: event.target.checked })}
                />
                <div className="min-w-0 flex-1 text-[13px]">
                  <p className={cn("font-medium", task.done_at && "text-[var(--on-surface-variant)] line-through")}>{task.title}</p>
                  <p className="text-[12px] text-[var(--on-surface-variant)]">
                    {task.due_at ? (
                      <span className={overdue ? "font-semibold text-[var(--error)]" : ""}>
                        {overdue ? "Overdue · " : "Due "}
                        {new Date(task.due_at).toLocaleDateString()}
                      </span>
                    ) : (
                      "No due date"
                    )}
                    {task.assignee_name ? ` · ${task.assignee_name}` : ""}
                    {task.lead_id && !leadId ? (
                      <>
                        {" · "}
                        <Link href={`/leads/${task.lead_id}`} className="underline">{task.lead_name}</Link>
                      </>
                    ) : null}
                  </p>
                </div>
                {canEdit ? (
                  <Button variant="ghost" size="icon-sm" aria-label={`Delete task ${task.title}`} onClick={() => remove.mutate(task.id)}>
                    <Trash2 aria-hidden />
                  </Button>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : (
        <EmptyState title="No tasks" description={leadId ? "Add a follow-up for this lead." : "You're all caught up."} />
      )}
    </div>
  );
}
