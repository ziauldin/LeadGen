"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { CampaignStepEditor } from "@/components/campaigns/campaign-step-editor";
import { PageHeader } from "@/components/layout/page-header";
import { campaignsApi, nichesApi } from "@/lib/api/endpoints";
import { WELLPREDICT_CAMPAIGN_STEP } from "@/lib/constants/wellpredict";
import { cn } from "@/lib/utils";

export default function NewCampaignPage() {
  const router = useRouter();
  const [nicheId, setNicheId] = useState("");
  const [name, setName] = useState("");
  const [step, setStep] = useState(WELLPREDICT_CAMPAIGN_STEP);

  const { data: niches } = useQuery({
    queryKey: ["niches"],
    queryFn: nichesApi.list,
  });

  const mutation = useMutation({
    mutationFn: () =>
      campaignsApi.create({
        niche_id: Number(nicheId),
        name,
        daily_send_limit: 20,
        sending_window_start: "09:00",
        sending_window_end: "17:00",
        steps: [step],
      }),
    onSuccess: (campaign) => {
      toast.success("Campaign created");
      router.push(`/campaigns/${campaign.id}`);
    },
    onError: () => toast.error("Failed to create campaign"),
  });

  return (
    <div>
      <PageHeader
        title="New campaign"
        description="Create an outreach sequence with compliant templates."
        actions={
          <Link href="/campaigns" className={cn(buttonVariants({ variant: "outline" }))}>
            Back
          </Link>
        }
      />
      <Card className="max-w-3xl">
        <CardHeader>
          <CardTitle>Campaign details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Niche</label>
            <Select value={nicheId} onValueChange={(v) => setNicheId(v ?? "")}>
              <SelectTrigger>
                <SelectValue placeholder="Select niche" />
              </SelectTrigger>
              <SelectContent>
                {(niches?.items ?? []).map((niche) => (
                  <SelectItem key={niche.id} value={String(niche.id)}>
                    {niche.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Campaign name</label>
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <CampaignStepEditor step={step} onChange={setStep} />
          <Button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending || !nicheId || !name}
          >
            {mutation.isPending ? "Creating…" : "Create campaign"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
