"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Calendar,
  CheckCircle2,
  ChevronRight,
  Megaphone,
  Pause,
  Play,
  Plus,
} from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { campaignsApi } from "@/lib/api/endpoints";
import type { CampaignStatus } from "@/lib/api/types";

const CAMPAIGN_STATUS_CONFIG: Record<
  CampaignStatus,
  { label: string; bg: string; text: string; dot: string }
> = {
  draft: {
    label: "Draft",
    bg: "var(--surface-variant)",
    text: "var(--on-surface-variant)",
    dot: "var(--outline)",
  },
  active: {
    label: "Active",
    bg: "var(--secondary-fixed)",
    text: "var(--on-secondary-fixed)",
    dot: "var(--on-secondary-fixed)",
  },
  paused: {
    label: "Paused",
    bg: "var(--tertiary-fixed)",
    text: "var(--on-tertiary-fixed)",
    dot: "var(--on-tertiary-fixed)",
  },
  completed: {
    label: "Completed",
    bg: "var(--primary-fixed)",
    text: "var(--on-primary-fixed)",
    dot: "var(--on-primary-fixed)",
  },
};

function CampaignStatusBadge({ status }: { status: CampaignStatus }) {
  const cfg = CAMPAIGN_STATUS_CONFIG[status];
  return (
    <span
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[12px] font-semibold"
      style={{ background: cfg.bg, color: cfg.text }}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: cfg.dot }} />
      {cfg.label}
    </span>
  );
}

export default function CampaignsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => campaignsApi.list(),
  });

  const campaigns = data?.items ?? [];

  return (
    <div>
      <PageHeader
        title="Campaigns"
        description="Outreach sequences with manual-approval send gates and compliance controls."
        actions={
          <Link
            href="/campaigns/new"
            className="flex items-center gap-2 px-5 py-2 rounded text-[13px] font-medium text-white active:scale-95 shadow-sm"
            style={{ background: "var(--primary)" }}
            onMouseEnter={(e: React.MouseEvent<HTMLAnchorElement>) =>
              (e.currentTarget.style.background = "var(--surface-tint)")
            }
            onMouseLeave={(e: React.MouseEvent<HTMLAnchorElement>) =>
              (e.currentTarget.style.background = "var(--primary)")
            }
          >
            <Plus className="w-4 h-4" />
            New Campaign
          </Link>
        }
      />

      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="bg-white border rounded-lg p-5 h-48 animate-pulse"
              style={{ borderColor: "var(--outline-variant)" }}
            />
          ))}
        </div>
      ) : campaigns.length === 0 ? (
        <div
          className="flex flex-col items-center justify-center py-24 rounded-lg border"
          style={{ background: "var(--surface-container-low)", borderColor: "var(--outline-variant)" }}
        >
          <div
            className="w-16 h-16 rounded-full flex items-center justify-center mb-4"
            style={{ background: "var(--primary-fixed)" }}
          >
            <Megaphone className="w-8 h-8" style={{ color: "var(--primary)" }} />
          </div>
          <h3 className="text-[18px] font-semibold mb-2" style={{ color: "var(--on-surface)" }}>
            No campaigns yet
          </h3>
          <p className="text-[14px] mb-6" style={{ color: "var(--on-surface-variant)" }}>
            Create a campaign to manage your outreach sequence.
          </p>
          <Link
            href="/campaigns/new"
            className="flex items-center gap-2 px-5 py-2 rounded text-[13px] font-medium text-white"
            style={{ background: "var(--primary)" }}
          >
            <Plus className="w-4 h-4" />
            Create campaign
          </Link>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {campaigns.map((campaign) => (
            <div
              key={campaign.id}
              className="bg-white border rounded-lg p-5 shadow-sm hover:shadow-md transition-shadow group"
              style={{ borderColor: "var(--outline-variant)" }}
            >
              <div className="flex items-start justify-between mb-4">
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center"
                  style={{ background: "var(--primary-fixed)" }}
                >
                  <Megaphone className="w-5 h-5" style={{ color: "var(--primary)" }} />
                </div>
                <CampaignStatusBadge status={campaign.status} />
              </div>

              <h3 className="text-[16px] font-semibold mb-1" style={{ color: "var(--on-surface)" }}>
                <Link
                  href={`/campaigns/${campaign.id}`}
                  className="hover:underline"
                  style={{ color: "inherit" }}
                >
                  {campaign.name}
                </Link>
              </h3>

              <div className="space-y-1.5 mt-3 mb-4">
                <div className="flex items-center gap-2 text-[12px]" style={{ color: "var(--on-surface-variant)" }}>
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  {campaign.daily_send_limit} emails/day limit
                </div>
                {campaign.sending_window_start && (
                  <div className="flex items-center gap-2 text-[12px]" style={{ color: "var(--on-surface-variant)" }}>
                    <Calendar className="w-3.5 h-3.5" />
                    {campaign.sending_window_start} – {campaign.sending_window_end}
                  </div>
                )}
                <div className="flex items-center gap-2 text-[12px]" style={{ color: "var(--on-surface-variant)" }}>
                  {campaign.status === "active" ? (
                    <Play className="w-3.5 h-3.5" style={{ color: "var(--secondary)" }} />
                  ) : (
                    <Pause className="w-3.5 h-3.5" />
                  )}
                  {campaign.steps.length} step{campaign.steps.length !== 1 ? "s" : ""} in sequence
                </div>
              </div>

              <div
                className="pt-4 border-t flex items-center justify-between"
                style={{ borderColor: "var(--outline-variant)" }}
              >
                <Link
                  href={`/campaigns/${campaign.id}`}
                  className="flex items-center gap-1 text-[12px] font-medium"
                  style={{ color: "var(--primary)" }}
                >
                  View details
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
                <Link
                  href={`/campaigns/${campaign.id}`}
                  className="p-1.5 rounded"
                  style={{ color: "var(--on-surface-variant)" }}
                >
                  <ChevronRight className="w-4 h-4" />
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
