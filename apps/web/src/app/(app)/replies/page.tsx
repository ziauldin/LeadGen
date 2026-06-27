"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Calendar,
  CheckCircle2,
  Download,
  Inbox,
  MessageSquare,
  MoreHorizontal,
  RefreshCw,
  ThumbsDown,
  ThumbsUp,
  XCircle,
} from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { repliesApi } from "@/lib/api/endpoints";
import type { ReplyClassification } from "@/lib/api/types";

const CLASSIFICATION_CONFIG: Record<
  ReplyClassification,
  { label: string; bg: string; text: string; dot: string; icon: typeof CheckCircle2 }
> = {
  positive: {
    label: "Positive",
    bg: "var(--secondary-fixed)",
    text: "var(--on-secondary-fixed)",
    dot: "var(--on-secondary-fixed)",
    icon: ThumbsUp,
  },
  neutral: {
    label: "Neutral",
    bg: "var(--surface-variant)",
    text: "var(--on-surface-variant)",
    dot: "var(--outline)",
    icon: MessageSquare,
  },
  objection: {
    label: "Objection",
    bg: "var(--tertiary-fixed)",
    text: "var(--on-tertiary-fixed)",
    dot: "var(--on-tertiary-fixed)",
    icon: ThumbsDown,
  },
  unsubscribe: {
    label: "Unsubscribe",
    bg: "var(--error-container)",
    text: "var(--on-error-container)",
    dot: "var(--on-error-container)",
    icon: XCircle,
  },
  bounce: {
    label: "Bounce",
    bg: "var(--error-container)",
    text: "var(--on-error-container)",
    dot: "var(--on-error-container)",
    icon: XCircle,
  },
  unknown: {
    label: "Pending",
    bg: "var(--surface-container)",
    text: "var(--on-surface-variant)",
    dot: "var(--outline)",
    icon: MoreHorizontal,
  },
};

function ClassificationBadge({ classification }: { classification: ReplyClassification }) {
  const cfg = CLASSIFICATION_CONFIG[classification] ?? CLASSIFICATION_CONFIG.unknown;
  return (
    <span
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[12px] font-semibold whitespace-nowrap"
      style={{ background: cfg.bg, color: cfg.text }}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: cfg.dot }} />
      {cfg.label}
    </span>
  );
}

