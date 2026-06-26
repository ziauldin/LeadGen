"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { NicheForm } from "@/components/niches/niche-form";
import { PageHeader } from "@/components/layout/page-header";
import { LoadingState } from "@/components/shared/loading-error";
import { nichesApi } from "@/lib/api/endpoints";
import { cn } from "@/lib/utils";

export default function NicheDetailPage() {
  const params = useParams();
  const id = Number(params.id);
  const queryClient = useQueryClient();

  const { data: niche, isLoading } = useQuery({
    queryKey: ["niches", id],
    queryFn: () => nichesApi.get(id),
    enabled: Number.isFinite(id),
  });

  const updateMutation = useMutation({
    mutationFn: (payload: Parameters<typeof nichesApi.update>[1]) => nichesApi.update(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["niches", id] });
      queryClient.invalidateQueries({ queryKey: ["niches"] });
      toast.success("Niche updated");
    },
    onError: () => toast.error("Failed to update niche"),
  });

  if (isLoading) return <LoadingState />;
  if (!niche) return <p className="text-sm text-destructive">Niche not found.</p>;

  return (
    <div>
      <PageHeader
        title={niche.name}
        description={`${niche.industry} · ${niche.country}`}
        actions={
          <>
            <Link href={`/search?niche_id=${niche.id}`} className={cn(buttonVariants())}>
              Run search
            </Link>
            <Link
              href={`/leads?niche_id=${niche.id}`}
              className={cn(buttonVariants({ variant: "outline" }))}
            >
              View leads
            </Link>
          </>
        }
      />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Edit niche</CardTitle>
          </CardHeader>
          <CardContent>
            <NicheForm
              niche={niche}
              submitLabel="Save changes"
              loading={updateMutation.isPending}
              onSubmit={(payload) => updateMutation.mutate(payload)}
            />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Current targeting</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="mb-2 text-sm font-medium">Roles</p>
              <div className="flex flex-wrap gap-1">
                {niche.target_roles.map((role) => (
                  <Badge key={role} variant="secondary">
                    {role}
                  </Badge>
                ))}
              </div>
            </div>
            <div>
              <p className="mb-2 text-sm font-medium">Keywords</p>
              <div className="flex flex-wrap gap-1">
                {niche.keywords.map((kw) => (
                  <Badge key={kw}>{kw}</Badge>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
