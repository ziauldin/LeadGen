"use client";

import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, Target } from "lucide-react";
import Link from "next/link";
import { NicheForm } from "@/components/niches/niche-form";
import { PageHeader } from "@/components/layout/page-header";
import { nichesApi } from "@/lib/api/endpoints";

export default function NewNichePage() {
  const router = useRouter();

  const mutation = useMutation({
    mutationFn: nichesApi.create,
    onSuccess: (niche) => {
      toast.success("Niche created successfully");
      router.push(`/niches/${niche.id}`);
    },
    onError: () => toast.error("Failed to create niche"),
  });

  return (
    <div>
      <PageHeader
        title="New Niche"
        description="Define geography, industry sector, target roles, and search queries for a target market segment."
        actions={
          <Link
            href="/niches"
            className="flex items-center gap-2 px-4 py-2 border rounded text-[13px] font-medium transition-colors"
            style={{
              background: "var(--surface-container-lowest)",
              borderColor: "var(--outline-variant)",
              color: "var(--on-surface)",
            }}
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Niches
          </Link>
        }
      />

      <div className="max-w-[640px]">
        <div
          className="bg-white border rounded-lg p-6 shadow-sm"
          style={{ borderColor: "var(--outline-variant)" }}
        >
          <h3
            className="text-[16px] font-semibold mb-6 flex items-center gap-2 pb-3 border-b"
            style={{ color: "var(--on-surface)", borderColor: "var(--outline-variant)" }}
          >
            <Target className="w-5 h-5 text-indigo-600" />
            Define Target Niche
          </h3>
          <NicheForm
            submitLabel="Create Niche"
            loading={mutation.isPending}
            onSubmit={(payload) => mutation.mutate(payload)}
          />
        </div>
      </div>
    </div>
  );
}
