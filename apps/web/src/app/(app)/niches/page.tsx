"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Globe, Plus, Tag, Target, Users } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { nichesApi } from "@/lib/api/endpoints";
import type { Niche } from "@/lib/api/types";

function NicheCard({ niche }: { niche: Niche }) {
  return (
    <div
      className="bg-white border rounded-lg p-5 shadow-sm hover:shadow-md transition-shadow group"
      style={{ borderColor: "var(--outline-variant)" }}
    >
      <div className="flex items-start justify-between mb-4">
        <div
          className="w-10 h-10 rounded-lg flex items-center justify-center"
          style={{ background: "var(--primary-fixed)" }}
        >
          <Target className="w-5 h-5" style={{ color: "var(--primary)" }} />
        </div>
        <Link
          href={`/niches/${niche.id}`}
          className="opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded"
          style={{ color: "var(--on-surface-variant)" }}
        >
          <ArrowRight className="w-4 h-4" />
        </Link>
      </div>

      <h3 className="text-[16px] font-semibold mb-1" style={{ color: "var(--on-surface)" }}>
        <Link
          href={`/niches/${niche.id}`}
          className="hover:underline"
          style={{ color: "inherit" }}
        >
          {niche.name}
        </Link>
      </h3>
      <p className="text-[13px] mb-4" style={{ color: "var(--on-surface-variant)" }}>
        {niche.industry}
      </p>

      <div className="flex items-center gap-3 text-[12px] mb-4" style={{ color: "var(--on-surface-variant)" }}>
        <div className="flex items-center gap-1">
          <Globe className="w-3.5 h-3.5" />
          {niche.country}
        </div>
        {niche.company_size_min || niche.company_size_max ? (
          <div className="flex items-center gap-1">
            <Users className="w-3.5 h-3.5" />
            {niche.company_size_min ?? "?"} – {niche.company_size_max ?? "?"} employees
          </div>
        ) : null}
      </div>

      {/* Target roles */}
      {niche.target_roles.length > 0 && (
        <div className="mb-3">
          <p className="text-[11px] font-semibold uppercase tracking-wider mb-1.5" style={{ color: "var(--on-surface-variant)" }}>
            Target Roles
          </p>
          <div className="flex flex-wrap gap-1.5">
            {niche.target_roles.slice(0, 4).map((role) => (
              <span
                key={role}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium"
                style={{
                  background: "var(--primary-fixed)",
                  color: "var(--on-primary-fixed)",
                }}
              >
                {role}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Keywords */}
      {niche.keywords.length > 0 && (
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider mb-1.5" style={{ color: "var(--on-surface-variant)" }}>
            Keywords
          </p>
          <div className="flex flex-wrap gap-1.5">
            {niche.keywords.slice(0, 5).map((kw) => (
              <span
                key={kw}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px]"
                style={{
                  background: "var(--surface-container)",
                  color: "var(--on-surface-variant)",
                }}
              >
                <Tag className="w-2.5 h-2.5" />
                {kw}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="mt-4 pt-4 border-t flex items-center justify-between" style={{ borderColor: "var(--outline-variant)" }}>
        <Link
          href={`/leads?niche_id=${niche.id}`}
          className="text-[12px] font-medium"
          style={{ color: "var(--primary)" }}
        >
          View leads →
        </Link>
        <Link
          href={`/search?niche_id=${niche.id}`}
          className="text-[12px] font-medium"
          style={{ color: "var(--on-surface-variant)" }}
        >
          Run search
        </Link>
      </div>
    </div>
  );
}

export default function NichesPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["niches"],
    queryFn: nichesApi.list,
  });

  return (
    <div>
      <PageHeader
        title="Niches"
        description="Target market segments with qualification criteria and outreach scope."
        actions={
          <Link
            href="/niches/new"
            className="flex items-center gap-2 px-5 py-2 rounded text-[13px] font-medium text-white transition-colors active:scale-95 shadow-sm"
            style={{ background: "var(--primary)" }}
            onMouseEnter={(e: React.MouseEvent<HTMLAnchorElement>) =>
              (e.currentTarget.style.background = "var(--surface-tint)")
            }
            onMouseLeave={(e: React.MouseEvent<HTMLAnchorElement>) =>
              (e.currentTarget.style.background = "var(--primary)")
            }
          >
            <Plus className="w-4 h-4" />
            New Niche
          </Link>
        }
      />

      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="bg-white border rounded-lg p-5 h-56 animate-pulse"
              style={{ borderColor: "var(--outline-variant)" }}
            />
          ))}
        </div>
      ) : (data?.items ?? []).length === 0 ? (
        <div
          className="flex flex-col items-center justify-center py-24 rounded-lg border"
          style={{
            background: "var(--surface-container-low)",
            borderColor: "var(--outline-variant)",
          }}
        >
          <div
            className="w-16 h-16 rounded-full flex items-center justify-center mb-4"
            style={{ background: "var(--primary-fixed)" }}
          >
            <Target className="w-8 h-8" style={{ color: "var(--primary)" }} />
          </div>
          <h3 className="text-[18px] font-semibold mb-2" style={{ color: "var(--on-surface)" }}>
            No niches yet
          </h3>
          <p className="text-[14px] mb-6" style={{ color: "var(--on-surface-variant)" }}>
            Create a niche to define your target market and start generating leads.
          </p>
          <Link
            href="/niches/new"
            className="flex items-center gap-2 px-5 py-2 rounded text-[13px] font-medium text-white"
            style={{ background: "var(--primary)" }}
          >
            <Plus className="w-4 h-4" />
            Create first niche
          </Link>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {(data?.items ?? []).map((niche) => (
            <NicheCard key={niche.id} niche={niche} />
          ))}
        </div>
      )}
    </div>
  );
}
