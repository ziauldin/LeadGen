"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  ArrowLeft,
  CheckCircle2,
  OctagonAlert,
  Pause,
  Pencil,
  Play,
  Send,
  ShieldCheck,
  UserPlus,
} from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ButtonLink } from "@/components/ui/button-link";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { ErrorState } from "@/components/shared/loading-error";
import { AddLeadsDialog } from "@/components/campaigns/add-leads-dialog";
import { CampaignEnrollmentsTable } from "@/components/campaigns/campaign-enrollments-table";
import { CampaignMessagesTable } from "@/components/campaigns/campaign-messages-table";
import { CampaignOverview } from "@/components/campaigns/campaign-overview";
import { CampaignSendersCard } from "@/components/campaigns/campaign-senders-card";
import { CampaignVariantsCard } from "@/components/campaigns/campaign-variants-card";
import { CampaignSequenceView } from "@/components/campaigns/campaign-sequence-view";
import { CampaignStatusBadge } from "@/components/campaigns/campaign-status-badge";
import { formatDate, formatDateTime, formatSendingDays } from "@/components/campaigns/format";
import { useWorkspace } from "@/hooks/use-workspace";
import { ApiError } from "@/lib/api/client";
import { campaignsApi, nichesApi } from "@/lib/api/endpoints";
import type { Campaign } from "@/lib/api/types";

const TABS = [
  { value: "overview", label: "Overview" },
  { value: "sequence", label: "Sequence" },
  { value: "enrollments", label: "Leads" },
  { value: "messages", label: "Emails" },
] as const;
type TabValue = (typeof TABS)[number]["value"];

function isTab(value: string | null): value is TabValue {
  return TABS.some((tab) => tab.value === value);
}

function scheduleSummary(campaign: Campaign): string {
  const window =
    campaign.sending_window_start && campaign.sending_window_end
      ? `${campaign.sending_window_start}–${campaign.sending_window_end}`
      : "the default window";
  return `${formatSendingDays(campaign.sending_days)}, ${window}${campaign.timezone ? ` (${campaign.timezone})` : ""}, up to ${campaign.daily_send_limit} a day`;
}

function BackLink() {
  return (
    <Link
      href="/campaigns"
      className="mb-3 inline-flex items-center gap-1.5 rounded text-[13px] font-medium text-[var(--on-surface-variant)] outline-none hover:text-[var(--primary)] focus-visible:ring-2 focus-visible:ring-[var(--primary)]"
    >
      <ArrowLeft className="size-4" aria-hidden />
      All campaigns
    </Link>
  );
}

