"use client";

import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, Target } from "lucide-react";
import { NicheForm } from "@/components/niches/niche-form";
import { PageHeader } from "@/components/layout/page-header";
import { ButtonLink } from "@/components/ui/button-link";
import { nichesApi } from "@/lib/api/endpoints";
import type { NicheCreate } from "@/lib/api/types";

export default function NewNichePage() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const create = useMutation({
    mutationFn: (payload: NicheCreate) => nichesApi.create(payload),
    onSuccess: (niche) => {
      queryClient.invalidateQueries({ queryKey: ["niches"] });
      queryClient.invalidateQueries({ queryKey: ["onboarding"] });
      toast.success(`Created ${niche.name}`);
      router.push(`/niches/${niche.id}`);
    },
  });

  return (
    <div>
      <div className="mb-2">
        <ButtonLink variant="ghost" size="sm" href="/niches">
          <ArrowLeft aria-hidden />
          All niches
        </ButtonLink>
      </div>
      <PageHeader
        title="New niche"
        description="Describe one market: where it is, which industry, who you want to reach and the words that describe them."
      />

      <section
        aria-labelledby="new-niche-title"
        className="max-w-[640px] rounded-lg border border-[var(--outline-variant)] bg-white p-5 shadow-sm"
      >
        <h3
          id="new-niche-title"
          className="mb-5 flex items-center gap-2 border-b border-[var(--outline-variant)] pb-3 text-[15px] font-semibold text-[var(--on-surface)]"
        >
          <Target className="size-4 text-[var(--primary)]" aria-hidden />
          Targeting
        </h3>
        <NicheForm
          submitLabel="Create niche"
          loading={create.isPending}
          onSubmit={(payload) => create.mutate(payload)}
        />
      </section>
    </div>
  );
}