const TAB_FILTERS: { label: string; value: string }[] = [
  { label: "All", value: "" },
  { label: "Positive", value: "positive" },
  { label: "Neutral", value: "neutral" },
  { label: "Objection", value: "objection" },
  { label: "Unsubscribe", value: "unsubscribe" },
  { label: "Bounce", value: "bounce" },
];

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function RepliesPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState("");
  const [editingNotesId, setEditingNotesId] = useState<number | null>(null);
  const [notesDraft, setNotesDraft] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["replies", activeTab],
    queryFn: () => repliesApi.list(activeTab || undefined),
  });

  const syncMutation = useMutation({
    mutationFn: repliesApi.sync,
    onSuccess: (result) => {
      toast.success(result.message);
      queryClient.invalidateQueries({ queryKey: ["replies"] });
    },
    onError: () => toast.error("Sync failed"),
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
        mark
          ? { mark_meeting_booked: true }
          : notes !== undefined
            ? { notes }
            : { classification: "positive" },
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["replies"] });
      setEditingNotesId(null);
      toast.success("Reply updated");
    },
    onError: () => toast.error("Update failed"),
  });

  const replies = data?.items ?? [];

  return (
    <div>
      <PageHeader
        title="Replies"
        description="Classify inbound responses and update lead status accordingly."
        actions={
          <>
            <button
              onClick={() => void repliesApi.exportCsv().then(() => toast.success("Export started"))}
              className="flex items-center gap-2 px-4 py-2 border rounded text-[13px] font-medium transition-colors active:scale-95"
              style={{
                background: "var(--surface-container-lowest)",
                borderColor: "var(--outline-variant)",
                color: "var(--on-surface)",
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.background = "var(--surface-container-low)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = "var(--surface-container-lowest)")
              }
            >
              <Download className="w-4 h-4" />
              Export CSV
            </button>
            <button
              onClick={() => syncMutation.mutate()}
              disabled={syncMutation.isPending}
              className="flex items-center gap-2 px-5 py-2 rounded text-[13px] font-medium text-white transition-colors active:scale-95 disabled:opacity-60"
              style={{ background: "var(--primary)" }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.background = "var(--surface-tint)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = "var(--primary)")
              }
            >
              <RefreshCw className={`w-4 h-4 ${syncMutation.isPending ? "animate-spin" : ""}`} />
              {syncMutation.isPending ? "Syncing…" : "Sync Replies"}
            </button>
          </>
        }
      />

      {/* Tab filters */}
      <div
        className="flex items-center gap-1 mb-4 border-b"
        style={{ borderColor: "var(--outline-variant)" }}
      >
        {TAB_FILTERS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => setActiveTab(tab.value)}
            className="px-4 py-2.5 text-[13px] font-medium transition-colors border-b-2 -mb-px"
            style={{
              color:
                activeTab === tab.value ? "var(--primary)" : "var(--on-surface-variant)",
              borderColor:
                activeTab === tab.value ? "var(--primary)" : "transparent",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Table */}
      <div
        className="bg-white border rounded-lg shadow-sm overflow-hidden"
        style={{ borderColor: "var(--outline-variant)" }}
      >
        {isLoading ? (
          <div className="p-10 text-center">
            <div
              className="inline-block w-5 h-5 border-2 rounded-full animate-spin mb-3"
              style={{ borderColor: "var(--primary-container)", borderTopColor: "var(--primary)" }}
            />
          </div>
        ) : replies.length === 0 ? (
          <div className="p-16 text-center">
            <Inbox className="w-10 h-10 mx-auto mb-3" style={{ color: "var(--outline)" }} />
            <p className="text-[16px] font-semibold mb-1" style={{ color: "var(--on-surface)" }}>
              No replies yet
            </p>
            <p className="text-[13px]" style={{ color: "var(--on-surface-variant)" }}>
              Click &ldquo;Sync Replies&rdquo; to check for inbound responses.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse whitespace-nowrap">
              <thead>
                <tr
                  className="border-b"
                  style={{ background: "var(--surface)", borderColor: "var(--outline-variant)" }}
                >
                  {["From", "Lead", "Campaign", "Classification", "Received", "Notes", "Actions"].map(
                    (h) => (
                      <th
                        key={h}
                        className={`py-3 px-5 text-[11px] font-semibold uppercase tracking-wider ${
                          h === "Actions" ? "text-right" : ""
                        }`}
                        style={{ color: "var(--on-surface-variant)" }}
                      >
                        {h}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {replies.map((reply) => (
                  <tr
                    key={reply.id}
                    className="border-b group transition-colors"
                    style={{ borderColor: "var(--outline-variant)" }}
                    onMouseEnter={(e) =>
                      (e.currentTarget.style.background = "var(--surface-container-low)")
                    }
                    onMouseLeave={(e) =>
                      (e.currentTarget.style.background = "transparent")
                    }
                  >
                    <td className="py-3.5 px-5">
                      <span className="text-[13px]" style={{ color: "var(--on-surface)" }}>
                        {reply.from_email}
                      </span>
                    </td>
                    <td className="py-3.5 px-5">
                      <span
                        className="text-[13px] font-medium"
                        style={{ color: "var(--on-surface)" }}
                      >
                        {reply.lead_name ?? "—"}
                      </span>
                    </td>
                    <td className="py-3.5 px-5">
                      <span className="text-[13px]" style={{ color: "var(--on-surface-variant)" }}>
                        {reply.campaign_id ? `Campaign #${reply.campaign_id}` : "—"}
                      </span>
                    </td>
                    <td className="py-3.5 px-5">
                      <ClassificationBadge classification={reply.classification} />
                    </td>
                    <td className="py-3.5 px-5">
                      <div
                        className="flex items-center gap-1.5 text-[12px]"
                        style={{ color: "var(--on-surface-variant)" }}
                      >
                        <Calendar className="w-3.5 h-3.5" />
                        {formatDate(reply.received_at)}
                      </div>
                    </td>
                    <td className="py-3.5 px-5 max-w-[200px]">
                      {editingNotesId === reply.id ? (
                        <div className="flex items-center gap-2">
                          <input
                            type="text"
                            value={notesDraft}
                            onChange={(e) => setNotesDraft(e.target.value)}
                            className="flex-1 px-2 py-1 border rounded text-[12px] outline-none min-w-0"
                            style={{
                              borderColor: "var(--primary)",
                              color: "var(--on-surface)",
                            }}
                          />
                          <button
                            onClick={() => updateMutation.mutate({ id: reply.id, notes: notesDraft })}
                            className="px-2 py-1 rounded text-[11px] font-medium text-white"
                            style={{ background: "var(--primary)" }}
                          >
                            Save
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => {
                            setEditingNotesId(reply.id);
                            setNotesDraft(reply.notes ?? "");
                          }}
                          className="text-[12px] text-left truncate max-w-[160px] block"
                          style={{ color: "var(--on-surface-variant)" }}
                        >
                          {reply.notes || "Add note…"}
                        </button>
                      )}
                    </td>
                    <td className="py-3.5 px-5 text-right">
                      <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        {reply.classification === "positive" && (
                          <button
                            onClick={() => updateMutation.mutate({ id: reply.id, mark: true })}
                            className="flex items-center gap-1.5 px-2.5 py-1 border rounded text-[11px] font-medium"
                            style={{
                              borderColor: "var(--secondary)",
                              color: "var(--secondary)",
                            }}
                          >
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            Mark Meeting
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
