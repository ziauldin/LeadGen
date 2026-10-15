"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, Globe, Search, Tag, Target, Trash2, Users } from "lucide-react";
import { NicheForm } from "@/components/niches/niche-form";
import { DeleteNicheDialog } from "@/components/niches/delete-niche-dialog";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { ButtonLink } from "@/components/ui/button-link";
import { ErrorState, LoadingState } from "@/components/shared/loading-error";
import { nichesApi } from "@/lib/api/endpoints";
import type { NicheCreate } from "@/lib/api/types";

function Chips({
  items,
  empty,
  tone = "neutral",
}: {
  items: string[];
  empty: string;
  tone?: "primary" | "neutral" | "error";
}) {
  if (items.length === 0) {
    return <p className="text-[12px] text-[var(--on-surface-variant)] italic">{empty}</p>;
  }
  const toneClass =
    tone === "primary"
      ? "bg-[var(--primary-fixed)] text-[var(--on-primary-fixed)]"
      : tone === "error"
        ? "bg-[var(--error-container)] text-[var(--on-error-container)]"
        : "bg-[var(--surface-container)] text-[var(--on-surface-variant)]";
  return (
    <ul className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <li
          key={item}
          className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-medium ${toneClass}`}
        >
          {tone === "neutral" ? <Tag className="size-2.5" aria-hidden /> : null}
          {item}
        </li>
      ))}
    </ul>
  );
}

export default function NicheDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const valid = Number.isFinite(id) && id > 0;
  const router = useRouter();
  const queryClient = useQueryClient();
  const [deleteOpen, setDeleteOpen] = useState(false);

  const niche = useQuery({
    queryKey: ["niches", "detail", id],
    queryFn: () => nichesApi.get(id),
    enabled: valid,
  });

  const update = useMutation({
    mutationFn: (payload: NicheCreate) => nichesApi.update(id, payload),
    onSuccess: (updated) => {
      queryClient.setQueryData(["niches", "detail", id], updated);
      queryClient.invalidateQueries({ queryKey: ["niches"] });
      toast.success("Niche saved");
    },
  });

  if (!valid) return <ErrorState message="This niche link isn't valid." />;
  if (niche.isLoading) return <LoadingState message="Loading niche…" />;
  if (niche.error || !niche.data) {
    return (
      <div className="space-y-4">
        <ButtonLink variant="ghost" size="sm" href="/niches">
          <ArrowLeft aria-hidden />
          All niches
        </ButtonLink>
        <ErrorState error={niche.error} onRetry={() => niche.refetch()} />
      </div>
    );
  }

  const data = niche.data;
  const size =
    data.company_size_min || data.company_size_max
      ? `${data.company_size_min ?? 1} – ${data.company_size_max ?? "any"} people`
      : "Any size";

  return (
    <div>
      <div className="mb-2">
        <ButtonLink variant="ghost" size="sm" href="/niches">
          <ArrowLeft aria-hidden />
          All niches
        </ButtonLink>
      </div>
      <PageHeader
        title={data.name}
        description={`${data.industry} in ${data.country}`}
        actions={
          <>
            <ButtonLink variant="outline" href={`/search?niche_id=${data.id}`}>
              <Search aria-hidden />
              Run a search
            </ButtonLink>
            <ButtonLink href={`/leads?niche_id=${data.id}`}>
              <Users aria-hidden />
              View leads
            </ButtonLink>
            <Button variant="destructive" onClick={() => setDeleteOpen(true)}>
              <Trash2 aria-hidden />
              Delete
            </Button>
          </>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <section
          aria-labelledby="niche-edit-title"
          className="rounded-lg border border-[var(--outline-variant)] bg-white p-5 shadow-sm"
        >
          <h3
            id="niche-edit-title"
            className="mb-5 flex items-center gap-2 border-b border-[var(--outline-variant)] pb-3 text-[15px] font-semibold text-[var(--on-surface)]"
          >
            <Target className="size-4 text-[var(--primary)]" aria-hidden />
            Targeting
          </h3>
          <NicheForm
            niche={data}
            submitLabel="Save changes"
            loading={update.isPending}
            onSubmit={(payload) => update.mutate(payload)}
          />
        </section>

        <aside
          aria-labelledby="niche-summary-title"
          className="h-fit rounded-lg border border-[var(--outline-variant)] bg-white p-5 shadow-sm"
        >
          <h3
            id="niche-summary-title"
            className="mb-4 text-[15px] font-semibold text-[var(--on-surface)]"
          >
            Summary
          </h3>
          <dl className="space-y-4 text-[13px]">
            <div className="flex items-start gap-3">
              <Globe className="mt-0.5 size-4 text-[var(--on-surface-variant)]" aria-hidden />
              <div>
                <dt className="text-[12px] text-[var(--on-surface-variant)]">Market</dt>
                <dd className="font-medium text-[var(--on-surface)]">
                  {data.industry} · {data.country}
                </dd>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <Users className="mt-0.5 size-4 text-[var(--on-surface-variant)]" aria-hidden />
              <div>
                <dt className="text-[12px] text-[var(--on-surface-variant)]">Company size</dt>
                <dd className="font-medium text-[var(--on-surface)]">{size}</dd>
              </div>
            </div>
            <div className="border-t border-[var(--outline-variant)] pt-3">
              <dt className="mb-2 text-[12px] text-[var(--on-surface-variant)]">Target roles</dt>
              <dd>
                <Chips items={data.target_roles} empty="Any role" tone="primary" />
              </dd>
            </div>
            <div className="border-t border-[var(--outline-variant)] pt-3">
              <dt className="mb-2 text-[12px] text-[var(--on-surface-variant)]">Keywords</dt>
              <dd>
                <Chips items={data.keywords} empty="No keywords yet" />
              </dd>
            </div>
            <div className="border-t border-[var(--outline-variant)] pt-3">
              <dt className="mb-2 text-[12px] text-[var(--on-surface-variant)]">Excluded</dt>
              <dd>
                <Chips items={data.exclusion_keywords} empty="Nothing excluded" tone="error" />
              </dd>
            </div>
          </dl>
        </aside>
      </div>

      <DeleteNicheDialog
        niche={data}
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        onDeleted={() => router.push("/niches")}
      />
    </div>
  );
}
