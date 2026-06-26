"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PageHeader } from "@/components/layout/page-header";
import { ReplyClassificationBadge } from "@/components/replies/reply-classification-badge";
import { repliesApi } from "@/lib/api/endpoints";

export default function RepliesPage() {
  const queryClient = useQueryClient();
  const [editingNotesId, setEditingNotesId] = useState<number | null>(null);
  const [notesDraft, setNotesDraft] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["replies"],
    queryFn: () => repliesApi.list(),
  });

  const syncMutation = useMutation({
    mutationFn: repliesApi.sync,
    onSuccess: (result) => {
      toast.success(result.message);
      queryClient.invalidateQueries({ queryKey: ["replies"] });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      mark,
      notes,
    }: {
      id: number;
      mark?: boolean;
      notes?: string;
    }) =>
      repliesApi.update(
        id,
        mark ? { mark_meeting_booked: true } : notes !== undefined ? { notes } : { classification: "positive" },
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["replies"] });
      setEditingNotesId(null);
      toast.success("Reply updated");
    },
  });

  async function handleExport() {
    try {
      await repliesApi.exportCsv();
      toast.success("Export started");
    } catch {
      toast.error("Export failed");
    }
  }

  return (
    <div>
      <PageHeader
        title="Replies"
        description="Classify inbound responses and update lead status."
        actions={
          <>
            <Button variant="outline" onClick={() => void handleExport()}>
              Export CSV
            </Button>
            <Button onClick={() => syncMutation.mutate()} disabled={syncMutation.isPending}>
              Sync replies
            </Button>
          </>
        }
      />
      {isLoading ? <p className="text-sm text-muted-foreground">Loading…</p> : null}
      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>From</TableHead>
              <TableHead>Lead</TableHead>
              <TableHead>Classification</TableHead>
              <TableHead>Notes</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data?.items.map((reply) => (
              <TableRow key={reply.id}>
                <TableCell>{reply.from_email}</TableCell>
                <TableCell>{reply.lead_name ?? "—"}</TableCell>
                <TableCell>
                  <ReplyClassificationBadge classification={reply.classification} />
                </TableCell>
                <TableCell className="max-w-xs">
                  {editingNotesId === reply.id ? (
                    <div className="space-y-2">
                      <Textarea
                        rows={2}
                        value={notesDraft}
                        onChange={(e) => setNotesDraft(e.target.value)}
                      />
                      <Button
                        size="sm"
                        onClick={() =>
                          updateMutation.mutate({ id: reply.id, notes: notesDraft })
                        }
                      >
                        Save
                      </Button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      className="text-left text-sm text-muted-foreground hover:underline"
                      onClick={() => {
                        setEditingNotesId(reply.id);
                        setNotesDraft(reply.notes ?? "");
                      }}
                    >
                      {reply.notes || "Add notes…"}
                    </button>
                  )}
                </TableCell>
                <TableCell className="text-right">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => updateMutation.mutate({ id: reply.id, mark: true })}
                    disabled={updateMutation.isPending}
                  >
                    Mark meeting
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
