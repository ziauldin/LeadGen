"use client";

import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { NicheForm } from "@/components/niches/niche-form";
import { PageHeader } from "@/components/layout/page-header";
import { nichesApi } from "@/lib/api/endpoints";

export default function NewNichePage() {
  const router = useRouter();

  const mutation = useMutation({
    mutationFn: nichesApi.create,
    onSuccess: (niche) => {
      toast.success("Niche created");
      router.push(`/niches/${niche.id}`);
    },
    onError: () => toast.error("Failed to create niche"),
  });

  return (
    <div>
      <PageHeader title="New niche" description="Define a target market for lead collection." />
      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle>Niche details</CardTitle>
        </CardHeader>
        <CardContent>
          <NicheForm
            submitLabel="Create niche"
            loading={mutation.isPending}
            onSubmit={(payload) => mutation.mutate(payload)}
          />
        </CardContent>
      </Card>
    </div>
  );
}
