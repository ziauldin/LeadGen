"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus } from "lucide-react";
import { ErrorState, LoadingState } from "@/components/shared/loading-error";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useWorkspace } from "@/hooks/use-workspace";
import { crmApi } from "@/lib/api/endpoints";
import type { components } from "@/lib/api/schema";
import { cn } from "@/lib/utils";

type Deal = components["schemas"]["DealRead"];
type Stage = components["schemas"]["StageRead"];

export function money(cents: number, currency = "USD") {
  return new Intl.NumberFormat(undefined, { style: "currency", currency, maximumFractionDigits: 0 }).format(cents / 100);
}

function NewDealDialog({ open, onOpenChange, stageId }: { open: boolean; onOpenChange: (open: boolean) => void; stageId?: number }) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [value, setValue] = useState("");
  const [close, setClose] = useState("");
  const create = useMutation({
    mutationFn: () =>
      crmApi.createDeal({
        title: title.trim(),
        value_cents: Math.round(Number(value || 0) * 100),
        expected_close_date: close || null,
        stage_id: stageId ?? null,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["deals-board"] });
      setTitle("");
      setValue("");
      setClose("");
      onOpenChange(false);
      toast.success("Deal created");
    },
  });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[440px]">
        <form
          className="grid gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (title.trim()) create.mutate();
          }}
        >
          <DialogHeader>
            <DialogTitle>New deal</DialogTitle>
            <DialogDescription>To open a deal for a lead, use Create deal on the lead&apos;s page.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-1.5">
            <label htmlFor="deal-title" className="text-[13px] font-medium">Name</label>
            <Input id="deal-title" required maxLength={255} value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <label htmlFor="deal-value" className="text-[13px] font-medium">Value</label>
              <Input id="deal-value" type="number" min={0} step="1" value={value} onChange={(e) => setValue(e.target.value)} />
            </div>
            <div className="grid gap-1.5">
              <label htmlFor="deal-close" className="text-[13px] font-medium">Expected close</label>
              <Input id="deal-close" type="date" value={close} onChange={(e) => setClose(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={!title.trim() || create.isPending}>Create deal</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function DealCard({ deal, stages, canEdit, onMove }: { deal: Deal; stages: Stage[]; canEdit: boolean; onMove: (stageId: number) => void }) {
  return (
    <li
      draggable={canEdit}
      onDragStart={(event) => event.dataTransfer.setData("text/deal", String(deal.id))}
      className="rounded-lg border border-[var(--outline-variant)] bg-white p-3 text-[13px] shadow-sm"
    >
      <p className="font-medium">
        {deal.lead_id ? (
          <Link href={`/leads/${deal.lead_id}`} className="hover:underline">{deal.title}</Link>
        ) : (
          deal.title
        )}
      </p>
      <p className="mt-0.5 text-[12px] text-[var(--on-surface-variant)]">
        {money(deal.value_cents, deal.currency)}
        {deal.expected_close_date ? ` · closes ${new Date(deal.expected_close_date).toLocaleDateString()}` : ""}
        {deal.owner_name ? ` · ${deal.owner_name}` : ""}
        {deal.source === "reply" ? " · from a reply" : ""}
      </p>
      {canEdit ? (
        <label className="mt-2 flex items-center gap-1 text-[11px] text-[var(--on-surface-variant)]">
          <span className="sr-only">Move {deal.title} to</span>
          <select
            className="w-full rounded border border-[var(--outline-variant)] bg-white px-1 py-0.5 text-[12px]"
            value={deal.stage_id}
            onChange={(event) => onMove(Number(event.target.value))}
            aria-label={`Stage for ${deal.title}`}
          >
            {stages.map((stage) => (
              <option key={stage.id} value={stage.id}>{stage.name}</option>
            ))}
          </select>
        </label>
      ) : null}
    </li>
  );
}

export function DealsBoard() {
  const queryClient = useQueryClient();
  const { can } = useWorkspace();
  const canEdit = can("leads.write");
  const board = useQuery({ queryKey: ["deals-board"], queryFn: crmApi.board });
  const [creating, setCreating] = useState<{ stageId?: number } | null>(null);
  const [dragOver, setDragOver] = useState<number | null>(null);
  const move = useMutation({
    mutationFn: ({ id, stageId }: { id: number; stageId: number }) => crmApi.updateDeal(id, { stage_id: stageId }),
    onMutate: async ({ id, stageId }) => {
      await queryClient.cancelQueries({ queryKey: ["deals-board"] });
      const previous = queryClient.getQueryData<components["schemas"]["Board"]>(["deals-board"]);
      if (previous) {
        queryClient.setQueryData(["deals-board"], {
          ...previous,
          deals: previous.deals.map((d) => (d.id === id ? { ...d, stage_id: stageId } : d)),
        });
      }
      return { previous };
    },
    onError: (_error, _vars, context) => context?.previous && queryClient.setQueryData(["deals-board"], context.previous),
    onSettled: () => void queryClient.invalidateQueries({ queryKey: ["deals-board"] }),
  });

  if (board.isLoading) return <LoadingState />;
  if (board.error) return <ErrorState error={board.error} onRetry={() => void board.refetch()} />;
  const data = board.data!;
  const currency = data.deals[0]?.currency ?? "USD";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[13px] text-[var(--on-surface-variant)]">
          {data.deals.length} deals · weighted pipeline {money(data.weighted_pipeline_cents, currency)}
        </p>
        {canEdit ? (
          <Button size="sm" onClick={() => setCreating({})}>
            <Plus aria-hidden /> New deal
          </Button>
        ) : null}
      </div>
      <div className="flex gap-3 overflow-x-auto pb-2" tabIndex={0} aria-label="Deals board">
        {data.stages.map((stage) => {
          const deals = data.deals.filter((d) => d.stage_id === stage.id);
          return (
            <section
              key={stage.id}
              aria-labelledby={`stage-${stage.id}`}
              onDragOver={(event) => {
                if (!canEdit) return;
                event.preventDefault();
                setDragOver(stage.id);
              }}
              onDragLeave={() => setDragOver(null)}
              onDrop={(event) => {
                event.preventDefault();
                setDragOver(null);
                const id = Number(event.dataTransfer.getData("text/deal"));
                if (id) move.mutate({ id, stageId: stage.id });
              }}
              className={cn(
                "flex w-64 shrink-0 flex-col rounded-lg bg-[var(--surface-container-low)] p-2",
                dragOver === stage.id && "ring-2 ring-[var(--primary)]",
              )}
            >
              <header className="mb-2 flex items-baseline justify-between px-1">
                <h2 id={`stage-${stage.id}`} className="text-[13px] font-semibold">
                  {stage.name}
                  <span className="ml-1 font-normal text-[var(--on-surface-variant)]">{deals.length}</span>
                </h2>
                <span className="text-[11px] text-[var(--on-surface-variant)]">{money(stage.value_cents, currency)}</span>
              </header>
              <ul className="space-y-2">
                {deals.map((deal) => (
                  <DealCard key={deal.id} deal={deal} stages={data.stages} canEdit={canEdit} onMove={(stageId) => move.mutate({ id: deal.id, stageId })} />
                ))}
              </ul>
              {canEdit && stage.kind === "open" ? (
                <Button variant="ghost" size="sm" className="mt-2 justify-start" onClick={() => setCreating({ stageId: stage.id })}>
                  <Plus aria-hidden /> Add deal
                </Button>
              ) : null}
            </section>
          );
        })}
      </div>
      <NewDealDialog open={creating !== null} onOpenChange={(open) => !open && setCreating(null)} stageId={creating?.stageId} />
    </div>
  );
}
