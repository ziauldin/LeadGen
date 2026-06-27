"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, Globe, Play, Search, Tag, Target, Users } from "lucide-react";
import { NicheForm } from "@/components/niches/niche-form";
import { PageHeader } from "@/components/layout/page-header";
import { LoadingState } from "@/components/shared/loading-error";
import { nichesApi } from "@/lib/api/endpoints";

export default function NicheDetailPage() {
  const params = useParams();
  const id = Number(params.id);
  const router = useRouter();
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
      toast.success("Niche updated successfully");
    },
    onError: () => toast.error("Failed to update niche"),
  });

  if (isLoading) return <LoadingState />;
  if (!niche) return <p className="text-sm text-destructive font-semibold">Niche not found.</p>;

  return (
    <div>
      <PageHeader
        title={niche.name}
        description={`Target market targeting ${niche.industry} in ${niche.country}.`}
        actions={
          <>
            <button
              onClick={() => router.back()}
              className="flex items-center gap-2 px-4 py-2 border rounded text-[13px] font-medium transition-colors"
              style={{
                background: "var(--surface-container-lowest)",
                borderColor: "var(--outline-variant)",
                color: "var(--on-surface)",
              }}
            >
              <ArrowLeft className="w-4 h-4" />
              Back
            </button>
            <Link
              href={`/search?niche_id=${niche.id}`}
              className="flex items-center gap-2 px-5 py-2 border rounded text-[13px] font-medium transition-colors hover:shadow-sm"
              style={{
                borderColor: "var(--primary)",
                color: "var(--primary)",
                background: "var(--primary-fixed)",
              }}
            >
              <Search className="w-4 h-4" />
              Run Search
            </Link>
            <Link
              href={`/leads?niche_id=${niche.id}`}
              className="flex items-center gap-2 px-5 py-2 rounded text-[13px] font-medium text-white transition-colors active:scale-95 shadow-sm"
              style={{ background: "var(--primary)" }}
            >
              <Play className="w-4 h-4" />
              View Leads
            </Link>
          </>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        {/* Left: Edit Form */}
        <div
          className="bg-white border rounded-lg p-6 shadow-sm"
          style={{ borderColor: "var(--outline-variant)" }}
        >
          <h3
            className="text-[16px] font-semibold mb-6 flex items-center gap-2 pb-3 border-b"
            style={{ color: "var(--on-surface)", borderColor: "var(--outline-variant)" }}
          >
            <Target className="w-5 h-5 text-indigo-600" />
            Edit Niche Targeting Criteria
          </h3>
          <NicheForm
            niche={niche}
            submitLabel="Save Changes"
            loading={updateMutation.isPending}
            onSubmit={(payload) => updateMutation.mutate(payload)}
          />
        </div>

        {/* Right: Current targeting stats */}
        <div className="flex flex-col gap-6">
          <div
            className="bg-white border rounded-lg p-6 shadow-sm"
            style={{ borderColor: "var(--outline-variant)" }}
          >
            <h3
              className="text-[15px] font-semibold mb-4"
              style={{ color: "var(--on-surface)" }}
            >
              Current Parameters
            </h3>

            <div className="space-y-4">
              {/* Country & Industry */}
              <div className="flex items-center gap-3">
                <div
                  className="w-8 h-8 rounded flex items-center justify-center shrink-0"
                  style={{ background: "var(--surface-container-low)" }}
                >
                  <Globe className="w-4 h-4 text-slate-600" />
                </div>
                <div>
                  <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Geography &amp; Sector</p>
                  <p className="text-[13px] font-medium" style={{ color: "var(--on-surface)" }}>
                    {niche.industry} · {niche.country}
                  </p>
                </div>
              </div>

              {/* Company size */}
              <div className="flex items-center gap-3">
                <div
                  className="w-8 h-8 rounded flex items-center justify-center shrink-0"
                  style={{ background: "var(--surface-container-low)" }}
                >
                  <Users className="w-4 h-4 text-slate-600" />
                </div>
                <div>
                  <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Employee Range</p>
                  <p className="text-[13px] font-medium" style={{ color: "var(--on-surface)" }}>
                    {niche.company_size_min ?? "0"} – {niche.company_size_max ?? "∞"} employees
                  </p>
                </div>
              </div>

              {/* Target Roles */}
              <div className="border-t pt-3" style={{ borderColor: "var(--outline-variant)" }}>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-2">Target Roles</p>
                <div className="flex flex-wrap gap-1.5">
                  {niche.target_roles.map((role) => (
                    <span
                      key={role}
                      className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium"
                      style={{
                        background: "var(--primary-fixed)",
                        color: "var(--on-primary-fixed)",
                      }}
                    >
                      {role}
                    </span>
                  ))}
                  {niche.target_roles.length === 0 && (
                    <span className="text-[12px] italic text-slate-400">No specific roles defined.</span>
                  )}
                </div>
              </div>

              {/* Keywords */}
              <div className="border-t pt-3" style={{ borderColor: "var(--outline-variant)" }}>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-2">Matching Keywords</p>
                <div className="flex flex-wrap gap-1.5">
                  {niche.keywords.map((kw) => (
                    <span
                      key={kw}
                      className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-[11px]"
                      style={{
                        background: "var(--surface-container)",
                        color: "var(--on-surface-variant)",
                      }}
                    >
                      <Tag className="w-2.5 h-2.5" />
                      {kw}
                    </span>
                  ))}
                  {niche.keywords.length === 0 && (
                    <span className="text-[12px] italic text-slate-400">No keywords defined.</span>
                  )}
                </div>
              </div>

              {/* Exclusion Keywords */}
              {niche.exclusion_keywords.length > 0 && (
                <div className="border-t pt-3" style={{ borderColor: "var(--outline-variant)" }}>
                  <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-2">Exclusion Keywords</p>
                  <div className="flex flex-wrap gap-1.5">
                    {niche.exclusion_keywords.map((kw) => (
                      <span
                        key={kw}
                        className="inline-flex items-center px-2 py-0.5 rounded text-[11px]"
                        style={{
                          background: "var(--error-container)",
                          color: "var(--on-error-container)",
                        }}
                      >
                        {kw}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
