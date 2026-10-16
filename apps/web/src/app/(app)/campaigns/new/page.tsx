"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { LoadingState } from "@/components/shared/loading-error";
import { CampaignForm } from "@/components/campaigns/campaign-form";
import {
  defaultCampaignValues,
  toCreatePayload,
  type CampaignFormValues,
} from "@/components/campaigns/campaign-form-schema";
import { getErrorMessage } from "@/lib/api/client";
import { campaignsApi } from "@/lib/api/endpoints";
import { track } from "@/lib/analytics";

function NewCampaign() {
  const router = useRouter();
  const params = useSearchParams();
  const queryClient = useQueryClient();
  const [serverError, setServerError] = useState<string | null>(null);
  const [defaults] = useState(() => defaultCampaignValues(Number(params.get("niche_id")) || null));

  const create = useMutation({
    mutationFn: (values: CampaignFormValues) => campaignsApi.create(toCreatePayload(values)),
    onMutate: () => setServerError(null),
    onSuccess: (campaign) => {
      queryClient.invalidateQueries({ queryKey: ["campaigns"] });
      track("campaign_created");
      toast.success("Campaign created", {
        description: "Add leads to start drafting emails for approval.",
      });
      router.push(`/campaigns/${campaign.id}`);
    },
    onError: (error) => {
      setServerError(getErrorMessage(error));
      window.scrollTo({ top: 0, behavior: "smooth" });
    },
  });

  return (
    <CampaignForm
      defaultValues={defaults}
      submitLabel="Create campaign"
      submitting={create.isPending || create.isSuccess}
      serverError={serverError}
      cancelHref="/campaigns"
      onSubmit={(values) => create.mutate(values)}
    />
  );
}

export default function NewCampaignPage() {
  return (
    <div className="mx-auto max-w-4xl">
      <Link
        href="/campaigns"
        className="mb-3 inline-flex items-center gap-1.5 rounded text-[13px] font-medium text-[var(--on-surface-variant)] outline-none hover:text-[var(--primary)] focus-visible:ring-2 focus-visible:ring-[var(--primary)]"
      >
        <ArrowLeft className="size-4" aria-hidden />
        All campaigns
      </Link>
      <PageHeader
        title="New campaign"
        description="Build a multi-step sequence. Nothing is sent until you approve each email."
      />
      <Suspense fallback={<LoadingState message="Loading form…" />}>
        <NewCampaign />
      </Suspense>
    </div>
  );
}
