"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { ErrorState, LoadingState } from "@/components/shared/loading-error";
import { CampaignForm } from "@/components/campaigns/campaign-form";
import {
  campaignToFormValues,
  toUpdatePayload,
  type CampaignFormValues,
} from "@/components/campaigns/campaign-form-schema";
import { getErrorMessage } from "@/lib/api/client";
import { campaignsApi } from "@/lib/api/endpoints";

export default function EditCampaignPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const router = useRouter();
  const queryClient = useQueryClient();
  const [serverError, setServerError] = useState<string | null>(null);

  const campaign = useQuery({
    queryKey: ["campaign", id],
    queryFn: () => campaignsApi.get(id),
    enabled: Number.isFinite(id),
  });

  const update = useMutation({
    mutationFn: (values: CampaignFormValues) => campaignsApi.update(id, toUpdatePayload(values)),
    onMutate: () => setServerError(null),
    onSuccess: (updated) => {
      queryClient.setQueryData(["campaign", id], updated);
      queryClient.invalidateQueries({ queryKey: ["campaign", id] });
      queryClient.invalidateQueries({ queryKey: ["campaigns"] });
      toast.success("Campaign saved");
      router.push(`/campaigns/${id}`);
    },
    onError: (error) => {
      setServerError(getErrorMessage(error));
      window.scrollTo({ top: 0, behavior: "smooth" });
    },
  });

  return (
    <div className="mx-auto max-w-4xl">
      <Link
        href={`/campaigns/${id}`}
        className="mb-3 inline-flex items-center gap-1.5 rounded text-[13px] font-medium text-[var(--on-surface-variant)] outline-none hover:text-[var(--primary)] focus-visible:ring-2 focus-visible:ring-[var(--primary)]"
      >
        <ArrowLeft className="size-4" aria-hidden />
        Back to campaign
      </Link>
      <PageHeader
        title={campaign.data ? `Edit ${campaign.data.name}` : "Edit campaign"}
        description="Changes apply to emails drafted from now on. Every email still needs approval."
      />
      {campaign.isLoading ? (
        <LoadingState message="Loading campaign…" />
      ) : campaign.error ? (
        <ErrorState error={campaign.error} onRetry={() => campaign.refetch()} />
      ) : campaign.data ? (
        <CampaignForm
          key={campaign.data.id}
          editing
          defaultValues={campaignToFormValues(campaign.data)}
          submitLabel="Save changes"
          submitting={update.isPending || update.isSuccess}
          serverError={serverError}
          cancelHref={`/campaigns/${id}`}
          onSubmit={(values) => update.mutate(values)}
        />
      ) : null}
    </div>
  );
}