function CampaignDetail() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const { hasRole } = useWorkspace();
  const isAdmin = hasRole("admin");

  const tabParam = searchParams.get("tab");
  const tab: TabValue = isTab(tabParam) ? tabParam : "overview";
  const [confirm, setConfirm] = useState<"start" | "pause" | "send" | null>(null);
  const [addLeadsOpen, setAddLeadsOpen] = useState(false);

  const campaignQuery = useQuery({
    queryKey: ["campaign", id],
    queryFn: () => campaignsApi.get(id),
    enabled: Number.isFinite(id),
  });
  const campaign = campaignQuery.data;
  const niche = useQuery({
    queryKey: ["niche", campaign?.niche_id],
    queryFn: () => nichesApi.get(campaign!.niche_id),
    enabled: Boolean(campaign?.niche_id),
  });

  function refresh(updated?: Campaign) {
    if (updated) queryClient.setQueryData(["campaign", id], updated);
    queryClient.invalidateQueries({ queryKey: ["campaign", id] });
    queryClient.invalidateQueries({ queryKey: ["campaigns"] });
  }

  const start = useMutation({
    mutationFn: () => campaignsApi.start(id),
    onSuccess: ({ campaign: updated }) => {
      refresh(updated);
      setConfirm(null);
      toast.success("Campaign started", {
        description: "Approved emails will send inside the sending window.",
      });
    },
  });
  const pause = useMutation({
    mutationFn: () => campaignsApi.pause(id),
    onSuccess: ({ campaign: updated }) => {
      refresh(updated);
      setConfirm(null);
      toast.success("Campaign paused", { description: "No emails will send until you start it again." });
    },
  });
  const sendNow = useMutation({
    mutationFn: () => campaignsApi.processSends(id),
    onSuccess: (result) => {
      refresh();
      queryClient.invalidateQueries({ queryKey: ["approvals"] });
      setConfirm(null);
      const summary = `${result.sent} sent, ${result.skipped} skipped, ${result.failed} failed`;
      if (result.failed > 0) toast.warning("Some emails failed to send", { description: summary });
      else if (result.sent === 0) toast.info("Nothing was due to send", { description: summary });
      else toast.success(`${result.sent} ${result.sent === 1 ? "email" : "emails"} sent`, { description: summary });
    },
  });

  function changeTab(value: unknown) {
    const next = String(value);
    // Each tab has its own filters and paging, so start from a clean URL.
    router.replace(next === "overview" ? pathname : `${pathname}?tab=${next}`, { scroll: false });
  }

  if (!Number.isFinite(id)) {
    return <ErrorState message="This campaign link isn't valid." />;
  }

  if (campaignQuery.isLoading) {
    return (
      <div role="status" aria-label="Loading campaign" className="space-y-4">
        <div className="h-10 w-2/3 max-w-md animate-pulse rounded bg-[var(--surface-container-high)]" />
        <div className="h-5 w-1/2 max-w-sm animate-pulse rounded bg-[var(--surface-container-high)]" />
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="h-24 animate-pulse rounded-lg bg-[var(--surface-container-high)]" />
          ))}
        </div>
      </div>
    );
  }

  if (campaignQuery.error || !campaign) {
    const notFound = campaignQuery.error instanceof ApiError && campaignQuery.error.status === 404;
    return (
      <ErrorState
        message={notFound ? "We couldn't find this campaign. It may have been deleted." : undefined}
        error={campaignQuery.error}
        onRetry={notFound ? undefined : () => campaignQuery.refetch()}
        action={
          notFound ? (
            <ButtonLink variant="outline" size="sm" href="/campaigns">
              Back to campaigns
            </ButtonLink>
          ) : null
        }
      />
    );
  }

  const steps = campaign.steps.length;
  const canStart = campaign.status === "draft" || campaign.status === "paused";
  const canPause = campaign.status === "active";
  const autoPaused = Boolean(campaign.auto_paused_reason) && campaign.status === "paused";

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="break-words text-[28px] leading-[36px] font-bold tracking-[-0.02em] text-[var(--on-surface)] sm:text-[36px] sm:leading-[44px]">
              {campaign.name}
            </h2>
            <CampaignStatusBadge status={campaign.status} />
          </div>
          <p className="mt-1 text-[13px] text-[var(--on-surface-variant)]">
            {niche.data ? (
              <Link href={`/niches/${campaign.niche_id}`} className="font-medium text-[var(--primary)] hover:underline">
                {niche.data.name}
              </Link>
            ) : (
              "Niche"
            )}
            {" · "}
            {steps} {steps === 1 ? "step" : "steps"} · Created {formatDate(campaign.created_at)}
          </p>
          <p className="mt-0.5 text-[12px] text-[var(--on-surface-variant)]">Sends {scheduleSummary(campaign)}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {canStart ? (
            <Button onClick={() => setConfirm("start")} disabled={steps === 0}>
              <Play aria-hidden />
              {campaign.status === "paused" ? "Resume" : "Start"}
            </Button>
          ) : null}
          {canPause ? (
            <Button variant="outline" onClick={() => setConfirm("pause")}>
              <Pause aria-hidden />
              Pause
            </Button>
          ) : null}
          <Button variant="outline" onClick={() => setAddLeadsOpen(true)}>
            <UserPlus aria-hidden />
            Add leads
          </Button>
          <ButtonLink variant="outline" href={`/campaigns/${id}/edit`}>
            <Pencil aria-hidden />
            Edit
          </ButtonLink>
          {isAdmin ? (
            <Button
              variant="secondary"
              onClick={() => setConfirm("send")}
              disabled={campaign.status !== "active"}
              title={campaign.status !== "active" ? "Start the campaign first" : undefined}
            >
              <Send aria-hidden />
              Send due emails now
            </Button>
          ) : null}
        </div>
      </div>

      {campaign.auto_paused_reason ? (
        <Alert variant="destructive" className="border-[var(--error)] bg-[var(--error-container)]/40 px-4 py-3">
          <OctagonAlert aria-hidden />
          <AlertTitle className="text-[14px] font-semibold">
            {autoPaused ? "Sending was paused automatically" : "This campaign was paused automatically earlier"}
          </AlertTitle>
          <AlertDescription className="text-[13px] text-[var(--on-error-container)]">
            <p>{campaign.auto_paused_reason}.</p>
            <p>
              Too many bounces or spam complaints can damage your sending reputation. Check the{" "}
              <button
                type="button"
                className="font-semibold underline"
                onClick={() => router.replace(`${pathname}?tab=messages&status=bounced`, { scroll: false })}
              >
                bounced emails
              </button>
              , clean your lead list, then {autoPaused ? "resume the campaign" : "keep an eye on the rates"}.
            </p>
          </AlertDescription>
        </Alert>
      ) : null}

      {campaign.completed_at ? (
        <Alert className="border-[var(--primary)]/30 bg-[var(--primary-fixed)]/40 px-4 py-3">
          <CheckCircle2 aria-hidden className="text-[var(--primary)]" />
          <AlertTitle className="text-[14px] font-semibold">Completed on {formatDateTime(campaign.completed_at)}</AlertTitle>
          <AlertDescription className="text-[13px]">
            Every lead has finished the sequence or was stopped. Add more leads to keep it going.
          </AlertDescription>
        </Alert>
      ) : null}

      {campaign.status === "draft" ? (
        <Alert className="px-4 py-3">
          <ShieldCheck aria-hidden className="text-[var(--secondary)]" />
          <AlertTitle className="text-[14px] font-semibold">This campaign is a draft</AlertTitle>
          <AlertDescription className="text-[13px]">
            Add leads to create step 1 drafts, approve them in{" "}
            <Link href={`/approvals?campaign_id=${id}`}>Approvals</Link>, then start the campaign. Approved
            emails only send while it&apos;s active.
          </AlertDescription>
        </Alert>
      ) : null}

      <Tabs value={tab} onValueChange={changeTab}>
        <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
          <TabsList variant="line" className="border-b border-[var(--outline-variant)] pb-1">
            {TABS.map((item) => (
              <TabsTrigger key={item.value} value={item.value} className="px-3 text-[13px]">
                {item.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </div>
        <TabsContent value="overview" className="pt-4">
          <CampaignOverview campaignId={id} />
          <CampaignVariantsCard campaignId={id} />
        </TabsContent>
        <TabsContent value="sequence" className="pt-4">
          <CampaignSequenceView campaign={campaign} />
          <CampaignSendersCard campaignId={id} />
        </TabsContent>
        <TabsContent value="enrollments" className="pt-4">
          <CampaignEnrollmentsTable campaignId={id} totalSteps={steps} onAddLeads={() => setAddLeadsOpen(true)} />
        </TabsContent>
        <TabsContent value="messages" className="pt-4">
          <CampaignMessagesTable campaignId={id} totalSteps={steps} />
        </TabsContent>
      </Tabs>

      <AddLeadsDialog campaign={campaign} open={addLeadsOpen} onOpenChange={setAddLeadsOpen} />

      <ConfirmDialog
        open={confirm === "start"}
        onOpenChange={(open) => !open && setConfirm(null)}
        title={campaign.status === "paused" ? "Resume this campaign?" : "Start this campaign?"}
        description={`Approved emails will send ${scheduleSummary(campaign)}. Every email still needs approval in Approvals before it can send.`}
        confirmLabel={campaign.status === "paused" ? "Resume campaign" : "Start campaign"}
        loading={start.isPending}
        onConfirm={() => start.mutate()}
      >
        {autoPaused ? (
          <p className="rounded-md bg-[var(--error-container)]/50 px-3 py-2 text-[13px] text-[var(--on-error-container)]">
            This campaign was paused because of high bounce or complaint rates. Make sure you&apos;ve fixed
            the cause before resuming.
          </p>
        ) : null}
      </ConfirmDialog>

      <ConfirmDialog
        open={confirm === "pause"}
        onOpenChange={(open) => !open && setConfirm(null)}
        title="Pause this campaign?"
        description="No emails will send while it's paused. Drafts stay in Approvals, and you can resume at any time."
        confirmLabel="Pause campaign"
        loading={pause.isPending}
        onConfirm={() => pause.mutate()}
      />

      <ConfirmDialog
        open={confirm === "send"}
        onOpenChange={(open) => !open && setConfirm(null)}
        title="Send due emails now?"
        description="This sends the campaign's approved emails that are due, without waiting for the scheduler. Only approved emails are sent, and sending limits still apply."
        confirmLabel="Send due emails"
        loading={sendNow.isPending}
        onConfirm={() => sendNow.mutate()}
      />
    </div>
  );
}

export default function CampaignDetailPage() {
  return (
    <div>
      <BackLink />
      <Suspense fallback={<div role="status" className="h-40 animate-pulse rounded-lg bg-[var(--surface-container-high)]" />}>
        <CampaignDetail />
      </Suspense>
    </div>
  );
}
