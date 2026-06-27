"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, ChevronDown, Plus } from "lucide-react";
import { CampaignStepEditor } from "@/components/campaigns/campaign-step-editor";
import { PageHeader } from "@/components/layout/page-header";
import { campaignsApi, nichesApi } from "@/lib/api/endpoints";
import { WELLPREDICT_CAMPAIGN_STEP } from "@/lib/constants/wellpredict";

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
        title="New Campaign"
        description="Configure target niche, name, limits, and step sequence for B2B outreach."
        actions={
          <Link
            href="/campaigns"
            className="flex items-center gap-2 px-4 py-2 border rounded text-[13px] font-medium transition-colors"
            style={{
              background: "var(--surface-container-lowest)",
              borderColor: "var(--outline-variant)",
              color: "var(--on-surface)",
            }}
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Campaigns
          </Link>
        }
      />

      <div className="max-w-[720px] flex flex-col gap-6">
        <div
          className="bg-white border rounded-lg p-6 shadow-sm flex flex-col gap-5"
          style={{ borderColor: "var(--outline-variant)" }}
        >
          {/* Niche select */}
          <div>
            <label
              className="block text-[13px] font-semibold mb-1.5"
              style={{ color: "var(--on-surface)" }}
            >
              Target Niche
            </label>
            <div className="relative">
              <select
                value={nicheId}
                onChange={(e) => setNicheId(e.target.value)}
                className="w-full px-3 py-2.5 border rounded text-[13px] outline-none appearance-none pr-8"
                style={{
                  borderColor: "var(--outline-variant)",
                  color: "var(--on-surface)",
                  background: "var(--surface-container-lowest)",
                }}
              >
                <option value="">Select target niche…</option>
                {(niches?.items ?? []).map((niche) => (
                  <option key={niche.id} value={String(niche.id)}>
                    {niche.name} — {niche.industry} ({niche.country})
                  </option>
                ))}
              </select>
              <ChevronDown
                className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 pointer-events-none"
                style={{ color: "var(--on-surface-variant)" }}
              />
            </div>
          </div>

          {/* Campaign Name */}
          <div>
            <label
              className="block text-[13px] font-semibold mb-1.5"
              style={{ color: "var(--on-surface)" }}
            >
              Campaign Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. CEO Outreach Q3"
              className="w-full px-3 py-2.5 border rounded text-[13px] outline-none"
              style={{
                borderColor: "var(--outline-variant)",
                color: "var(--on-surface)",
                background: "var(--surface-container-lowest)",
              }}
              onFocus={(e) => {
                e.target.style.borderColor = "var(--primary)";
                e.target.style.boxShadow = "0 0 0 1px var(--primary)";
              }}
              onBlur={(e) => {
                e.target.style.borderColor = "var(--outline-variant)";
                e.target.style.boxShadow = "none";
              }}
            />
          </div>
        </div>

        {/* Step Sequence section */}
        <div>
          <h3
            className="text-[14px] font-semibold mb-3 px-1"
            style={{ color: "var(--on-surface)" }}
          >
            Sequence Steps
          </h3>
          <CampaignStepEditor step={step} onChange={setStep} />
        </div>

        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending || !nicheId || !name}
          className="self-start flex items-center gap-2 px-5 py-2.5 rounded text-[13px] font-medium text-white transition-colors disabled:opacity-50 active:scale-[0.98] shadow-sm"
          style={{ background: "var(--primary)" }}
        >
          <Plus className="w-4 h-4" />
          {mutation.isPending ? "Creating campaign…" : "Create Campaign"}
        </button>
      </div>
    </div>
  );
}
